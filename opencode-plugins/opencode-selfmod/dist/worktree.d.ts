import type { ICandidateChange } from "./proposals.js";
import type { IPluginConfig } from "./config.js";
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
export interface ICreateWorktreeInput {
    readonly projectDir: string;
    readonly proposalId: string;
    readonly config: IPluginConfig;
}
/**
 * Create an isolated git worktree + branch for testing candidate changes.
 * Returns the worktree info or throws if creation fails.
 */
export declare function createCandidateWorktree(input: ICreateWorktreeInput): IWorktreeInfo;
export interface IApplyChangesInput {
    readonly worktree: IWorktreeInfo;
    readonly changes: readonly ICandidateChange[];
}
/**
 * Apply candidate changes to the worktree. Writes files and stages them.
 */
export declare function applyCandidateChanges(input: IApplyChangesInput): Promise<void>;
export interface IDiscardWorktreeInput {
    readonly worktree: IWorktreeInfo;
    readonly projectDir: string;
}
/**
 * Remove a candidate worktree and its branch.
 */
export declare function discardWorktree(input: IDiscardWorktreeInput): void;
export interface IApplyApprovedChangesInput {
    readonly worktree: IWorktreeInfo;
    readonly projectDir: string;
    readonly changes: readonly ICandidateChange[];
}
export declare function applyApprovedChanges(input: IApplyApprovedChangesInput): Promise<void>;
/**
 * Get the git diff for a worktree (against its initial state).
 */
export declare function getWorktreeDiff(worktreePath: string): string;
//# sourceMappingURL=worktree.d.ts.map