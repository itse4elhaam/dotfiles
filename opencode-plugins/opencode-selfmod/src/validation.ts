import { execSync } from "node:child_process";
import type { IWorktreeInfo } from "./worktree.js";

// ---------------------------------------------------------------------------
// Validation types
// ---------------------------------------------------------------------------

export interface IValidationResult {
  /** True if all validation checks passed. */
  readonly passed: boolean;
  /** Error messages from failed checks. */
  readonly errors: readonly string[];
  /** Warning messages. */
  readonly warnings: readonly string[];
  /** Raw stdout from the last validation command. */
  readonly output: string;
}

// ---------------------------------------------------------------------------
// Validation runner
// ---------------------------------------------------------------------------

export interface IRunValidationInput {
  readonly worktree: IWorktreeInfo;
  readonly commands: readonly string[];
}

/**
 * Execute validation commands inside the candidate worktree.
 * Returns a combined result.
 */
export function runValidation(input: IRunValidationInput): IValidationResult {
  const { worktree, commands } = input;

  if (commands.length === 0) {
    return {
      passed: true,
      errors: [],
      warnings: ["No validation commands configured — skipping"],
      output: "",
    };
  }

  const errors: string[] = [];
  const warnings: string[] = [];
  let lastOutput = "";

  for (const cmd of commands) {
    try {
      const stdout = execSync(cmd, {
        cwd: worktree.path,
        stdio: "pipe",
        timeout: 60_000,
      }).toString();
      lastOutput += stdout;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      errors.push(`Command "${cmd}" failed: ${message}`);
    }
  }

  return {
    passed: errors.length === 0,
    errors,
    warnings,
    output: lastOutput,
  };
}
