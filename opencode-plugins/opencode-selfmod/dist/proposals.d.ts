import type { IRiskThreshold } from "./config.js";
import type { IFileChange } from "./policy.js";
export interface IProposal {
    readonly id: string;
    readonly title: string;
    readonly description: string;
    readonly changes: readonly IFileChange[];
    readonly riskLevel: IRiskThreshold;
    readonly createdAt: number;
}
export interface ICandidateChange {
    readonly filePath: string;
    readonly changeType: "add" | "modify" | "delete" | "rename";
    readonly newContent?: string;
    readonly oldContent?: string;
}
export declare function createProposal(params: {
    title: string;
    description: string;
    changes: readonly ICandidateChange[];
    riskLevel: IRiskThreshold;
}): IProposal;
export declare function getProposal(id: string): IProposal | undefined;
export declare function listProposals(): readonly IProposal[];
export declare function removeProposal(id: string): boolean;
export declare function clearProposals(): void;
//# sourceMappingURL=proposals.d.ts.map