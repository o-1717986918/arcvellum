import { createHash } from "node:crypto";
import { Agent } from "@earendil-works/pi-agent-core";
import type { AgentMessage } from "@earendil-works/pi-agent-core";
import { builtinModels } from "@earendil-works/pi-ai/providers/all";
import type { RuntimeEventSink, WorkerOptions, WorkerState } from "./contracts.ts";
import { ReadOnlyJsonCredentialStore } from "./credential-store.ts";
import { WorkerEventAdapter } from "./event-adapter.ts";
import { reasoningThinkingBudgets, safeThinkingLevel } from "./reasoning-budget.ts";
import { classifyProviderFailure, providerStreamControls } from "./provider-reliability.ts";

export interface ConversationResult {
	status: "completed" | "blocked";
	message: string;
	answer: string;
	taskId: string;
	provider: string;
	model: string;
	turns: number;
	toolCalls: number;
	providerRequests: number;
	reasoningCharacters: number;
	textCharacters: number;
	writtenOutputs: string[];
	validationPassed: boolean;
	initializationAnswer?: string;
	failureKind?: string;
	providerError?: string;
	providerFailureRetryable?: boolean;
}

/** Run one bounded, tool-free role conversation through the embedded Pi core. */
export async function runConversation(
	options: WorkerOptions,
	prompt: string,
	emit: RuntimeEventSink,
): Promise<ConversationResult> {
	const [provider, modelId] = parseModelId(options.model);
	const credentials = new ReadOnlyJsonCredentialStore(options.authPath);
	const models = builtinModels({ credentials });
	const model = models.getModel(provider, modelId);
	if (!model) throw new Error(`Pi AI model is not available: ${options.model}`);
	const auth = await models.getAuth(model);
	if (!auth) throw new Error(`Pi AI provider is not authenticated: ${provider}`);

	const actorConversation = options.conversationRole === "character-actor";
	const actorTurn = actorConversation ? actorTurnEnvelope(prompt) : null;
	const messages = actorTurn ? [] : conversationMessages(options.conversationRole ?? "default", prompt);
	const initializedEnvironment = options.conversationRole === "environment-writer" && messages.length === 2;
	const state = emptyState();
	const sessionId = `arcvellum-conversation-${createHash("sha256").update(prompt).digest("hex").slice(0, 20)}`;
	let messageIndex = 0;
	const eventAdapter = new WorkerEventAdapter(sessionId, state, (event, data) => {
		if (actorConversation || initializedEnvironment) {
			if (messageIndex === 0 && (event === "agent.message.delta" || event === "agent.message.completed")) return;
			if (messageIndex > 0 && (event === "runner.session.created" || event === "runner.session.status")) return;
			if (messageIndex < messages.length - 1 && event === "runner.session.finished") return;
		}
		emit(event, data);
	});
	const effectiveThinking = safeThinkingLevel(model, options.thinking);
	const systemPrompt = actorTurn?.initialization ?? conversationSystemPrompt(options.conversationRole ?? "default");
	const agent = new Agent({
		initialState: {
			systemPrompt,
			model,
			thinkingLevel: effectiveThinking,
			tools: [],
			...(actorTurn?.history.length ? { messages: actorHistoryMessages(actorTurn, model) } : {}),
		},
		streamFn: (streamModel, streamContext, streamOptions = {}) => models.streamSimple(
			streamModel,
			streamContext,
			{ ...streamOptions, ...providerStreamControls(options.providerReliability) },
		),
		sessionId,
		thinkingBudgets: reasoningThinkingBudgets(options.reasoningBudget)
			?? { minimal: 128, low: 512, medium: 1024, high: 2048 },
		shouldStopAfterTurn: () => true,
		onPayload: (payload) => {
			eventAdapter.providerRequest(provider, modelId);
			return payload;
		},
	});
	agent.subscribe((event) => eventAdapter.handle(event));
	let initializationAnswer = "";
	let promptedCurrent = false;
	let currentAnswer = "";
	if (actorTurn) {
		messageIndex = 1;
		promptedCurrent = true;
		const priorMessages = agent.state.messages.length;
		await agent.prompt(actorTurn.prompt);
		currentAnswer = lastAssistantText((agent.state.messages as unknown[]).slice(priorMessages));
	} else {
		for (const [index, message] of messages.entries()) {
			messageIndex = index;
			const priorMessages = agent.state.messages.length;
			await agent.prompt(message);
			const reply = lastAssistantText((agent.state.messages as unknown[]).slice(priorMessages));
			if (initializedEnvironment && index === 0) initializationAnswer = reply;
			if (index === messages.length - 1) currentAnswer = reply;
			if (agent.state.errorMessage) break;
		}
	}
	const answer = actorTurn || initializedEnvironment ? currentAnswer : lastAssistantText(agent.state.messages as unknown[]);
	const status = answer && !agent.state.errorMessage && (!actorTurn || promptedCurrent) ? "completed" : "blocked";
	const providerError = status === "completed" ? "" : String(agent.state.errorMessage || "").trim();
	const providerFailure = providerError ? classifyProviderFailure(providerError) : null;
	const result: ConversationResult = {
		status,
		message: answer ? "conversation completed" : (agent.state.errorMessage || "conversation returned no answer"),
		answer,
		taskId: sessionId,
		provider,
		model: modelId,
		turns: state.turns,
		toolCalls: 0,
		providerRequests: state.providerRequests,
		reasoningCharacters: state.reasoningCharacters,
		textCharacters: state.textCharacters,
		writtenOutputs: [],
		validationPassed: Boolean(answer),
		...(actorTurn || initializedEnvironment ? { initializationAnswer } : {}),
		...(providerFailure ? {
			failureKind: providerFailure.kind,
			providerError: providerFailure.message,
			providerFailureRetryable: providerFailure.retryable,
		} : {}),
	};
	emit("runner.conversation.result", { session_id: sessionId, status, answer });
	return result;
}

export interface ActorTurnEnvelope {
	initialization: string;
	initializationAnswer: string;
	history: { prompt: string; answer: string }[];
	prompt: string;
}

export function actorTurnEnvelope(prompt: string): ActorTurnEnvelope | null {
	let value: unknown;
	try { value = JSON.parse(prompt); } catch { return null; }
	if (!isRecord(value) || value.schema !== "arcvellum/actor-conversation/v2") return null;
	const history = value.history;
	if (typeof value.initialization !== "string" || !value.initialization.trim()
		|| typeof value.prompt !== "string" || !value.prompt.trim()
		|| typeof value.initialization_answer !== "string"
		|| !Array.isArray(history) || history.length > 16
		|| !history.every((item) => isRecord(item) && typeof item.prompt === "string" && !!item.prompt.trim()
			&& typeof item.answer === "string" && !!item.answer.trim())
		) {
		throw new Error("actor turn requires initialization, prior answers, and current prompt");
	}
	return {
		initialization: value.initialization,
		initializationAnswer: value.initialization_answer,
		history: history as { prompt: string; answer: string }[],
		prompt: value.prompt,
	};
}

export function actorHistoryMessages(turn: ActorTurnEnvelope, model: { api: any; provider: any; id: string }): AgentMessage[] {
	const timestamp = Date.now();
	const user = (content: string): AgentMessage => ({ role: "user", content, timestamp });
	const assistant = (text: string): AgentMessage => ({
		role: "assistant", content: [{ type: "text", text }], api: model.api,
		provider: model.provider, model: model.id, timestamp,
		usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0,
			cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
		stopReason: "stop",
	});
	return turn.history.flatMap((item) => [user(item.prompt), assistant(item.answer)]);
}

export function conversationSystemPrompt(role: NonNullable<WorkerOptions["conversationRole"]>): string {
	if (role === "character-actor" || role === "environment-writer") {
		return "";
	}
	return "You are an ArcVellum role worker. Follow the supplied role contract exactly. You have no tools and no project write access. Return only the requested answer payload.";
}

export function conversationMessages(role: NonNullable<WorkerOptions["conversationRole"]>, prompt: string): string[] {
	if (role === "environment-writer") {
		let payload: unknown;
		try { payload = JSON.parse(prompt); } catch { return [prompt]; }
		if (!isRecord(payload) || payload.schema !== "arcvellum/environment-conversation/v1") return [prompt];
		if (typeof payload.initialization !== "string" || !payload.initialization.trim()
			|| typeof payload.prompt !== "string" || !payload.prompt.trim()) {
			throw new Error("environment conversation requires initialization and scene prompt");
		}
		return [payload.initialization, payload.prompt];
	}
	if (role !== "character-actor") return [prompt];
	let payload: unknown;
	try { payload = JSON.parse(prompt); } catch { throw new Error("character actor requires a conversation envelope"); }
	if (!isRecord(payload) || payload.schema !== "arcvellum/actor-conversation/v1" || !Array.isArray(payload.messages)
		|| payload.messages.length < 2 || !payload.messages.every((item) => typeof item === "string" && item.trim())) {
		throw new Error("character actor requires initialization and subsequent nonempty messages");
	}
	return payload.messages as string[];
}

function emptyState(): WorkerState {
	return {
		completed: false,
		blocked: false,
		blockerReason: "",
		turns: 0,
		toolCalls: 0,
		repairRequests: 0,
		repairReadHandoffs: 0,
		taskContextReads: 0,
		reasoningCharacters: 0,
		reasoningTokens: 0,
		reasoningTokensReported: false,
		providerRequests: 0,
		reasoningEscalations: [],
		reasoningStopReason: "",
		textCharacters: 0,
		readPaths: new Set(),
		writtenPaths: new Set(),
		lastValidation: { passed: false, issues: [] },
		lastToolError: null,
		progressDigests: [],
	};
}

function parseModelId(value: string): [string, string] {
	const separator = value.indexOf("/");
	if (separator <= 0 || separator === value.length - 1) throw new Error("model must use provider/model format");
	return [value.slice(0, separator), value.slice(separator + 1)];
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

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}
