import type { IPluginConfig, IRiskThreshold } from "./config.js";
export type IChangeType = "add" | "modify" | "delete" | "rename";
export interface IFileChange {
    /** Absolute path to the file being changed. */
    readonly filePath: string;
    /** Type of operation. */
    readonly changeType: IChangeType;
    /** New content (absent for pure deletions). */
    readonly newContent?: string;
    /** Previous content (absent for pure additions). */
    readonly oldContent?: string;
}
export interface IPolicyDecision {
    /** Whether the change is allowed. */
    readonly allowed: boolean;
    /** Human-readable reason for the decision. */
    readonly reason: string;
    /** Classified risk level. */
    readonly riskLevel: IRiskThreshold;
    /** Which policy rule triggered. */
    readonly matchedRule?: string;
    /** Per-file risk notes for review and diff reports. */
    readonly findings: readonly string[];
}
export interface IProtectedPathEntry {
    readonly glob: string;
    readonly risk: IRiskThreshold;
    readonly reason: string;
}
export declare const DEFAULT_PROTECTED_PATHS: readonly IProtectedPathEntry[];
/**
 * Classify the risk level of a single file change.
 */
export declare function classifyRisk(change: IFileChange, config: IPluginConfig): {
    risk: IRiskThreshold;
    matchedEntry?: IProtectedPathEntry;
};
export interface IPolicyInput {
    readonly changes: readonly IFileChange[];
    readonly config: IPluginConfig;
}
/**
 * Evaluate whether a set of changes passes the policy gate.
 * Returns one combined decision. For MVP all changes must pass.
 */
export declare function evaluatePolicy(input: IPolicyInput): IPolicyDecision;
//# sourceMappingURL=policy.d.ts.map