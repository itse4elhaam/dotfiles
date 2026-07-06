import type { IRiskThreshold } from "./config.js";
import type { IFileChange } from "./policy.js";

// ---------------------------------------------------------------------------
// Proposal data types
// ---------------------------------------------------------------------------

export interface IProposal {
  readonly id: string;
  readonly title: string;
  readonly description: string;
  readonly changes: readonly IFileChange[];
  readonly riskLevel: IRiskThreshold;
  readonly createdAt: number; // unix ms
}

export interface ICandidateChange {
  readonly filePath: string;
  readonly changeType: "add" | "modify" | "delete" | "rename";
  readonly newContent?: string;
  readonly oldContent?: string;
}

// ---------------------------------------------------------------------------
// Proposal store (in-memory for MVP)
// ---------------------------------------------------------------------------

const proposals = new Map<string, IProposal>();

let nextId = 1;

function generateId(): string {
  const id = nextId;
  nextId += 1;
  return `selfmod_${Date.now()}_${id}`;
}

export function createProposal(params: {
  title: string;
  description: string;
  changes: readonly ICandidateChange[];
  riskLevel: IRiskThreshold;
}): IProposal {
  const proposal: IProposal = {
    id: generateId(),
    title: params.title,
    description: params.description,
    changes: params.changes as readonly IFileChange[],
    riskLevel: params.riskLevel,
    createdAt: Date.now(),
  };
  proposals.set(proposal.id, proposal);
  return proposal;
}

export function getProposal(id: string): IProposal | undefined {
  return proposals.get(id);
}

export function listProposals(): readonly IProposal[] {
  return [...proposals.values()];
}

export function removeProposal(id: string): boolean {
  return proposals.delete(id);
}

export function clearProposals(): void {
  proposals.clear();
}
