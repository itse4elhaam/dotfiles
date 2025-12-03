/**
 * Cursor Proxy Server for OpenCode
 * 
 * Creates a local HTTP server that translates OpenAI-compatible requests
 * to cursor-agent CLI calls, allowing Cursor models to appear as native
 * providers in OpenCode's model switcher.
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

interface IStreamEvent {
	type: string;
	subtype?: string;
	message?: {
		role: string;
		content: Array<{ type: string; text: string }>;
	};
	result?: string;
	is_error?: boolean;
}

// Available Cursor models
const CURSOR_MODELS = [
	"auto",
	"claude-4.5-opus-high-thinking",
	"claude-4.5-sonnet-thinking",
	"gpt-5.1-codex",
	"gpt-5.1-codex-high",
	"gemini-3-pro",
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
		} catch (error) {
			// Silent fail
		}
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
			} catch (error) {
				// Skip malformed JSON
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
					res.writeHead(200, {
						"Content-Type": "text/event-stream",
						"Cache-Control": "no-cache",
						"Connection": "keep-alive",
					});

					// Spawn cursor-agent process
					const proc = Bun.spawn(
						["cursor-agent", "-p", "--model", model, "--output-format", "stream-json", "--stream-partial-output", prompt],
						{
							stdout: "pipe",
							stderr: "pipe",
						}
					);

					let accumulatedText = "";
					const reader = proc.stdout.getReader();
					const decoder = new TextDecoder();

					// Read stream line by line
					let buffer = "";
					while (true) {
						const { done, value } = await reader.read();
						
						if (done) break;
						
						buffer += decoder.decode(value, { stream: true });
						const lines = buffer.split("\n");
						buffer = lines.pop() || ""; // Keep incomplete line in buffer

						for (const line of lines) {
							if (!line.trim()) continue;

							try {
								const event: IStreamEvent = JSON.parse(line);

								// Extract text from assistant messages
								if (event.type === "assistant" && event.message?.content) {
									for (const content of event.message.content) {
										if (content.type === "text" && content.text) {
											accumulatedText += content.text;
											
											// Send SSE chunk
											const chunk = {
												id: `cursor-${Date.now()}`,
												object: "chat.completion.chunk",
												created: Math.floor(Date.now() / 1000),
												model: request.model,
												choices: [{
													index: 0,
													delta: { content: content.text },
													finish_reason: null,
												}],
											};
											res.write(`data: ${JSON.stringify(chunk)}\n\n`);
										}
									}
								}
							} catch (parseError) {
								// Skip malformed JSON
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
				} else {
					// Non-streaming response
					const output = await $`cursor-agent -p --model ${model} --output-format stream-json ${prompt}`.text();
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
		console.log(`✅ Cursor proxy running on http://127.0.0.1:${PORT}`);
	});

	// Cleanup on exit
	process.on("exit", () => {
		log("Cursor proxy server shutting down");
		server.close();
	});

	return {};
};
