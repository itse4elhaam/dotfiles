import type { Plugin } from "@opencode-ai/plugin";
import { tool } from "@opencode-ai/plugin/tool";
import { z } from "zod";

import { resolveConfig, type IPluginConfig } from "./config.js";
import { evaluatePolicy, type IFileChange } from "./policy.js";
import { createProposal, getProposal, type ICandidateChange } from "./proposals.js";
import { formatContextPack, generateContextPack } from "./context-pack.js";
import {
  applyApprovedChanges,
  createCandidateWorktree,
  applyCandidateChanges,
  discardWorktree,
  getWorktreeDiff,
} from "./worktree.js";
import { runValidation } from "./validation.js";
import { generateDiffReport } from "./reporting.js";

// ---------------------------------------------------------------------------
// In-memory state
// ---------------------------------------------------------------------------

const worktrees = new Map<string, Awaited<ReturnType<typeof createCandidateWorktree>>>();
const validationStatus = new Map<string, boolean>();

// ---------------------------------------------------------------------------
// Tool: selfmod_propose
// ---------------------------------------------------------------------------

const createProposeTool = (config: IPluginConfig) => tool({
  description: "Create a self-modification proposal describing intended changes for review",
  args: {
    title: z.string().min(1).describe("Short title for the proposal"),
    description: z.string().min(1).describe("Reason and intent for the change"),
    changes: z.array(z.object({
      filePath: z.string().min(1).describe("Absolute or project-relative file path"),
      changeType: z.enum(["add", "modify", "delete", "rename"]).describe("Type of operation"),
      newContent: z.string().optional().describe("New file content (omit for deletions)"),
      oldContent: z.string().optional().describe("Previous content (omit for additions)"),
    })).min(1).describe("The set of file changes in this proposal"),
  },
  execute: async (args) => {
    const changes: IFileChange[] = args.changes.map((c) => ({
      filePath: c.filePath,
      changeType: c.changeType,
      newContent: c.newContent,
      oldContent: c.oldContent,
    }));

    const decision = evaluatePolicy({ changes, config });
    const proposal = createProposal({
      title: args.title,
      description: args.description,
      changes,
      riskLevel: decision.riskLevel,
    });

    return JSON.stringify({
      proposalId: proposal.id,
      title: proposal.title,
      riskLevel: proposal.riskLevel,
      allowed: decision.allowed,
      reason: decision.reason,
      findings: decision.findings,
      next: decision.allowed
        ? "Run selfmod_worktree, then selfmod_validate, selfmod_diff, and selfmod_apply with explicit confirmation."
        : "Revise the proposal or raise riskThreshold intentionally before creating a worktree.",
    });
  },
});

// ---------------------------------------------------------------------------
// Tool: selfmod_context
// ---------------------------------------------------------------------------

const createContextPackTool = (config: IPluginConfig) => tool({
  description: "Gather a context pack of current OpenCode configuration for informed proposals",
  args: {
    projectDir: z.string().default(".").describe("Project root directory"),
  },
  execute: async (args, ctx) => {
    const projectDir = args.projectDir === "."
      ? ctx.directory
      : args.projectDir;

    const pack = await generateContextPack({
      projectDir,
      pluginConfig: config,
      homeConfigDir: config.homeConfigDir ?? process.env.HOME,
    });
    const summary = formatContextPack(pack);

    return JSON.stringify({
      context: summary.markdown,
      hasOpencodeConfig: pack.opencodeConfig !== null,
      hasTuiConfig: pack.tuiConfig !== null,
      agentCount: pack.agents.length,
      commandCount: pack.commands.length,
      toolCount: pack.customTools.length,
      contextFileCount: pack.contextFiles.length,
      pluginConfigCount: pack.pluginConfigs.length,
      totalFiles: summary.totalFiles,
      truncated: summary.truncated,
      projectDir: pack.projectDir,
    });
  },
});

// ---------------------------------------------------------------------------
// Tool: selfmod_evaluate
// ---------------------------------------------------------------------------

const createEvaluateTool = (config: IPluginConfig) => tool({
  description: "Evaluate a proposal against policy rules (dry run — no changes made)",
  args: {
    proposalId: z.string().min(1).describe("ID of the proposal to evaluate"),
  },
  execute: async (args) => {
    const proposal = getProposal(args.proposalId);
    if (!proposal) {
      return JSON.stringify({ error: `Proposal "${args.proposalId}" not found` });
    }

    const decision = evaluatePolicy({ changes: proposal.changes, config });

    return JSON.stringify({
      proposalId: args.proposalId,
      allowed: decision.allowed,
      riskLevel: decision.riskLevel,
      reason: decision.reason,
      matchedRule: decision.matchedRule,
      findings: decision.findings,
    });
  },
});

// ---------------------------------------------------------------------------
// Tool: selfmod_worktree
// ---------------------------------------------------------------------------

const createWorktreeTool = (config: IPluginConfig) => tool({
  description: "Create an isolated git worktree and apply candidate changes for testing",
  args: {
    proposalId: z.string().min(1).describe("ID of the proposal to test"),
    projectDir: z.string().default(".").describe("Project root with git repo"),
  },
  execute: async (args, ctx) => {
    const proposal = getProposal(args.proposalId);
    if (!proposal) {
      return JSON.stringify({ error: `Proposal "${args.proposalId}" not found` });
    }

    const projectDir = args.projectDir === "." ? ctx.directory : args.projectDir;
    const decision = evaluatePolicy({ changes: proposal.changes, config });

    if (!decision.allowed) {
      return JSON.stringify({
        proposalId: proposal.id,
        error: "Policy gate failed; worktree was not created",
        reason: decision.reason,
        findings: decision.findings,
      });
    }

    try {
      const worktree = createCandidateWorktree({
        projectDir,
        proposalId: proposal.id,
        config,
      });

      await applyCandidateChanges({
        worktree,
        changes: proposal.changes as ICandidateChange[],
      });

      const diff = getWorktreeDiff(worktree.path);
      worktrees.set(proposal.id, worktree);

      return JSON.stringify({
        proposalId: proposal.id,
        worktreePath: worktree.path,
        branch: worktree.branch,
        riskLevel: decision.riskLevel,
        diffLines: diff.length === 0 ? 0 : diff.split("\n").length,
        diffPreview: diff.slice(0, 2000),
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return JSON.stringify({ error: `Worktree creation failed: ${message}` });
    }
  },
});

// ---------------------------------------------------------------------------
// Tool: selfmod_validate
// ---------------------------------------------------------------------------

const createValidateTool = (config: IPluginConfig) => tool({
  description: "Run validation commands against a candidate worktree",
  args: {
    proposalId: z.string().min(1).describe("Proposal ID with an active worktree"),
    commands: z.array(z.string()).optional().describe("Validation commands to run; defaults to plugin validationCommands"),
  },
  execute: async (args) => {
    const worktree = worktrees.get(args.proposalId);
    if (!worktree) {
      return JSON.stringify({ error: `No active worktree for proposal "${args.proposalId}"` });
    }

    const commands = args.commands ?? config.validationCommands;
    const result = runValidation({
      worktree,
      commands,
    });
    validationStatus.set(args.proposalId, result.passed);

    return JSON.stringify({
      proposalId: args.proposalId,
      commands,
      passed: result.passed,
      errorCount: result.errors.length,
      errors: result.errors,
      output: result.output.slice(0, 2000),
    });
  },
});

// ---------------------------------------------------------------------------
// Tool: selfmod_diff
// ---------------------------------------------------------------------------

const diffTool = tool({
  description: "Show the structured diff report for a candidate proposal",
  args: {
    proposalId: z.string().min(1).describe("Proposal ID with an active worktree"),
  },
  execute: async (args) => {
    const proposal = getProposal(args.proposalId);
    const worktree = worktrees.get(args.proposalId);

    if (!proposal || !worktree) {
      return JSON.stringify({ error: `No active proposal/worktree for "${args.proposalId}"` });
    }

    const report = generateDiffReport({
      proposalId: proposal.id,
      worktree,
      changes: proposal.changes,
      riskLevel: proposal.riskLevel,
    });

    return JSON.stringify({
      proposalId: report.proposalId,
      summary: report.summary,
      fileCount: report.entries.length,
      rawDiff: report.rawDiff.slice(0, 3000),
    });
  },
});

// ---------------------------------------------------------------------------
// Tool: selfmod_apply (guarded — copies from worktree to active config)
// ---------------------------------------------------------------------------

const createApplyTool = (config: IPluginConfig) => tool({
  description: "Apply an approved, validated proposal from worktree to active config",
  args: {
    proposalId: z.string().min(1).describe("Proposal ID to apply"),
    projectDir: z.string().default(".").describe("Project root with git repo"),
    confirm: z.string().describe('Must exactly equal "apply:<proposalId>"'),
  },
  execute: async (args, ctx) => {
    const proposal = getProposal(args.proposalId);
    const worktree = worktrees.get(args.proposalId);

    if (!proposal || !worktree) {
      return JSON.stringify({ error: `No active proposal/worktree for "${args.proposalId}"` });
    }

    const expectedConfirmation = `apply:${args.proposalId}`;
    if (args.confirm !== expectedConfirmation) {
      return JSON.stringify({
        proposalId: args.proposalId,
        status: "blocked",
        reason: `Explicit confirmation required. Re-run with confirm="${expectedConfirmation}" after reviewing selfmod_diff.`,
      });
    }

    if (validationStatus.get(args.proposalId) !== true) {
      return JSON.stringify({
        proposalId: args.proposalId,
        status: "blocked",
        reason: "Validation has not passed for this proposal. Run selfmod_validate first.",
      });
    }

    const decision = evaluatePolicy({ changes: proposal.changes, config });
    if (!decision.allowed) {
      return JSON.stringify({
        proposalId: args.proposalId,
        status: "blocked",
        reason: decision.reason,
        findings: decision.findings,
      });
    }

    const projectDir = args.projectDir === "." ? ctx.directory : args.projectDir;
    await applyApprovedChanges({
      worktree,
      projectDir,
      changes: proposal.changes as readonly ICandidateChange[],
    });

    return JSON.stringify({
      proposalId: args.proposalId,
      status: "applied",
      appliedFiles: proposal.changes.map((change) => change.filePath),
      next: "Run project validation again in the active checkout, then selfmod_cleanup.",
    });
  },
});

// ---------------------------------------------------------------------------
// Tool: selfmod_cleanup
// ---------------------------------------------------------------------------

const cleanupTool = tool({
  description: "Discard a candidate worktree and remove its branch",
  args: {
    proposalId: z.string().min(1).describe("Proposal ID to clean up"),
    projectDir: z.string().default(".").describe("Project root with git repo"),
  },
  execute: async (args, ctx) => {
    const worktree = worktrees.get(args.proposalId);
    if (!worktree) {
      return JSON.stringify({ error: `No active worktree for "${args.proposalId}"` });
    }

    const projectDir = args.projectDir === "." ? ctx.directory : args.projectDir;

    discardWorktree({ worktree, projectDir });
    worktrees.delete(args.proposalId);

    return JSON.stringify({ proposalId: args.proposalId, status: "cleaned" });
  },
});

// ---------------------------------------------------------------------------
// Main: SelfModPlugin
// ---------------------------------------------------------------------------

export const SelfModPlugin: Plugin = async (_input, options) => {
  const config: IPluginConfig = resolveConfig(options as Record<string, unknown> | undefined);

  return {
    tool: {
      selfmod_propose: createProposeTool(config),
      selfmod_context: createContextPackTool(config),
      selfmod_evaluate: createEvaluateTool(config),
      selfmod_worktree: createWorktreeTool(config),
      selfmod_validate: createValidateTool(config),
      selfmod_diff: diffTool,
      selfmod_apply: createApplyTool(config),
      selfmod_cleanup: cleanupTool,
    },
  };
};

export default SelfModPlugin;
