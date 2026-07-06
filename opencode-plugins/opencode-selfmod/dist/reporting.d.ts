import type { IFileChange } from "./policy.js";
import type { IRiskThreshold } from "./config.js";
import type { IWorktreeInfo } from "./worktree.js";
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
export interface IGenerateDiffReportInput {
    readonly proposalId: string;
    readonly worktree: IWorktreeInfo;
    readonly changes: readonly IFileChange[];
    readonly riskLevel: IRiskThreshold;
}
/**
 * Generate a structured diff report from a candidate worktree.
 */
export declare function generateDiffReport(input: IGenerateDiffReportInput): IDiffReport;
//# sourceMappingURL=reporting.d.ts.map