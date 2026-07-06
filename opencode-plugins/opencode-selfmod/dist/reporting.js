import { getWorktreeDiff } from "./worktree.js";
/**
 * Generate a structured diff report from a candidate worktree.
 */
export function generateDiffReport(input) {
    const { proposalId, worktree, changes, riskLevel } = input;
    const rawDiff = getWorktreeDiff(worktree.path);
    const entries = changes.map((change) => ({
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
function formatChangeType(type) {
    switch (type) {
        case "add": return "[A]";
        case "modify": return "[M]";
        case "delete": return "[D]";
        case "rename": return "[R]";
    }
}
/**
 * Extract the diff hunk for a specific file path from the raw diff output.
 */
function extractHunk(rawDiff, filePath) {
    const lines = rawDiff.split("\n");
    const result = [];
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
//# sourceMappingURL=reporting.js.map