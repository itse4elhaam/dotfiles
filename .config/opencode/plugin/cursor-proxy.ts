/**
 * Cursor Proxy Server for OpenCode
 * 
 * Creates a local HTTP server that translates OpenAI-compatible requests
 * to cursor-agent CLI calls, allowing Cursor models to appear as native
 * providers in OpenCode's model switcher.
 * 
 * Features:
 * - Supports all cursor-agent models including thinking variants
 * - Streams reasoning content in real-time
 * - Automatically approves MCP servers (--approve-mcps)
 * - Uses workspace directory context (--workspace)
 * - Forces command execution without prompts (--force)
 */

import { type Plugin } from "@opencode-ai/plugin";
import * as http from "node:http";
import * as fs from "node:fs";
import * as path from "node:path";

interface IChatCompletionRequest {
	model: string;
	messages: Array<{ role: string; content: string }>;
	stream?: boolean;
	temperature?: number;
	max_tokens?: number;
}

interface IToolCallResult {
	success?: Record<string, unknown>;
	rejected?: { command?: string; reason?: string };
}

interface IToolCall {
	shellToolCall?: {
		args?: { command?: string };
		result?: IToolCallResult & {
			success?: { stdout?: string; stderr?: string; exitCode?: number };
		};
	};
	readToolCall?: {
		args?: { path?: string; offset?: number; limit?: number };
		result?: {
			success?: { content?: string; path?: string; totalLines?: number; totalChars?: number };
		};
	};
	writeToolCall?: {
		args?: { path?: string; fileText?: string };
		result?: {
			success?: { path?: string; linesCreated?: number; fileSize?: number };
		};
	};
	editToolCall?: {
		args?: { path?: string; oldText?: string; newText?: string };
		result?: { success?: Record<string, unknown> };
	};
	grepToolCall?: {
		args?: { pattern?: string; path?: string };
		result?: {
			success?: { workspaceResults?: Record<string, { content: { totalMatchedLines: number } }> };
		};
	};
	globToolCall?: {
		args?: { globPattern?: string; targetDirectory?: string };
		result?: { success?: { totalFiles?: number } };
	};
	lsToolCall?: {
		args?: { path?: string; ignore?: string[] };
		result?: {
			success?: {
				directoryTreeRoot?: { childrenFiles?: unknown[]; childrenDirs?: unknown[] };
			};
		};
	};
	deleteToolCall?: {
		args?: { path?: string };
		result?: { success?: Record<string, unknown>; rejected?: { reason?: string } };
	};
	function?: { name?: string; arguments?: string };
}

interface IStreamEvent {
	type: string;
	subtype?: string;
	text?: string;
	call_id?: string;
	message?: {
		role: string;
		content: Array<{ type: string; text: string }>;
	};
	result?: string;
	is_error?: boolean;
	tool_call?: IToolCall;
}

// Available Cursor models (from cursor-agent --help)
const CURSOR_MODELS = [
	// Auto mode
	"composer-1",
	"auto",
	// Claude models
	"sonnet-4.5",
	"sonnet-4.5-thinking",
	"opus-4.5",
	"opus-4.5-thinking",
	"opus-4.1",
	// Google & xAI
	"gemini-3-pro",
	"grok",
	// GPT models
	"gpt-5",
	"gpt-5.1",
	"gpt-5-high",
	"gpt-5.1-high",
	"gpt-5-codex",
	"gpt-5-codex-high",
	"gpt-5.1-codex",
	"gpt-5.1-codex-high",
];

export const CursorProxy: Plugin = async ({ $, directory }) => {
	const PORT = 9876;
	const logPath = path.join(directory, ".opencode", "cursor-proxy.log");
	
	// Ensure log directory exists
	const logDir = path.dirname(logPath);
	if (!fs.existsSync(logDir)) {
		fs.mkdirSync(logDir, { recursive: true });
	}

	function log(message: string): void {
		const timestamp = new Date().toISOString();
		const logMessage = `[${timestamp}] ${message}\n`;
		try {
			fs.appendFileSync(logPath, logMessage);
		} catch {
			// Silent fail
		}
	}

	/**
	 * Format tool call started event into markdown
	 */
	function formatToolStarted(toolCall: IToolCall): string {
		if (toolCall.shellToolCall?.args?.command) {
			return `\n**Tool Use: bash**\n\`\`\`bash\n${toolCall.shellToolCall.args.command}\n\`\`\`\n`;
		}
		if (toolCall.readToolCall?.args?.path) {
			const args = toolCall.readToolCall.args;
			let info = args.path;
			if (args.offset !== undefined || args.limit !== undefined) {
				info += ` (offset: ${args.offset ?? 0}, limit: ${args.limit ?? "all"})`;
			}
			return `\n**Tool Use: read**\n\`${info}\`\n`;
		}
		if (toolCall.writeToolCall?.args?.path) {
			const args = toolCall.writeToolCall.args;
			const preview = args.fileText?.slice(0, 100) ?? "";
			const truncated = (args.fileText?.length ?? 0) > 100 ? "..." : "";
			return `\n**Tool Use: write**\n\`${args.path}\` (${args.fileText?.length ?? 0} chars)\n\`\`\`\n${preview}${truncated}\n\`\`\`\n`;
		}
		if (toolCall.editToolCall?.args?.path) {
			return `\n**Tool Use: edit**\n\`${toolCall.editToolCall.args.path}\`\n`;
		}
		if (toolCall.grepToolCall?.args) {
			const args = toolCall.grepToolCall.args;
			return `\n**Tool Use: grep**\n\`${args.pattern}\` in \`${args.path ?? "."}\`\n`;
		}
		if (toolCall.globToolCall?.args) {
			const args = toolCall.globToolCall.args;
			return `\n**Tool Use: glob**\n\`${args.globPattern}\` in \`${args.targetDirectory ?? "."}\`\n`;
		}
		if (toolCall.lsToolCall?.args) {
			const args = toolCall.lsToolCall.args;
			let info = args.path ?? ".";
			if (args.ignore?.length) {
				info += ` (ignore: ${args.ignore.join(", ")})`;
			}
			return `\n**Tool Use: list**\n\`${info}\`\n`;
		}
		if (toolCall.deleteToolCall?.args?.path) {
			return `\n**Tool Use: delete**\n\`${toolCall.deleteToolCall.args.path}\`\n`;
		}
		if (toolCall.function?.name) {
			return `\n**Tool Use: ${toolCall.function.name}**\n`;
		}
		return "";
	}

	/**
	 * Format tool call completed event into markdown
	 */
	function formatToolCompleted(toolCall: IToolCall): string {
		if (toolCall.shellToolCall) {
			const tc = toolCall.shellToolCall;
			if (tc.result?.rejected) {
				return `\n**Result:** Rejected${tc.result.rejected.reason ? ` (${tc.result.rejected.reason})` : ""}\n`;
			}
			if (tc.result?.success) {
				const { stdout, stderr, exitCode } = tc.result.success;
				const output = stdout || stderr || "";
				let result = `\n**Result:** Exit ${exitCode ?? 0}\n`;
				if (output.trim()) {
					result += `\`\`\`\n${output.slice(0, 2000)}${output.length > 2000 ? "\n... (truncated)" : ""}\n\`\`\`\n`;
				}
				return result;
			}
		}
		if (toolCall.readToolCall?.result?.success) {
			const s = toolCall.readToolCall.result.success;
			return `\n**Result:** Read ${s.totalLines ?? "?"} lines (${s.totalChars ?? "?"} chars)\n`;
		}
		if (toolCall.writeToolCall?.result?.success) {
			const s = toolCall.writeToolCall.result.success;
			return `\n**Result:** Wrote ${s.linesCreated ?? "?"} lines (${s.fileSize ?? "?"} bytes) to \`${s.path}\`\n`;
		}
		if (toolCall.editToolCall?.result?.success) {
			return `\n**Result:** Edit applied\n`;
		}
		if (toolCall.grepToolCall?.result?.success) {
			const results = toolCall.grepToolCall.result.success.workspaceResults;
			if (results) {
				const firstKey = Object.keys(results)[0];
				const matches = results[firstKey]?.content?.totalMatchedLines ?? 0;
				return `\n**Result:** Found ${matches} matches\n`;
			}
			return `\n**Result:** Grep completed\n`;
		}
		if (toolCall.globToolCall?.result?.success) {
			return `\n**Result:** Found ${toolCall.globToolCall.result.success.totalFiles ?? 0} files\n`;
		}
		if (toolCall.lsToolCall?.result?.success) {
			const root = toolCall.lsToolCall.result.success.directoryTreeRoot;
			const files = root?.childrenFiles?.length ?? 0;
			const dirs = root?.childrenDirs?.length ?? 0;
			return `\n**Result:** Listed ${files} files, ${dirs} directories\n`;
		}
		if (toolCall.deleteToolCall) {
			if (toolCall.deleteToolCall.result?.success) {
				return `\n**Result:** Deleted\n`;
			}
			if (toolCall.deleteToolCall.result?.rejected) {
				return `\n**Result:** Delete rejected${toolCall.deleteToolCall.result.rejected.reason ? `: ${toolCall.deleteToolCall.result.rejected.reason}` : ""}\n`;
			}
		}
		return `\n**Result:** Completed\n`;
	}

	/**
	 * Parse cursor-agent NDJSON output and extract text
	 */
	function parseCursorOutput(output: string): string {
		const lines = output.trim().split("\n");
		let text = "";

		for (const line of lines) {
			if (!line.trim()) continue;
			
			try {
				const event: IStreamEvent = JSON.parse(line);
				
				if (event.type === "assistant" && event.message?.content) {
					for (const content of event.message.content) {
						if (content.type === "text") {
							text += content.text;
						}
					}
				}
				
				if (event.type === "result" && event.result) {
					text += event.result;
				}
			} catch {
				continue;
			}
		}

		return text.trim();
	}

	/**
	 * Handle OpenAI-compatible chat completion requests with streaming
	 */
	async function handleChatCompletion(
		req: http.IncomingMessage,
		res: http.ServerResponse,
	): Promise<void> {
		let body = "";

		req.on("data", (chunk) => {
			body += chunk.toString();
		});

		req.on("end", async () => {
			try {
				const request: IChatCompletionRequest = JSON.parse(body);
				log(`Request: model=${request.model}, messages=${request.messages.length}, stream=${request.stream}`);

				// Extract the last user message as the prompt
				const lastMessage = request.messages[request.messages.length - 1];
				const prompt = lastMessage?.content || "Hello";

				// Map model name (handle both with/without cursor/ prefix)
				const model = request.model.replace("cursor/", "");
				
				if (!CURSOR_MODELS.includes(model)) {
					log(`Unknown model: ${model}`);
					res.writeHead(400, { "Content-Type": "application/json" });
					res.end(JSON.stringify({ error: `Unknown model: ${model}. Available: ${CURSOR_MODELS.join(", ")}` }));
					return;
				}

				log(`Executing: cursor-agent with model=${model}`);

				// If streaming is requested
				if (request.stream) {
					log(`[STREAM START] Starting streaming response for model=${model}`);
					res.writeHead(200, {
						"Content-Type": "text/event-stream",
						"Cache-Control": "no-cache",
						"Connection": "keep-alive",
					});

					// Spawn cursor-agent process
					log(`[SPAWN] Spawning cursor-agent with --force, --approve-mcps, and --workspace flags`);
					const proc = Bun.spawn(
						["cursor-agent", "-p", "--force", "--model", model, "--output-format", "stream-json", "--stream-partial-output", "--approve-mcps", "--workspace", directory, prompt],
						{
							stdout: "pipe",
							stderr: "pipe",
						}
					);

					let accumulatedText = "";
					let fullRawOutput = "";
					
					log(`[CAPTURE] Starting output capture`);
					const reader = proc.stdout.getReader();
					const decoder = new TextDecoder();

					const sendChunk = (content: string) => {
						if (!content) return;
						accumulatedText += content;
						const chunk = {
							id: `cursor-${Date.now()}`,
							object: "chat.completion.chunk",
							created: Math.floor(Date.now() / 1000),
							model: request.model,
							choices: [{
								index: 0,
								delta: { content },
								finish_reason: null,
							}],
						};
						res.write(`data: ${JSON.stringify(chunk)}\n\n`);
					};

					// Read stream line by line
					let buffer = "";
					while (true) {
						const { done, value } = await reader.read();
						
						if (done) break;
						
						const chunk = decoder.decode(value, { stream: true });
						fullRawOutput += chunk;
						buffer += chunk;
						const lines = buffer.split("\n");
						buffer = lines.pop() || "";

						for (const line of lines) {
							if (!line.trim()) continue;

							try {
								const event: IStreamEvent = JSON.parse(line);

								// Handle thinking events (for thinking models like sonnet-4.5-thinking)
								if (event.type === "thinking" && event.subtype === "delta" && event.text) {
									// Format thinking as a distinct block
									sendChunk(`\n> **Thinking:** ${event.text}`);
								}

								// Handle tool calls (started)
								if (event.type === "tool_call" && event.subtype === "started" && event.tool_call) {
									const formatted = formatToolStarted(event.tool_call);
									sendChunk(formatted);
								}

								// Handle tool calls (completed)
								if (event.type === "tool_call" && event.subtype === "completed" && event.tool_call) {
									const formatted = formatToolCompleted(event.tool_call);
									sendChunk(formatted);
								}

								// Extract text from assistant messages
								if (event.type === "assistant" && event.message?.content) {
									for (const content of event.message.content) {
										if (content.type === "text" && content.text) {
											sendChunk(content.text);
										}
									}
								}
							} catch {
								continue;
							}
						}
					}

					// Send final chunk
					const finalChunk = {
						id: `cursor-${Date.now()}`,
						object: "chat.completion.chunk",
						created: Math.floor(Date.now() / 1000),
						model: request.model,
						choices: [{
							index: 0,
							delta: {},
							finish_reason: "stop",
						}],
					};
					res.write(`data: ${JSON.stringify(finalChunk)}\n\n`);
					res.write("data: [DONE]\n\n");
					res.end();

					log(`Streaming complete: ${accumulatedText.length} chars`);
					log(`===== COMPLETE RAW CURSOR OUTPUT START =====`);
					log(fullRawOutput);
					log(`===== COMPLETE RAW CURSOR OUTPUT END =====`);
				} else {
					// Non-streaming response
					const output = await $`cursor-agent -p --force --model ${model} --output-format stream-json --approve-mcps --workspace ${directory} ${prompt}`.text();
					const responseText = parseCursorOutput(output);
					
					if (!responseText) {
						throw new Error("Empty response from cursor-agent");
					}

					log(`Response length: ${responseText.length} chars`);

					const response = {
						id: `cursor-${Date.now()}`,
						object: "chat.completion",
						created: Math.floor(Date.now() / 1000),
						model: request.model,
						choices: [{
							index: 0,
							message: {
								role: "assistant",
								content: responseText,
							},
							finish_reason: "stop",
						}],
						usage: {
							prompt_tokens: 0,
							completion_tokens: 0,
							total_tokens: 0,
						},
					};

					res.writeHead(200, { "Content-Type": "application/json" });
					res.end(JSON.stringify(response));
				}
			} catch (error) {
				log(`Error: ${error instanceof Error ? error.message : String(error)}`);
				res.writeHead(500, { "Content-Type": "application/json" });
				res.end(JSON.stringify({ error: error instanceof Error ? error.message : String(error) }));
			}
		});
	}

	/**
	 * Handle model list requests
	 */
	function handleModels(res: http.ServerResponse): void {
		const models = CURSOR_MODELS.map((id) => ({
			id: `cursor/${id}`,
			object: "model",
			created: Date.now(),
			owned_by: "cursor",
		}));

		res.writeHead(200, { "Content-Type": "application/json" });
		res.end(JSON.stringify({ object: "list", data: models }));
	}

	// Create HTTP server
	const server = http.createServer((req, res) => {
		// Enable CORS
		res.setHeader("Access-Control-Allow-Origin", "*");
		res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
		res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");

		if (req.method === "OPTIONS") {
			res.writeHead(200);
			res.end();
			return;
		}

		log(`${req.method} ${req.url}`);

		if (req.url === "/v1/chat/completions" && req.method === "POST") {
			handleChatCompletion(req, res);
		} else if (req.url === "/v1/models" && req.method === "GET") {
			handleModels(res);
		} else {
			res.writeHead(404, { "Content-Type": "application/json" });
			res.end(JSON.stringify({ error: "Not found" }));
		}
	});

	// Start server
	server.listen(PORT, "127.0.0.1", () => {
		log(`Cursor proxy server started on http://127.0.0.1:${PORT}`);
		console.log(`Cursor proxy running on http://127.0.0.1:${PORT}`);
	});

	// Cleanup on exit
	process.on("exit", () => {
		log("Cursor proxy server shutting down");
		server.close();
	});

	return {};
};
