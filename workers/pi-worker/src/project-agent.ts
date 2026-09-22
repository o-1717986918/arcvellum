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
const WORKSPACE_CATALOG_TOOL = "workspace_catalog";
const PROJECT_SEARCH_TOOL = "project_search";
const CREATION_OBSERVE_TOOL = "creation_observe";
const PROJECT_CONTROLS_TOOL = "project_controls";
const PROJECT_RECORD_DIRECTION_TOOL = "project_record_direction";
const CREATION_CONTROL_TOOL = "creation_control";
const PROJECT_DECISION_RESOLVE_TOOL = "project_decision_resolve";
const PROJECT_QUALITY_UPDATE_TOOL = "project_quality_update";
const PROJECT_RHYTHM_UPDATE_TOOL = "project_rhythm_update";
const PROJECT_STYLE_MOUNT_TOOL = "project_style_mount";
const PROJECT_ASSET_PROMOTE_TOOL = "project_asset_promote";
const PROJECT_DIAGNOSE_TOOL = "project_diagnose";
const PROJECT_CREATE_TOOL = "project_create";
const PROJECT_GOAL_MANAGE_TOOL = "project_goal_manage";
const PROJECT_CHAPTER_EXTEND_TOOL = "project_chapter_extend";
const SUPPORTED_TOOLS = new Set([
	WORKSPACE_CATALOG_TOOL,
	PROJECT_OVERVIEW_TOOL,
	PROJECT_SEARCH_TOOL,
	CREATION_OBSERVE_TOOL,
	PROJECT_CONTROLS_TOOL,
	PROJECT_RECORD_DIRECTION_TOOL,
	CREATION_CONTROL_TOOL,
	PROJECT_DECISION_RESOLVE_TOOL,
	PROJECT_QUALITY_UPDATE_TOOL,
	PROJECT_RHYTHM_UPDATE_TOOL,
	PROJECT_STYLE_MOUNT_TOOL,
	PROJECT_ASSET_PROMOTE_TOOL,
	PROJECT_DIAGNOSE_TOOL,
	PROJECT_CREATE_TOOL,
	PROJECT_GOAL_MANAGE_TOOL,
	PROJECT_CHAPTER_EXTEND_TOOL,
]);

export interface ProjectAgentStart {
	sessionId: string;
	turnId: string;
	prompt: string;
	systemPrompt: string;
	allowedTools: string[];
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

/** Run one time-bounded Pi turn. Project behavior remains behind bridge tools. */
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
			return toolResults.length === 0;
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
	if (name === WORKSPACE_CATALOG_TOOL) {
		return {
			label: "Read Work Catalog",
			description: "List registered works and stable work_id values without exposing filesystem paths.",
			parameters: Type.Object({ query: Type.Optional(Type.String({ maxLength: 200 })) }),
		};
	}
	if (name === PROJECT_OVERVIEW_TOOL) {
		return {
			label: "Read Project Overview",
			description: "Read current project identity, progress, next action, and blocking state.",
			parameters: Type.Object({ work_id: workId(), focus: Type.Optional(Type.String({ maxLength: 200 })) }),
		};
	}
	if (name === PROJECT_SEARCH_TOOL) {
		return {
			label: "Search Project",
			description: "Search the indexed project library and promoted manuscript without reading arbitrary files.",
			parameters: Type.Object({
				work_id: workId(),
				query: Type.String({ minLength: 1, maxLength: 300 }),
				limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 30 })),
			}),
		};
	}
	if (name === CREATION_OBSERVE_TOOL) return {
		label: "Observe Creation",
		description: "Read current creation run, Agent activity, and recent workflow events.",
		parameters: Type.Object({ work_id: workId(), focus: Type.Optional(Type.String({ maxLength: 200 })) }),
	};
	if (name === PROJECT_CONTROLS_TOOL) return {
		label: "Inspect Project Controls",
		description: "Read pending decisions, quality rules, rhythm, mounted style, or delivery readiness.",
		parameters: Type.Object({
			work_id: workId(),
			section: Type.Optional(Type.Union([
				Type.Literal("all"),
				Type.Literal("decisions"),
				Type.Literal("quality"),
				Type.Literal("rhythm"),
				Type.Literal("style"),
				Type.Literal("archive"),
				Type.Literal("delivery"),
			])),
		}),
	};
	if (name === PROJECT_RECORD_DIRECTION_TOOL) return {
		label: "Record Creative Direction",
		description: "Record a durable creative direction for the current project when it advances the user's stated goal.",
		parameters: Type.Object({
			work_id: workId(),
			message: Type.String({ minLength: 1, maxLength: 6000 }),
		}),
	};
	if (name === CREATION_CONTROL_TOOL) return {
		label: "Control Creation",
		description: "Start, pause, or resume the project's lean-v2 creation run. Use this directly; do not ask for tool approval.",
		parameters: Type.Object({
			work_id: workId(),
			operation: Type.Union([Type.Literal("start"), Type.Literal("pause"), Type.Literal("resume")]),
			reason: Type.Optional(Type.String({ maxLength: 500 })),
		}),
	};
	if (name === PROJECT_DECISION_RESOLVE_TOOL) return {
		label: "Resolve Project Decision",
		description: "Choose one currently available option and resume creation after it is consumed.",
		parameters: Type.Object({
			work_id: workId(),
			choice_id: Type.String({ minLength: 1, maxLength: 300 }),
			selected: Type.String({ minLength: 1, maxLength: 300 }),
			rationale: Type.Optional(Type.String({ maxLength: 2000 })),
		}),
	};
	if (name === PROJECT_QUALITY_UPDATE_TOOL) return {
		label: "Update Quality Rules",
		description: "Replace the complete validated language and lint profile for future candidates.",
		parameters: Type.Object({
			work_id: workId(),
			profile: Type.Object({}, { additionalProperties: true }),
		}),
	};
	if (name === PROJECT_RHYTHM_UPDATE_TOOL) return {
		label: "Update Narrative Rhythm",
		description: "Update rhythm entries and/or the book profile. For a profile-only correction, omit entries; the service preserves all current scene entries.",
		parameters: Type.Object({
			work_id: workId(),
			entries: Type.Optional(Type.Array(Type.Object({}, { additionalProperties: true }), { maxItems: 500 })),
			book_profile: Type.Optional(Type.Object({}, { additionalProperties: true })),
		}),
	};
	if (name === PROJECT_STYLE_MOUNT_TOOL) return {
		label: "Mount Style Version",
		description: "Mount one exact immutable style version after Studio validates its current impact preview.",
		parameters: Type.Object({
			work_id: workId(),
			style_id: Type.String({ minLength: 1, maxLength: 200 }),
			version_id: Type.String({ minLength: 1, maxLength: 200 }),
			content_hash: Type.String({ minLength: 8, maxLength: 200 }),
			scope: Type.Optional(Type.String({ maxLength: 40 })),
			priority: Type.Optional(Type.String({ maxLength: 40 })),
		}),
	};
	if (name === PROJECT_ASSET_PROMOTE_TOOL) return {
		label: "Promote Reviewed Asset",
		description: "Start formal promotion for an archive candidate only after its existing review and promotion gates pass.",
		parameters: Type.Object({
			work_id: workId(),
			candidate_id: Type.String({ minLength: 1, maxLength: 300 }),
		}),
	};
	if (name === PROJECT_DIAGNOSE_TOOL) return {
		label: "Diagnose Project",
		description: "Diagnose decisions, stalls, recoverable stops, or completion before taking recovery action.",
		parameters: Type.Object({ work_id: workId(), focus: Type.Optional(Type.String({ maxLength: 300 })) }),
	};
	if (name === PROJECT_CREATE_TOOL) return {
		label: "Create Work",
		description: "Create and register a new literary work in the configured ArcVellum library.",
		parameters: Type.Object({
			title: Type.String({ minLength: 1, maxLength: 200 }),
			work_type: Type.Optional(Type.String({ maxLength: 80 })),
			target_length: Type.Optional(Type.Integer({ minimum: 1000, maximum: 10000000 })),
			target_chapters: Type.Optional(Type.Integer({ minimum: 0, maximum: 10000 })),
			target_scenes: Type.Optional(Type.Integer({ minimum: 0, maximum: 100000 })),
			premise: Type.Optional(Type.String({ maxLength: 6000 })),
			genre: Type.Optional(Type.String({ maxLength: 200 })),
		}),
	};
	if (name === PROJECT_GOAL_MANAGE_TOOL) return {
		label: "Manage Long-running Goal",
		description: "Start, pause, resume, or recover a durable full-auto lean-v2 goal for one registered work.",
		parameters: Type.Object({
			work_id: workId(),
			operation: Type.Union([
				Type.Literal("start"), Type.Literal("pause"), Type.Literal("resume"), Type.Literal("recover"),
			]),
			objective: Type.Optional(Type.String({ maxLength: 8000 })),
			stop_after_formal_units: Type.Optional(Type.Integer({ minimum: 0, maximum: 100000 })),
		}),
	};
	if (name === PROJECT_CHAPTER_EXTEND_TOOL) return {
		label: "Extend Current Chapter",
		description: "Append new planned scenes after the latest committed scene of the current chapter and rebalance future scene counts while preserving the book's total character target. Never insert into already written history or use rhythm settings as scene inventory.",
		parameters: Type.Object({
			work_id: workId(),
			chapter_id: Type.String({ pattern: "^chapter_[0-9]{4}$" }),
			additional_scenes: Type.Integer({ minimum: 1, maximum: 8 }),
			target_per_scene: Type.Optional(Type.Integer({ minimum: 1800, maximum: 6000 })),
			direction: Type.String({ minLength: 1, maxLength: 3000 }),
		}),
	};
	throw new Error(`unsupported Project Agent tool: ${name}`);
}

function workId() {
	return Type.Optional(Type.String({ pattern: "^work-[a-f0-9]{16}$" }));
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
