import { readFile, readdir } from "node:fs/promises";
import { resolve, dirname, join } from "node:path";
import type { IPluginConfig } from "./config.js";

// ---------------------------------------------------------------------------
// Context pack data types
// ---------------------------------------------------------------------------

export interface IContextFile {
  readonly path: string;
  readonly content: string;
}

export interface IContextPack {
  /** The project root directory. */
  readonly projectDir: string;
  /** Parsed content of opencode.json (server config). */
  readonly opencodeConfig: IContextFile | null;
  /** Parsed content of tui.json (TUI config) if it exists. */
  readonly tuiConfig: IContextFile | null;
  /** All agent definition files (*.md in agent/). */
  readonly agents: readonly IContextFile[];
  /** All command definition files (*.md in command/). */
  readonly commands: readonly IContextFile[];
  /** All custom tool definitions. */
  readonly customTools: readonly IContextFile[];
  /** All context files (in context/). */
  readonly contextFiles: readonly IContextFile[];
  /** Plugin config JSON files (plugin configs). */
  readonly pluginConfigs: readonly IContextFile[];
  /** package.json files found in OpenCode config directories. */
  readonly packageMeta: readonly IContextFile[];
  /** The plugin's own resolved config. */
  readonly pluginConfig: IPluginConfig;
}

export interface IContextSummary {
  readonly markdown: string;
  readonly totalFiles: number;
  readonly truncated: boolean;
}

// ---------------------------------------------------------------------------
// Standard locations to scan
// ---------------------------------------------------------------------------

/**
 * Directories to scan for OpenCode config artifacts, relative to the
 * project root or the user's home config directory.
 */
const CONFIG_DIRS = [
  ".config/opencode",
  ".opencode",
] as const;

/**
 * Sub-paths within each config directory.
 */
const SUB_PATHS = {
  agents: "agent",
  commands: "command",
  tools: "tool",
  context: "context",
  plugins: "plugins",
  plugin: "plugin",
} as const;

// ---------------------------------------------------------------------------
// Context pack generation
// ---------------------------------------------------------------------------

async function readFileSafe(filePath: string): Promise<string | null> {
  try {
    return await readFile(filePath, "utf8");
  } catch {
    return null;
  }
}

async function readDirSafe(dirPath: string): Promise<readonly string[]> {
  try {
    const entries = await readdir(dirPath, { withFileTypes: true });
    return entries
      .filter((e) => e.isFile())
      .map((e) => e.name);
  } catch {
    return [];
  }
}

async function collectFiles(
  baseDir: string,
  subPath: string,
): Promise<readonly IContextFile[]> {
  const dir = resolve(baseDir, subPath);
  const names = await readDirSafe(dir);
  const results: IContextFile[] = [];

  for (const name of names) {
    const filePath = join(dir, name);
    const content = await readFileSafe(filePath);
    if (content !== null) {
      results.push({ path: filePath, content });
    }
  }

  return results;
}

async function collectFromAllDirs(
  projectDir: string,
  homeConfigDir: string | undefined,
  subPath: string,
): Promise<readonly IContextFile[]> {
  const results: IContextFile[] = [];

  for (const rel of CONFIG_DIRS) {
    const candidate = resolve(projectDir, rel, subPath);
    const files = await collectFiles(dirname(candidate), subPath);
    results.push(...files);
  }

  if (homeConfigDir && homeConfigDir !== projectDir) {
    for (const rel of CONFIG_DIRS) {
      const candidate = resolve(homeConfigDir, rel, subPath);
      const files = await collectFiles(dirname(candidate), subPath);
      results.push(...files);
    }
  }

  return results;
}

async function findConfigFile(
  projectDir: string,
  homeConfigDir: string | undefined,
  fileName: string,
): Promise<IContextFile | null> {
  const candidates: string[] = [];

  for (const rel of CONFIG_DIRS) {
    candidates.push(resolve(projectDir, rel, fileName));
  }
  if (homeConfigDir && homeConfigDir !== projectDir) {
    for (const rel of CONFIG_DIRS) {
      candidates.push(resolve(homeConfigDir, rel, fileName));
    }
  }

  for (const candidate of candidates) {
    const content = await readFileSafe(candidate);
    if (content !== null) {
      return { path: candidate, content };
    }
  }

  return null;
}

async function findPackageFiles(
  projectDir: string,
  homeConfigDir: string | undefined,
): Promise<readonly IContextFile[]> {
  const results: IContextFile[] = [];
  const candidates: string[] = [];

  for (const rel of CONFIG_DIRS) {
    candidates.push(resolve(projectDir, rel, "package.json"));
  }
  if (homeConfigDir && homeConfigDir !== projectDir) {
    for (const rel of CONFIG_DIRS) {
      candidates.push(resolve(homeConfigDir, rel, "package.json"));
    }
  }

  for (const candidate of candidates) {
    const content = await readFileSafe(candidate);
    if (content !== null) {
      results.push({ path: candidate, content });
    }
  }

  return results;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export interface IGenerateContextPackInput {
  readonly projectDir: string;
  readonly homeConfigDir?: string;
  readonly pluginConfig: IPluginConfig;
}

/**
 * Gather enough OpenCode-specific context to inform self-modification
 * proposals. Reads all config, agents, commands, tools, and plugin configs
 * from standard locations.
 */
export async function generateContextPack(
  input: IGenerateContextPackInput,
): Promise<IContextPack> {
  const { projectDir, homeConfigDir, pluginConfig } = input;

  const [opencodeConfig, tuiConfig, agents, commands, customTools, contextFiles, pluginConfigs, packageMeta] =
    await Promise.all([
      findConfigFile(projectDir, homeConfigDir, "opencode.json"),
      findConfigFile(projectDir, homeConfigDir, "tui.json"),
      collectFromAllDirs(projectDir, homeConfigDir, SUB_PATHS.agents),
      collectFromAllDirs(projectDir, homeConfigDir, SUB_PATHS.commands),
      collectFromAllDirs(projectDir, homeConfigDir, SUB_PATHS.tools),
      collectFromAllDirs(projectDir, homeConfigDir, SUB_PATHS.context),
      collectFromAllDirs(projectDir, homeConfigDir, SUB_PATHS.plugins),
      findPackageFiles(projectDir, homeConfigDir),
    ]);

  return {
    projectDir,
    opencodeConfig,
    tuiConfig,
    agents,
    commands,
    customTools,
    contextFiles,
    pluginConfigs,
    packageMeta,
    pluginConfig,
  };
}

export function formatContextPack(pack: IContextPack): IContextSummary {
  const sections: string[] = [];
  let totalFiles = 0;

  sections.push("# OpenCode Self-Modification Context Pack");
  sections.push(`Project: ${pack.projectDir}`);
  sections.push(`Self-modifier model: ${pack.pluginConfig.model}`);
  sections.push(`Risk threshold: ${pack.pluginConfig.riskThreshold}`);
  sections.push("");
  sections.push("## Safety Contract");
  sections.push("- Never mutate active OpenCode config directly.");
  sections.push("- Always propose, classify risk, create a candidate worktree, validate, diff, then require explicit approval.");
  sections.push("- The improvement scope includes OpenCode config, agent, command, tool, plugin, context, and plugin config files.");
  sections.push("");

  const addFile = (label: string, file: IContextFile | null): void => {
    if (!file) return;
    totalFiles += 1;
    sections.push(`## ${label}: ${file.path}`);
    sections.push("```text");
    sections.push(truncate(redact(file.content), pack.pluginConfig.maxFileChars));
    sections.push("```");
  };

  const addFiles = (label: string, files: readonly IContextFile[]): void => {
    if (files.length === 0) return;
    sections.push(`## ${label} (${files.length})`);
    for (const file of files) {
      totalFiles += 1;
      sections.push(`### ${file.path}`);
      sections.push("```text");
      sections.push(truncate(redact(file.content), pack.pluginConfig.maxFileChars));
      sections.push("```");
    }
  };

  addFile("opencode.json", pack.opencodeConfig);
  addFile("tui.json", pack.tuiConfig);
  addFiles("Agents", pack.agents);
  addFiles("Commands", pack.commands);
  addFiles("Custom tools", pack.customTools);
  addFiles("Context files", pack.contextFiles);
  addFiles("Plugin configs", pack.pluginConfigs);
  addFiles("Package metadata", pack.packageMeta);

  const raw = sections.join("\n");
  const markdown = truncate(raw, pack.pluginConfig.maxContextChars);

  return {
    markdown,
    totalFiles,
    truncated: markdown.length < raw.length,
  };
}

function truncate(value: string, maxChars: number): string {
  if (value.length <= maxChars) return value;
  return `${value.slice(0, maxChars)}\n...[truncated ${value.length - maxChars} chars]`;
}

function redact(value: string): string {
  return value
    .replace(/(api[_-]?key\s*[:=]\s*)[^\s"']+/gi, "$1[REDACTED]")
    .replace(/(token\s*[:=]\s*)[^\s"']+/gi, "$1[REDACTED]")
    .replace(/(password\s*[:=]\s*)[^\s"']+/gi, "$1[REDACTED]")
    .replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/g, "Bearer [REDACTED]");
}
