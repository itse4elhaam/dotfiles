import type { IFileChange } from "./policy.js";
import type { IRiskThreshold } from "./config.js";
import { getWorktreeDiff } from "./worktree.js";
import type { IWorktreeInfo } from "./worktree.js";

// ---------------------------------------------------------------------------
// Diff report types
// ---------------------------------------------------------------------------

export interface IDiffEntry {
  readonly filePath: string;
  readonly changeType: "add" | "modify" | "delete" | "rename";
  readonly riskLevel: IRiskThreshold;
  readonly diffHunk: string;
}

export interface IDiffReport {
  readonly proposalId: string;
  readonly worktreePath: string;
  readonly entries: readonly IDiffEntry[];
  readonly rawDiff: string;
  readonly summary: string;
}

// ---------------------------------------------------------------------------
// Report generation
// ---------------------------------------------------------------------------

export interface IGenerateDiffReportInput {
  readonly proposalId: string;
  readonly worktree: IWorktreeInfo;
  readonly changes: readonly IFileChange[];
  readonly riskLevel: IRiskThreshold;
}

/**
 * Generate a structured diff report from a candidate worktree.
 */
export function generateDiffReport(input: IGenerateDiffReportInput): IDiffReport {
  const { proposalId, worktree, changes, riskLevel } = input;
  const rawDiff = getWorktreeDiff(worktree.path);

  const entries: IDiffEntry[] = changes.map((change) => ({
    filePath: change.filePath,
    changeType: change.changeType,
    riskLevel,
    diffHunk: extractHunk(rawDiff, change.filePath),
  }));

  const addedCount = entries.filter((e) => e.changeType === "add").length;
  const modifiedCount = entries.filter((e) => e.changeType === "modify").length;
  const deletedCount = entries.filter((e) => e.changeType === "delete").length;

  const summary = [
    `Proposal: ${proposalId}`,
    `Risk level: ${riskLevel}`,
    `Files: ${entries.length} total (${addedCount} added, ${modifiedCount} modified, ${deletedCount} deleted)`,
    ...entries.map((e) => `  ${formatChangeType(e.changeType)} ${e.filePath} [${e.riskLevel}]`),
  ].join("\n");

  return {
    proposalId,
    worktreePath: worktree.path,
    entries,
    rawDiff,
    summary,
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatChangeType(type: "add" | "modify" | "delete" | "rename"): string {
  switch (type) {
    case "add":    return "[A]";
    case "modify": return "[M]";
    case "delete": return "[D]";
    case "rename": return "[R]";
  }
}

/**
 * Extract the diff hunk for a specific file path from the raw diff output.
 */
function extractHunk(rawDiff: string, filePath: string): string {
  const lines = rawDiff.split("\n");
  const result: string[] = [];
  let inTarget = false;

  for (const line of lines) {
    if (line.startsWith("diff --git")) {
      inTarget = line.includes(filePath);
    }
    if (inTarget) {
      result.push(line);
    }
  }

  return result.join("\n");
}
