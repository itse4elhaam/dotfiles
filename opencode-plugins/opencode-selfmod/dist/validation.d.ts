import type { IWorktreeInfo } from "./worktree.js";
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
export interface IRunValidationInput {
    readonly worktree: IWorktreeInfo;
    readonly commands: readonly string[];
}
/**
 * Execute validation commands inside the candidate worktree.
 * Returns a combined result.
 */
export declare function runValidation(input: IRunValidationInput): IValidationResult;
//# sourceMappingURL=validation.d.ts.map