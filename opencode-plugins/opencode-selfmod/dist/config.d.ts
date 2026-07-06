import { z } from "zod";
/**
 * Risk threshold enum.
 * - "safe":        Only allow no-risk changes (e.g. comments, whitespace).
 * - "moderate":    Allow low-risk changes (e.g. new non-sensitive files).
 * - "dangerous":   Allow moderate-risk changes (e.g. code modifications).
 * - "critical":    Allow all changes including config deletions (requires
 *                  explicit user confirmation regardless).
 * - "off":         Disable self-modification entirely.
 */
export declare const RiskThreshold: z.ZodEnum<{
    safe: "safe";
    moderate: "moderate";
    dangerous: "dangerous";
    critical: "critical";
    off: "off";
}>;
export type IRiskThreshold = z.infer<typeof RiskThreshold>;
export declare const PluginConfig: z.ZodObject<{
    model: z.ZodDefault<z.ZodString>;
    riskThreshold: z.ZodDefault<z.ZodEnum<{
        safe: "safe";
        moderate: "moderate";
        dangerous: "dangerous";
        critical: "critical";
        off: "off";
    }>>;
    autoApprovalPatterns: z.ZodDefault<z.ZodArray<z.ZodString>>;
    protectedPathOverrides: z.ZodDefault<z.ZodArray<z.ZodString>>;
    workDir: z.ZodDefault<z.ZodString>;
    validationCommands: z.ZodDefault<z.ZodArray<z.ZodString>>;
    homeConfigDir: z.ZodOptional<z.ZodString>;
    maxContextChars: z.ZodDefault<z.ZodNumber>;
    maxFileChars: z.ZodDefault<z.ZodNumber>;
    debug: z.ZodDefault<z.ZodBoolean>;
}, z.core.$strip>;
export type IPluginConfig = z.infer<typeof PluginConfig>;
export declare const DEFAULT_CONFIG: IPluginConfig;
/**
 * Merge partial user-provided options with defaults.
 */
export declare function resolveConfig(raw: Record<string, unknown> | undefined): IPluginConfig;
//# sourceMappingURL=config.d.ts.map