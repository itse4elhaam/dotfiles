import { z } from "zod";
// ---------------------------------------------------------------------------
// Plugin config schema — loaded from plugin options in opencode.json
// ---------------------------------------------------------------------------
/**
 * Risk threshold enum.
 * - "safe":        Only allow no-risk changes (e.g. comments, whitespace).
 * - "moderate":    Allow low-risk changes (e.g. new non-sensitive files).
 * - "dangerous":   Allow moderate-risk changes (e.g. code modifications).
 * - "critical":    Allow all changes including config deletions (requires
 *                  explicit user confirmation regardless).
 * - "off":         Disable self-modification entirely.
 */
export const RiskThreshold = z.enum([
    "safe",
    "moderate",
    "dangerous",
    "critical",
    "off",
]);
// ---------------------------------------------------------------------------
// PluginConfig
// ---------------------------------------------------------------------------
export const PluginConfig = z.object({
    /**
     * Model identifier used by the self-modifier subagent.
     * Format: `"providerId/modelId"` (e.g. `"opencode-go/deepseek-v4-flash"`).
     * The subagent definition references this key so the model can be changed
     * without editing the agent file.
     */
    model: z.string().default("opencode-go/deepseek-v4-flash"),
    /**
     * Maximum risk level the plugin will act on without escalation.
     * Changes classified above this threshold will be rejected.
     */
    riskThreshold: RiskThreshold.default("moderate"),
    /**
     * Glob patterns whose matching changes are always auto-approved
     * when within the risk threshold. Use sparingly.
     * Example: `["opencode-selfmod/dist/**"]`
     */
    autoApprovalPatterns: z.array(z.string()).default([]),
    /**
     * Override the built-in protected path set. This is a merge: entries
     * prefixed with `!` remove a built-in default; other entries add to it.
     */
    protectedPathOverrides: z.array(z.string()).default([]),
    /**
     * Directory for candidate worktrees. Relative paths are resolved against
     * the plugin's project directory. Defaults to a `.selfmod` directory
     * inside the project.
     */
    workDir: z.string().default(".selfmod/worktrees"),
    /**
     * Validation commands to run against candidate changes.
     * Each entry is a shell command string.
     * Defaults: `["tsc --noEmit"]` if a tsconfig exists.
     */
    validationCommands: z.array(z.string()).default([]),
    /**
     * Directory that contains the user's global OpenCode config. Defaults to
     * `$HOME` so the context pack can inspect `~/.config/opencode` in addition
     * to project-local `.opencode` files.
     */
    homeConfigDir: z.string().optional(),
    /**
     * Maximum number of characters returned by `selfmod_context`.
     */
    maxContextChars: z.number().int().positive().default(24_000),
    /**
     * Maximum number of characters included per context file.
     */
    maxFileChars: z.number().int().positive().default(4_000),
    /**
     * If true, the plugin logs verbose debug output to stderr.
     */
    debug: z.boolean().default(false),
});
// ---------------------------------------------------------------------------
// Default config
// ---------------------------------------------------------------------------
export const DEFAULT_CONFIG = {
    model: "opencode-go/deepseek-v4-flash",
    riskThreshold: "moderate",
    autoApprovalPatterns: [],
    protectedPathOverrides: [],
    workDir: ".selfmod/worktrees",
    validationCommands: [],
    homeConfigDir: undefined,
    maxContextChars: 24_000,
    maxFileChars: 4_000,
    debug: false,
};
/**
 * Merge partial user-provided options with defaults.
 */
export function resolveConfig(raw) {
    const parsed = PluginConfig.safeParse(raw ?? {});
    if (!parsed.success) {
        console.error("[opencode-selfmod] Invalid config, using defaults:", parsed.error.message);
        return DEFAULT_CONFIG;
    }
    return parsed.data;
}
//# sourceMappingURL=config.js.map