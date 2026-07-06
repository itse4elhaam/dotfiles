// ---------------------------------------------------------------------------
// Proposal store (in-memory for MVP)
// ---------------------------------------------------------------------------
const proposals = new Map();
let nextId = 1;
function generateId() {
    const id = nextId;
    nextId += 1;
    return `selfmod_${Date.now()}_${id}`;
}
export function createProposal(params) {
    const proposal = {
        id: generateId(),
        title: params.title,
        description: params.description,
        changes: params.changes,
        riskLevel: params.riskLevel,
        createdAt: Date.now(),
    };
    proposals.set(proposal.id, proposal);
    return proposal;
}
export function getProposal(id) {
    return proposals.get(id);
}
export function listProposals() {
    return [...proposals.values()];
}
export function removeProposal(id) {
    return proposals.delete(id);
}
export function clearProposals() {
    proposals.clear();
}
//# sourceMappingURL=proposals.js.map