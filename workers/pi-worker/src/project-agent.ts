import { createInterface } from "node:readline";
import type { Readable, Writable } from "node:stream";
import { Agent, type AgentEvent, type AgentTool, type StreamFn, type ThinkingLevel } from "@earendil-works/pi-agent-core";
import { Type, type Model } from "@earendil-works/pi-ai";
import { builtinModels } from "@earendil-works/pi-ai/providers/all";
import type { ProjectAgentOptions } from "./contracts.ts";
import { ReadOnlyJsonCredentialStore } from "./credential-store.ts";
import { providerStreamControls } from "./provider-reliability.ts";
import {
	encodeEnvelope,
	envelope,
	parseEnvelopeLine,
	ProjectToolBridge,
	type BridgeEnvelope,
	type BridgeWriter,
} from "./project-agent-protocol.ts";
import { safeThinkingLevel } from "./reasoning-budget.ts";

const PROJECT_OVERVIEW_TOOL = "project_overview";
const PROJECT_SEARCH_TOOL = "project_search";
const CREATION_OBSERVE_TOOL = "creation_observe";
const SUPPORTED_TOOLS = new Set([PROJECT_OVERVIEW_TOOL, PROJECT_SEARCH_TOOL, CREATION_OBSERVE_TOOL]);

export interface ProjectAgentStart {
	sessionId: string;
	turnId: string;
	prompt: string;
	systemPrompt: string;
	allowedTools: string[];
	maxTurns: number;
	maxToolCalls: number;
}

export interface ProjectAgentModelRuntime {
	model: Model<any>;
	streamFn: StreamFn;
	thinkingLevel?: ThinkingLevel;
}

export interface ProjectAgentTurnResult {
	status: "completed" | "blocked" | "cancelled";
	answer: string;
	turns: number;
	toolCalls: number;
}

/** Run one bounded Pi turn. Project behavior remains behind bridge tools. */
export async function runProjectAgentTurn(
	start: ProjectAgentStart,
	runtime: ProjectAgentModelRuntime,
	bridge: ProjectToolBridge,
	emit: BridgeWriter,
	signal?: AbortSignal,
): Promise<ProjectAgentTurnResult> {
	let turns = 0;
	let toolCalls = 0;
	const tools = createProjectAgentTools(start, bridge, () => {
		if (toolCalls >= start.maxToolCalls) throw new Error("Project Agent tool budget exhausted");
		toolCalls += 1;
	});
	const agent = new Agent({
		initialState: {
			systemPrompt: start.systemPrompt,
			model: runtime.model,
			thinkingLevel: runtime.thinkingLevel ?? "off",
			tools,
		},
		streamFn: runtime.streamFn,
		sessionId: start.sessionId,
		toolExecution: "sequential",
		shouldStopAfterTurn: ({ toolResults }) => {
			turns += 1;
			return toolResults.length === 0 || turns >= start.maxTurns;
		},
	});
	const abort = () => agent.abort();
	signal?.addEventListener("abort", abort, { once: true });
	const eventWriter = new ProjectAgentEventWriter(start.turnId, emit);
	agent.subscribe((event) => eventWriter.handle(event));
	try {
		await agent.prompt(start.prompt);
		if (signal?.aborted) {
			return { status: "cancelled", answer: "", turns, toolCalls };
		}
		const answer = lastAssistantText(agent.state.messages as unknown[]);
		return {
			status: answer ? "completed" : "blocked",
			answer,
			turns,
			toolCalls,
		};
	} finally {
		signal?.removeEventListener("abort", abort);
	}
}

export async function runProjectAgentProcess(
	options: ProjectAgentOptions,
	version: string,
	input: Readable = process.stdin,
	output: Writable = process.stdout,
): Promise<number> {
	const write: BridgeWriter = (value) => output.write(encodeEnvelope(value));
	write(envelope("bridge.ready", "bridge", { version }));
	const lines = createInterface({ input, crlfDelay: Infinity });
	let activeTurn = "";
	let bridge: ProjectToolBridge | null = null;
	let controller: AbortController | null = null;
	let settled = false;

	return await new Promise<number>((resolve) => {
		const finish = (code: number) => {
			if (settled) return;
			settled = true;
			lines.close();
			resolve(code);
		};

		lines.on("line", (line) => {
			if (!line.trim() || settled) return;
			try {
				const value = parseEnvelopeLine(line);
				if (value.type === "turn.start") {
					if (activeTurn) throw new Error("Project Agent process accepts one turn only");
					const start = parseStart(value);
					activeTurn = start.turnId;
					bridge = new ProjectToolBridge(activeTurn, write);
					controller = new AbortController();
					void loadModelRuntime(options)
						.then((runtime) => runProjectAgentTurn(start, runtime, bridge!, write, controller!.signal))
						.then((result) => {
							write(envelope("turn.complete", activeTurn, result as unknown as Record<string, unknown>));
							finish(result.status === "completed" ? 0 : 2);
						})
						.catch((error) => {
							write(envelope("bridge.error", activeTurn, { message: safeError(error) }));
							finish(1);
						});
					return;
				}
				if (!activeTurn || value.turn_id !== activeTurn) {
					throw new Error("bridge message does not belong to the active turn");
				}
				if (value.type === "tool.result") {
					bridge?.receive(value);
					return;
				}
				if (value.type === "turn.cancel") {
					bridge?.cancel(String(value.payload.reason || "Project Agent turn cancelled"));
					controller?.abort();
					return;
				}
				throw new Error(`unexpected host message: ${value.type}`);
			} catch (error) {
				const turnId = activeTurn || "bridge";
				write(envelope("bridge.error", turnId, { message: safeError(error) }));
				bridge?.cancel("Project Agent protocol failed");
				controller?.abort();
				finish(1);
			}
		});

		lines.on("close", () => {
			if (settled) return;
			bridge?.cancel("Project Agent input closed");
			controller?.abort();
			finish(1);
		});
	});
}

function createProjectAgentTools(
	start: ProjectAgentStart,
	bridge: ProjectToolBridge,
	onCall: () => void,
): AgentTool[] {
	return start.allowedTools.map((name) => {
		if (!SUPPORTED_TOOLS.has(name)) throw new Error(`unsupported Project Agent tool: ${name}`);
		const definition = projectToolDefinition(name);
		return {
			name,
			label: definition.label,
			description: definition.description,
			parameters: definition.parameters,
			executionMode: "sequential",
			execute: async (_toolCallId, params, signal) => {
				onCall();
				const result = await bridge.request(name, params as Record<string, unknown>, signal);
				return {
					content: [{ type: "text", text: JSON.stringify(result) }],
					details: { name },
				};
			},
		} satisfies AgentTool;
	});
}

function projectToolDefinition(name: string): {
	label: string;
	description: string;
	parameters: ReturnType<typeof Type.Object>;
} {
	if (name === PROJECT_OVERVIEW_TOOL) {
		return {
			label: "Read Project Overview",
			description: "Read current project identity, progress, next action, and blocking state.",
			parameters: Type.Object({ focus: Type.Optional(Type.String({ maxLength: 200 })) }),
		};
	}
	if (name === PROJECT_SEARCH_TOOL) {
		return {
			label: "Search Project",
			description: "Search the indexed project library and promoted manuscript without reading arbitrary files.",
			parameters: Type.Object({
				query: Type.String({ minLength: 1, maxLength: 300 }),
				limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 30 })),
			}),
		};
	}
	return {
		label: "Observe Creation",
		description: "Read current creation run, Agent activity, and recent workflow events.",
		parameters: Type.Object({ focus: Type.Optional(Type.String({ maxLength: 200 })) }),
	};
}

function parseStart(value: BridgeEnvelope): ProjectAgentStart {
	if (value.type !== "turn.start") throw new Error("expected turn.start");
	const allowedTools = value.payload.allowed_tools;
	const start: ProjectAgentStart = {
		sessionId: requiredString(value.payload, "session_id"),
		turnId: value.turn_id,
		prompt: requiredString(value.payload, "prompt"),
		systemPrompt: requiredString(value.payload, "system_prompt"),
		allowedTools: Array.isArray(allowedTools) ? allowedTools.map(String) : [],
		maxTurns: positiveInteger(value.payload.max_turns, 4),
		maxToolCalls: positiveInteger(value.payload.max_tool_calls, 4),
	};
	if (!start.allowedTools.length) throw new Error("turn.start requires at least one allowed tool");
	return start;
}

async function loadModelRuntime(options: ProjectAgentOptions): Promise<ProjectAgentModelRuntime> {
	const [provider, modelId] = parseModelId(options.model);
	const credentials = new ReadOnlyJsonCredentialStore(options.authPath);
	const models = builtinModels({ credentials });
	const model = models.getModel(provider, modelId);
	if (!model) throw new Error(`Pi AI model is not available: ${options.model}`);
	const auth = await models.getAuth(model);
	if (!auth) throw new Error(`Pi AI provider is not authenticated: ${provider}`);
	return {
		model,
		thinkingLevel: safeThinkingLevel(model, options.thinking),
		streamFn: (streamModel, context, streamOptions = {}) => models.streamSimple(
			streamModel,
			context,
			{ ...streamOptions, ...providerStreamControls(options.providerReliability) },
		),
	};
}

class ProjectAgentEventWriter {
	private text = "";
	private reasoning = "";
	private readonly turnId: string;
	private readonly emit: BridgeWriter;

	constructor(turnId: string, emit: BridgeWriter) {
		this.turnId = turnId;
		this.emit = emit;
	}

	handle(event: AgentEvent): void {
		if (event.type === "message_update") {
			const update = event.assistantMessageEvent;
			if (update.type === "text_delta") {
				this.text += update.delta;
				if (this.text.length >= 96) this.flushText();
			}
			if (update.type === "thinking_delta") {
				this.reasoning += update.delta;
				if (this.reasoning.length >= 160) this.flushReasoning();
			}
			return;
		}
		if (event.type === "message_end" || event.type === "tool_execution_start" || event.type === "agent_end") {
			this.flush();
		}
		if (event.type === "message_end" && event.message.role === "assistant") {
			const usage = event.message.usage;
			this.send({
				event: "model.usage",
				input_tokens: usage.input,
				output_tokens: usage.output,
				cache_read_tokens: usage.cacheRead,
				cache_write_tokens: usage.cacheWrite,
			});
		}
		if (event.type === "tool_execution_start") {
			this.send({ event: "tool.started", call_id: event.toolCallId, tool: event.toolName });
			return;
		}
		if (event.type === "tool_execution_end") {
			this.send({ event: "tool.finished", call_id: event.toolCallId, tool: event.toolName, error: event.isError });
			return;
		}
		if (["agent_start", "agent_end", "turn_start", "turn_end"].includes(event.type)) {
			this.send({ event: event.type.replaceAll("_", ".") });
		}
	}

	private flush(): void {
		this.flushReasoning();
		this.flushText();
	}

	private flushText(): void {
		if (!this.text) return;
		this.send({ event: "text.delta", text: this.text });
		this.text = "";
	}

	private flushReasoning(): void {
		if (!this.reasoning) return;
		this.send({ event: "reasoning.delta", text: this.reasoning });
		this.reasoning = "";
	}

	private send(payload: Record<string, unknown>): void {
		this.emit(envelope("agent.event", this.turnId, payload));
	}
}

function lastAssistantText(messages: unknown[]): string {
	for (let index = messages.length - 1; index >= 0; index -= 1) {
		const message = messages[index];
		if (!isRecord(message) || message.role !== "assistant" || !Array.isArray(message.content)) continue;
		const text = message.content
			.filter(isRecord)
			.filter((item) => item.type === "text")
			.map((item) => String(item.text || ""))
			.join("")
			.trim();
		if (text) return text;
	}
	return "";
}

function requiredString(value: Record<string, unknown>, field: string): string {
	const item = String(value[field] || "").trim();
	if (!item) throw new Error(`turn.start requires ${field}`);
	return item;
}

function positiveInteger(value: unknown, fallback: number): number {
	const parsed = Number(value ?? fallback);
	if (!Number.isInteger(parsed) || parsed < 1) throw new Error("Project Agent budgets must be positive integers");
	return parsed;
}

function parseModelId(value: string): [string, string] {
	const separator = value.indexOf("/");
	if (separator <= 0 || separator === value.length - 1) throw new Error("model must use provider/model format");
	return [value.slice(0, separator), value.slice(separator + 1)];
}

function safeError(error: unknown): string {
	return (error instanceof Error ? error.message : String(error)).slice(0, 2000);
}

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}
