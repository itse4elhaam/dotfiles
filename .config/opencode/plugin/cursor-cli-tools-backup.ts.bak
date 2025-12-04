import { type Plugin, tool } from "@opencode-ai/plugin";
import * as fs from "node:fs";
import * as path from "node:path";

/**
 * Cursor CLI Plugin for OpenCode
 * 
 * Integrates Cursor AI models (including Auto mode) into OpenCode via cursor-agent CLI.
 * Supports streaming responses and provides access to all Cursor models.
 */

interface IStreamEvent {
	type: string;
	subtype?: string;
	message?: {
		role: string;
		content: Array<{ type: string; text: string }>;
	};
	tool_call?: unknown;
	call_id?: string;
	duration_ms?: number;
	duration_api_ms?: number;
	is_error?: boolean;
	result?: string;
	session_id?: string;
	request_id?: string;
	model?: string;
}

interface ICursorModelsResponse {
	models: string[];
}

// Verbose logging utility
const VERBOSE = process.env.OPENCODE_CURSOR_VERBOSE === "true";
let VERBOSE_LOG_PATH: string | null = null;

function initVerboseLog(directory: string): void {
	if (VERBOSE) {
		VERBOSE_LOG_PATH = path.join(directory, ".opencode", "cursor-verbose.log");
		const dir = path.dirname(VERBOSE_LOG_PATH);
		if (!fs.existsSync(dir)) {
			fs.mkdirSync(dir, { recursive: true });
		}
		// Clear log on init
		fs.writeFileSync(VERBOSE_LOG_PATH, `=== Cursor Plugin Verbose Log ===\n`);
	}
}

function verboseLog(message: string, data?: unknown): void {
	if (VERBOSE && VERBOSE_LOG_PATH) {
		const timestamp = new Date().toISOString();
		const logMessage = `[${timestamp}] ${message}\n`;
		const dataMessage = data ? `${JSON.stringify(data, null, 2)}\n` : "";
		
		try {
			fs.appendFileSync(VERBOSE_LOG_PATH, logMessage + dataMessage);
		} catch (error) {
			// Silent fail - don't break plugin if logging fails
		}
	}
}

// Error logging utility
class ErrorLogger {
	private logPath: string;

	constructor(directory: string) {
		this.logPath = path.join(directory, ".opencode", "cursor-errors.log");
		this.ensureLogDir();
	}

	private ensureLogDir(): void {
		const dir = path.dirname(this.logPath);
		if (!fs.existsSync(dir)) {
			fs.mkdirSync(dir, { recursive: true });
		}
	}

	log(error: Error | string, context?: string): void {
		const timestamp = new Date().toISOString();
		const message =
			error instanceof Error ? error.message : error;
		const stack = error instanceof Error ? error.stack : "";

		const logEntry = `[${timestamp}] ${context ? `[${context}] ` : ""}${message}\n${stack ? `${stack}\n` : ""}\n`;

		try {
			fs.appendFileSync(this.logPath, logEntry);
		} catch (writeError) {
			console.error("Failed to write to error log:", writeError);
		}
	}

	getUserMessage(error: Error | string): string {
		const message =
			error instanceof Error ? error.message : error;

		// Friendly error messages
		if (
			message.includes("CURSOR_API_KEY") ||
			message.includes("not authenticated")
		) {
			return "⚠️  Cursor authentication required. Run 'cursor-agent' to login or set CURSOR_API_KEY environment variable.";
		}

		if (message.includes("command not found")) {
			return "⚠️  Cursor CLI not installed. Install with: curl https://cursor.com/install -fsS | bash";
		}

		if (
			message.includes("resource_exhausted") ||
			message.includes("not available for free users") ||
			message.includes("upgrade to Pro")
		) {
			return "⚠️  Cursor Pro subscription required. The Cloud Agent API is only available for Pro users. Upgrade at https://www.cursor.com/pricing";
		}

		if (message.includes("rate limit")) {
			return "⚠️  Cursor API rate limit reached. Please wait a moment and try again.";
		}

		if (message.includes("subscription")) {
			return "⚠️  Cursor subscription required. Please upgrade at https://cursor.com/settings";
		}

		return `⚠️  Error: ${message.split("\n")[0]}. Check .opencode/cursor-errors.log for details.`;
	}
}

// Static fallback models (in case API fetch fails)
const STATIC_CURSOR_MODELS = [
	"auto",
	"claude-4.5-opus-high-thinking",
	"claude-4.5-sonnet-thinking",
	"gpt-5.1-codex",
	"gpt-5.1-codex-high",
	"gemini-3-pro",
] as const;

// Toggle state management
class ToggleState {
	private statePath: string;
	private enabled: boolean;

	constructor(directory: string) {
		this.statePath = path.join(directory, ".opencode", "cursor-toggle.json");
		this.enabled = this.load();
	}

	private load(): boolean {
		try {
			if (fs.existsSync(this.statePath)) {
				const data = JSON.parse(fs.readFileSync(this.statePath, "utf-8"));
				verboseLog("ToggleState: Loaded state", data);
				return data.enabled ?? true; // Default to enabled
			}
		} catch (error) {
			verboseLog("ToggleState: Error loading state, defaulting to enabled", error);
		}
		return true; // Default to enabled if no state file
	}

	private save(): void {
		try {
			const dir = path.dirname(this.statePath);
			if (!fs.existsSync(dir)) {
				fs.mkdirSync(dir, { recursive: true });
			}
			fs.writeFileSync(this.statePath, JSON.stringify({ enabled: this.enabled }, null, 2));
			verboseLog("ToggleState: Saved state", { enabled: this.enabled });
		} catch (error) {
			verboseLog("ToggleState: Error saving state", error);
		}
	}

	isEnabled(): boolean {
		return this.enabled;
	}

	enable(): void {
		this.enabled = true;
		this.save();
	}

	disable(): void {
		this.enabled = false;
		this.save();
	}

	toggle(): boolean {
		this.enabled = !this.enabled;
		this.save();
		return this.enabled;
	}

	getStatus(): string {
		return this.enabled ? "✅ ENABLED" : "❌ DISABLED";
	}
}

/**
 * Fetch available models from Cursor API
 */
async function fetchCursorModels(): Promise<string[]> {
	verboseLog("fetchCursorModels: Starting model fetch");
	try {
		const apiKey = process.env.CURSOR_API_KEY;
		if (!apiKey) {
			verboseLog("fetchCursorModels: No API key found, using static models");
			return [...STATIC_CURSOR_MODELS];
		}

		verboseLog("fetchCursorModels: API key found, fetching from Cursor API");
		const response = await fetch("https://api.cursor.com/v0/models", {
			headers: {
				Authorization: `Bearer ${apiKey}`,
			},
		});

		if (!response.ok) {
			verboseLog(`fetchCursorModels: API response not OK (${response.status}), using static models`);
			return [...STATIC_CURSOR_MODELS];
		}

		const data = (await response.json()) as ICursorModelsResponse;
		const models = ["auto", ...data.models];
		verboseLog("fetchCursorModels: Successfully fetched models", models);
		
		// Always include "auto" at the beginning, then add API models
		return models;
	} catch (error) {
		verboseLog("fetchCursorModels: Error fetching models, using static fallback", error);
		// Fallback to static list on any error
		return [...STATIC_CURSOR_MODELS];
	}
}

export const CursorCLI: Plugin = async ({ $, directory }) => {
	initVerboseLog(directory);
	verboseLog("CursorCLI: Plugin initializing", { directory });
	const errorLogger = new ErrorLogger(directory);
	const toggleState = new ToggleState(directory);
	
	// Fetch dynamic model list at plugin initialization
	const availableModels = await fetchCursorModels();
	verboseLog("CursorCLI: Plugin initialized with models", availableModels);
	verboseLog("CursorCLI: Toggle state", { enabled: toggleState.isEnabled() });

	/**
	 * Parse NDJSON stream from cursor-agent and accumulate response
	 */
	async function parseStreamResponse(
		streamOutput: string,
	): Promise<string> {
		const lines = streamOutput.trim().split("\n");
		let accumulatedText = "";
		const toolCalls: string[] = [];

		for (const line of lines) {
			if (!line.trim()) continue;

			try {
				const event: IStreamEvent = JSON.parse(line);

				switch (event.type) {
					case "system":
						if (event.subtype === "init" && event.model) {
							accumulatedText += `🤖 Using Cursor model: ${event.model}\n\n`;
						}
						break;

					case "assistant":
						if (event.message?.content) {
							for (const content of event.message.content) {
								if (content.type === "text") {
									accumulatedText += content.text;
								}
							}
						}
						break;

					case "tool_call":
						if (event.subtype === "started") {
							// Tool execution started
							if (event.tool_call) {
								toolCalls.push(
									`\n🔧 Tool executing: ${JSON.stringify(event.tool_call)}`,
								);
							}
						} else if (event.subtype === "completed") {
							// Tool execution completed
							toolCalls.push(
								`\n✅ Tool completed: ${JSON.stringify(event.tool_call)}`,
							);
						}
						break;

					case "result":
						if (event.result) {
							accumulatedText += `\n\n${event.result}`;
						}
						if (event.duration_ms) {
							accumulatedText += `\n\n⏱️  Completed in ${event.duration_ms}ms`;
						}
						break;
				}
			} catch (parseError) {
				errorLogger.log(
					parseError as Error,
					"parseStreamResponse",
				);
				// Skip malformed JSON lines
				continue;
			}
		}

		// Append tool call information
		if (toolCalls.length > 0) {
			accumulatedText += "\n\n" + toolCalls.join("\n");
		}

		return accumulatedText.trim();
	}

	return {
		tool: {
			/**
			 * Toggle Cursor tools on/off
			 */
			cursor_toggle: tool({
				description:
					"Toggle Cursor AI tools on or off. When disabled, cursor_chat and cursor_agent will not work. Use this to control when Cursor is available.",
				args: {
					action: tool.schema
						.enum(["on", "off", "toggle", "status"])
						.optional()
						.default("toggle")
						.describe(
							"Action to perform: 'on' (enable), 'off' (disable), 'toggle' (switch state), 'status' (check current state)",
						),
				},
				async execute(args) {
					const action = args.action ?? "toggle";

					switch (action) {
						case "on":
							toggleState.enable();
							return `✅ Cursor tools ENABLED\n\ncursor_chat and cursor_agent are now available.\n\nUse cursor_toggle with action=off to disable.`;

						case "off":
							toggleState.disable();
							return `❌ Cursor tools DISABLED\n\ncursor_chat and cursor_agent will return errors until re-enabled.\n\nUse cursor_toggle with action=on to enable.`;

						case "toggle":
							const newState = toggleState.toggle();
							return newState
								? `✅ Cursor tools ENABLED\n\ncursor_chat and cursor_agent are now available.`
								: `❌ Cursor tools DISABLED\n\ncursor_chat and cursor_agent will return errors until re-enabled.`;

						case "status":
							const status = toggleState.getStatus();
							const stateMsg = toggleState.isEnabled()
								? "Cursor tools are currently active and can be used."
								: "Cursor tools are currently disabled and will return errors if called.";
							return `🔍 Cursor Toggle Status: ${status}\n\n${stateMsg}\n\nUse cursor_toggle to change state.`;

						default:
							return `❓ Unknown action: ${action}. Use: on, off, toggle, or status`;
					}
				},
			}),

			/**
			 * Main chat tool - Send prompts to Cursor AI with streaming support
			 */
			cursor_chat: tool({
				description:
					"Send a prompt to Cursor AI with streaming responses. Supports all Cursor models including Auto mode (recommended).",
				args: {
					prompt: tool.schema
						.string()
						.describe(
							"The prompt/question to send to Cursor AI",
						),
					model: tool.schema
						.string()
						.optional()
						.default("auto")
						.describe(
							`Model to use. Available: ${availableModels.join(", ")}. Default: auto (Cursor picks best model)`,
						),
				},
				async execute(args, context) {
					// Check if Cursor tools are enabled
					if (!toggleState.isEnabled()) {
						return `❌ Cursor tools are currently DISABLED\n\nUse cursor_toggle with action=on to enable Cursor tools.\n\nCurrent status: ${toggleState.getStatus()}`;
					}

					try {
						const model = args.model ?? "auto";

						// Execute cursor-agent with streaming output
						const result =
							await $`cursor-agent -p --model ${model} --output-format stream-json --stream-partial-output ${args.prompt}`.text();

						// Parse the NDJSON stream
						const response =
							await parseStreamResponse(result);

						if (!response) {
							throw new Error(
								"Empty response from Cursor CLI",
							);
						}

						return response;
					} catch (error) {
						errorLogger.log(error as Error, "cursor_chat");
						return errorLogger.getUserMessage(
							error as Error,
						);
					}
				},
			}),

			/**
			 * List available Cursor models (fetched dynamically at plugin load)
			 */
			cursor_models: tool({
				description:
					"List all available Cursor AI models (dynamically fetched from Cursor API)",
				args: {},
				async execute() {
					const modelList = availableModels.map((m) => `  - ${m}`).join("\n");
					
					return `🎯 Available Cursor Models (${availableModels.length} models):\n\n${modelList}\n\n💡 Usage:\n  - Use "auto" (recommended) to let Cursor pick the best model\n  - Specify any model with cursor_chat or cursor_agent tools\n  - Models are fetched dynamically when plugin loads\n\n📝 Example: "Use cursor_chat with model=claude-4.5-sonnet-thinking to explain this code"`;
				},
			}),

			/**
			 * Agent tool - For file modifications and code generation
			 */
			cursor_agent: tool({
				description:
					"Run Cursor agent to modify files, generate code, or perform refactoring tasks. Use --force to allow file modifications.",
				args: {
					prompt: tool.schema
						.string()
						.describe(
							"Task description for the Cursor agent",
						),
					model: tool.schema
						.string()
						.optional()
						.default("auto")
						.describe(
							`Model to use. Available: ${availableModels.join(", ")}. Default: auto (Cursor picks best model)`,
						),
					force: tool.schema
						.boolean()
						.default(false)
						.describe(
							"Allow file modifications without confirmation (required for actual changes)",
						),
				},
				async execute(args) {
					// Check if Cursor tools are enabled
					if (!toggleState.isEnabled()) {
						return `❌ Cursor tools are currently DISABLED\n\nUse cursor_toggle with action=on to enable Cursor tools.\n\nCurrent status: ${toggleState.getStatus()}`;
					}

					try {
						const model = args.model ?? "auto";
						const forceFlag = args.force ? "--force" : "";

						// Build command dynamically
						const cmd = [
							"cursor-agent",
							"-p",
							forceFlag,
							`--model ${model}`,
							"--output-format stream-json",
							"--stream-partial-output",
							args.prompt,
						]
							.filter(Boolean)
							.join(" ");

						// Execute with shell
						const result = await $`${cmd}`.text();

						// Parse the NDJSON stream
						const response =
							await parseStreamResponse(result);

						if (!response) {
							throw new Error(
								"Empty response from Cursor CLI",
							);
						}

						// Add warning if force not used
						if (!args.force) {
							return `${response}\n\n⚠️  Note: File modifications were proposed but not applied. Use force=true to apply changes.`;
						}

						return response;
					} catch (error) {
						errorLogger.log(error as Error, "cursor_agent");
						return errorLogger.getUserMessage(
							error as Error,
						);
					}
				},
			}),
		},
	};
};
