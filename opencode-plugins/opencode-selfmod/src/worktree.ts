import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, isAbsolute, relative, resolve } from "node:path";
import { execSync } from "node:child_process";
import type { ICandidateChange } from "./proposals.js";
import type { IPluginConfig } from "./config.js";

// ---------------------------------------------------------------------------
// Worktree types
// ---------------------------------------------------------------------------

export interface IWorktreeInfo {
  /** Absolute path to the source project root. */
  readonly projectDir: string;
  /** Absolute path to the worktree root. */
  readonly path: string;
  /** Name of the temporary branch. */
  readonly branch: string;
  /** Raw git diff output (empty if no changes applied yet). */
  readonly diff: string;
  /** The proposal ID this worktree was created for. */
  readonly proposalId: string;
}

// ---------------------------------------------------------------------------
// Worktree creation
// ---------------------------------------------------------------------------

export interface ICreateWorktreeInput {
  readonly projectDir: string;
  readonly proposalId: string;
  readonly config: IPluginConfig;
}

/**
 * Create an isolated git worktree + branch for testing candidate changes.
 * Returns the worktree info or throws if creation fails.
 */
export function createCandidateWorktree(input: ICreateWorktreeInput): IWorktreeInfo {
  const { projectDir, proposalId, config } = input;
  const workDir = resolve(projectDir, config.workDir);

  execSync(`mkdir -p "${workDir}"`, { cwd: projectDir });

  const sanitisedId = proposalId.replace(/[^a-zA-Z0-9_-]/g, "_");
  const branch = `selfmod/${sanitisedId}`;
  const worktreePath = resolve(workDir, sanitisedId);

  execSync(`git branch -D "${branch}" 2>/dev/null || true`, {
    cwd: projectDir,
    stdio: "pipe",
  });

  execSync(`git worktree add -b "${branch}" "${worktreePath}" HEAD`, {
    cwd: projectDir,
    stdio: "pipe",
  });

  return {
    projectDir,
    path: worktreePath,
    branch,
    diff: "",
    proposalId,
  };
}

// ---------------------------------------------------------------------------
// Apply changes to worktree
// ---------------------------------------------------------------------------

export interface IApplyChangesInput {
  readonly worktree: IWorktreeInfo;
  readonly changes: readonly ICandidateChange[];
}

/**
 * Apply candidate changes to the worktree. Writes files and stages them.
 */
export async function applyCandidateChanges(input: IApplyChangesInput): Promise<void> {
  const { worktree, changes } = input;

  for (const change of changes) {
    const relPath = toProjectRelativePath(change.filePath, worktree.projectDir);
    const absPath = resolve(worktree.path, relPath);

    if (change.changeType === "delete") {
      await rm(absPath, { force: true, recursive: false });
      continue;
    }

    if (change.newContent !== undefined) {
      await mkdir(dirname(absPath), { recursive: true });
      await writeFile(absPath, change.newContent, "utf8");
    }
  }

  // Stage all changes
  execSync("git add -A", { cwd: worktree.path, stdio: "pipe" });
}

// ---------------------------------------------------------------------------
// Discard worktree
// ---------------------------------------------------------------------------

export interface IDiscardWorktreeInput {
  readonly worktree: IWorktreeInfo;
  readonly projectDir: string;
}

/**
 * Remove a candidate worktree and its branch.
 */
export function discardWorktree(input: IDiscardWorktreeInput): void {
  const { worktree, projectDir } = input;

  // Remove worktree
  execSync(`git worktree remove "${worktree.path}" 2>/dev/null; rm -rf "${worktree.path}"`, {
    cwd: projectDir,
    stdio: "pipe",
  });

  // Delete branch
  execSync(`git branch -D "${worktree.branch}" 2>/dev/null`, {
    cwd: projectDir,
    stdio: "pipe",
  });
}

export interface IApplyApprovedChangesInput {
  readonly worktree: IWorktreeInfo;
  readonly projectDir: string;
  readonly changes: readonly ICandidateChange[];
}

export async function applyApprovedChanges(input: IApplyApprovedChangesInput): Promise<void> {
  const { worktree, projectDir, changes } = input;

  for (const change of changes) {
    const relPath = toProjectRelativePath(change.filePath, projectDir);
    const sourcePath = resolve(worktree.path, relPath);
    const targetPath = resolve(projectDir, relPath);

    if (change.changeType === "delete") {
      await rm(targetPath, { force: true, recursive: false });
      continue;
    }

    const content = await readFile(sourcePath, "utf8");
    await mkdir(dirname(targetPath), { recursive: true });
    await writeFile(targetPath, content, "utf8");
  }
}

// ---------------------------------------------------------------------------
// Diff
// ---------------------------------------------------------------------------

/**
 * Get the git diff for a worktree (against its initial state).
 */
export function getWorktreeDiff(worktreePath: string): string {
  try {
    return execSync("git diff HEAD", { cwd: worktreePath, stdio: "pipe" }).toString();
  } catch {
    return "";
  }
}

function toProjectRelativePath(filePath: string, projectDir: string): string {
  if (!isAbsolute(filePath)) return filePath;
  const relativePath = relative(projectDir, filePath);
  if (relativePath.startsWith("..")) {
    throw new Error(`Absolute path is outside the project root: ${filePath}`);
  }
  return relativePath;
}
