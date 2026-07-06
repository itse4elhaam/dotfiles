import { execSync } from "node:child_process";
/**
 * Execute validation commands inside the candidate worktree.
 * Returns a combined result.
 */
export function runValidation(input) {
    const { worktree, commands } = input;
    if (commands.length === 0) {
        return {
            passed: true,
            errors: [],
            warnings: ["No validation commands configured — skipping"],
            output: "",
        };
    }
    const errors = [];
    const warnings = [];
    let lastOutput = "";
    for (const cmd of commands) {
        try {
            const stdout = execSync(cmd, {
                cwd: worktree.path,
                stdio: "pipe",
                timeout: 60_000,
            }).toString();
            lastOutput += stdout;
        }
        catch (error) {
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
//# sourceMappingURL=validation.js.map