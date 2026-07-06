import type { IPluginConfig } from "./config.js";
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
export declare function generateContextPack(input: IGenerateContextPackInput): Promise<IContextPack>;
export declare function formatContextPack(pack: IContextPack): IContextSummary;
//# sourceMappingURL=context-pack.d.ts.map