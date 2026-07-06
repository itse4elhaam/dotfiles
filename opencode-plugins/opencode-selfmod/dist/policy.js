export const DEFAULT_PROTECTED_PATHS = [
    // -- CRITICAL: never auto-approve, always gate ---------------------------
    { glob: "**/.git/**", risk: "critical", reason: "Git metadata is never modified" },
    { glob: "**/.gitignore", risk: "critical", reason: "Gitignore affects repo boundaries" },
    { glob: "**/secrets*", risk: "critical", reason: "Secrets file" },
    { glob: "**/.env*", risk: "critical", reason: "Environment variable files" },
    { glob: "**/*.pem", risk: "critical", reason: "Private key / certificate" },
    { glob: "**/*.key", risk: "critical", reason: "Key file" },
    // -- DANGEROUS: requires moderate+ threshold -----------------------------
    { glob: "**/package-lock.json", risk: "dangerous", reason: "Package lock — change only with intent" },
    { glob: "**/yarn.lock", risk: "dangerous", reason: "Package lock — change only with intent" },
    { glob: "**/pnpm-lock.yaml", risk: "dangerous", reason: "Package lock — change only with intent" },
    { glob: "**/bun.lock", risk: "dangerous", reason: "Package lock — change only with intent" },
    { glob: "**/.github/workflows/**", risk: "dangerous", reason: "CI/CD config" },
    { glob: "**/.circleci/**", risk: "dangerous", reason: "CI/CD config" },
    { glob: "**/Dockerfile*", risk: "dangerous", reason: "Container build definition" },
    // -- MODERATE: guarded by default threshold ------------------------------
    { glob: "**/.bashrc", risk: "moderate", reason: "Shell rc file" },
    { glob: "**/.zshrc", risk: "moderate", reason: "Shell rc file" },
    { glob: "**/.profile", risk: "moderate", reason: "Shell rc file" },
    { glob: "**/.config/opencode/**", risk: "moderate", reason: "OpenCode config files" },
    { glob: "**/.opencode/**", risk: "moderate", reason: "OpenCode project-local config" },
    { glob: "**/opencode-selfmod/**", risk: "moderate", reason: "Self-mod plugin source" },
    { glob: "**/src/**", risk: "moderate", reason: "Plugin source code" },
];
// ---------------------------------------------------------------------------
// Glob matching helpers (simple — supports * and **)
// ---------------------------------------------------------------------------
/**
 * Convert a glob pattern to a RegExp.
 * Supports `**`, `*`, and literal characters.
 */
function globToRegExp(glob) {
    let pattern = "";
    let i = 0;
    while (i < glob.length) {
        const char = glob[i];
        if (char === "*" && glob[i + 1] === "*" && glob[i + 2] === "/") {
            pattern += "(?:.+/)*";
            i += 3;
        }
        else if (char === "*" && glob[i + 1] === "*" && glob[i + 2] === undefined) {
            pattern += ".+";
            i += 2;
        }
        else if (char === "*") {
            pattern += "[^/]*";
            i += 1;
        }
        else if (char === "?") {
            pattern += "[^/]";
            i += 1;
        }
        else {
            pattern += char.replace(/[.+^${}()|[\]\\]/g, "\\$&");
            i += 1;
        }
    }
    return new RegExp(`^${pattern}$`, "i");
}
function matchesGlob(filePath, glob) {
    // Normalise path separators
    const normalised = filePath.replace(/\\/g, "/");
    const re = globToRegExp(glob);
    return re.test(normalised) || re.test(normalised.replace(/\/$/, ""));
}
// ---------------------------------------------------------------------------
// Risk classification
// ---------------------------------------------------------------------------
/**
 * Classify the risk level of a single file change.
 */
export function classifyRisk(change, config) {
    const overrides = buildOverrideSet(config.protectedPathOverrides);
    const entries = applyOverrides(DEFAULT_PROTECTED_PATHS, overrides);
    for (const entry of entries) {
        if (matchesGlob(change.filePath, entry.glob)) {
            return { risk: entry.risk, matchedEntry: entry };
        }
    }
    // Default classification by change type
    if (change.changeType === "delete") {
        return { risk: "dangerous" };
    }
    if (change.changeType === "modify" && change.filePath.endsWith(".json")) {
        return { risk: "moderate" };
    }
    if (change.changeType === "add" && change.filePath.endsWith(".md")) {
        return { risk: "safe" };
    }
    return { risk: "moderate" };
}
/**
 * Evaluate whether a set of changes passes the policy gate.
 * Returns one combined decision. For MVP all changes must pass.
 */
export function evaluatePolicy(input) {
    const { changes, config } = input;
    if (config.riskThreshold === "off") {
        return {
            allowed: false,
            reason: "Self-modification is disabled (riskThreshold: off)",
            riskLevel: "off",
            findings: [],
        };
    }
    const thresholdRank = riskRank(config.riskThreshold);
    const findings = [];
    for (const change of changes) {
        const { risk, matchedEntry } = classifyRisk(change, config);
        const changeRank = riskRank(risk);
        const suspiciousContent = findSuspiciousContent(change);
        findings.push(`${change.changeType.toUpperCase()} ${change.filePath}: ${risk}${matchedEntry ? ` (${matchedEntry.reason})` : ""}`);
        if (suspiciousContent.length > 0) {
            return {
                allowed: false,
                reason: `Change to "${change.filePath}" contains blocked validation/safety bypass markers: ${suspiciousContent.join(", ")}`,
                riskLevel: "critical",
                matchedRule: "blocked-content",
                findings,
            };
        }
        if (changeRank > thresholdRank) {
            return {
                allowed: false,
                reason: `Change to "${change.filePath}" classified as "${risk}" which exceeds threshold "${config.riskThreshold}"`,
                riskLevel: risk,
                matchedRule: matchedEntry?.glob,
                findings,
            };
        }
    }
    // All changes within threshold
    const maxRisk = changes.reduce((highest, c) => {
        const { risk } = classifyRisk(c, config);
        return riskRank(risk) > riskRank(highest) ? risk : highest;
    }, "safe");
    return {
        allowed: true,
        reason: `All ${changes.length} change(s) within threshold "${config.riskThreshold}"`,
        riskLevel: maxRisk,
        findings,
    };
}
// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------
function riskRank(level) {
    const ranks = {
        safe: 0,
        moderate: 1,
        dangerous: 2,
        critical: 3,
        off: 99,
    };
    return ranks[level] ?? 1;
}
function buildOverrideSet(overrides) {
    return new Set(overrides);
}
function applyOverrides(defaults, overrides) {
    if (overrides.size === 0)
        return defaults;
    const removals = new Set();
    const additions = [];
    for (const entry of overrides) {
        if (entry.startsWith("!")) {
            removals.add(entry.slice(1));
        }
        else {
            additions.push({ glob: entry, risk: "moderate", reason: "User-defined override" });
        }
    }
    const filtered = defaults.filter((d) => !removals.has(d.glob));
    return [...filtered, ...additions];
}
function findSuspiciousContent(change) {
    const content = change.newContent ?? "";
    const blocked = [
        "@ts-ignore",
        "@ts-expect-error",
        "eslint-disable",
        "describe.skip",
        "it.skip",
        "test.skip",
        "shellcheck disable",
    ];
    return blocked.filter((marker) => content.includes(marker));
}
//# sourceMappingURL=policy.js.map