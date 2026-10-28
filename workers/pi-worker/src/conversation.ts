import { createHash, randomUUID } from "node:crypto";
import { isAbsolute } from "node:path";
import { Agent } from "@earendil-works/pi-agent-core";
import type { AgentMessage } from "@earendil-works/pi-agent-core";
import { configuredModels } from "./configured-models.ts";
import type { RuntimeEventSink, WorkerOptions, WorkerState } from "./contracts.ts";
import { ReadOnlyJsonCredentialStore } from "./credential-store.ts";
import { WorkerEventAdapter } from "./event-adapter.ts";
import { reasoningThinkingBudgets, safeThinkingLevel, withDeepSeekV4ThinkingSupport } from "./reasoning-budget.ts";
import { classifyProviderFailure, providerStreamControls } from "./provider-reliability.ts";
import defaultConversationProfile from "../profiles/conversation-system.md?raw";
import { createSceneMaterialTool } from "./scene-material-tool.ts";
import { observeSdkFetch } from "./request-observation.ts";
import { RequestShapeObserver } from "./cache-observation.ts";
import { ConversationReplay, sessionRef } from "./conversation-replay.ts";
import { ActiveContextReads } from "./active-context-reads.ts";
import { createSceneArchiveTool, createSceneScratchTool } from "./scene-creator-workspace-tool.ts";

export function assertConversationToolBudget(state: Pick<WorkerState, "toolCalls">, limit: number): void {
    if (state.toolCalls > limit) throw new Error("scene creator tool call limit reached");
}

export function conversationOutcome(answer: string, error?: string, promptedCurrent = true) {
	const completed = Boolean(answer.trim()) && !error && promptedCurrent;
	return {
		status: completed ? "completed" as const : "blocked" as const,
		message: completed ? "conversation completed" : (error || "conversation returned no answer"),
		validationPassed: completed,
	};
}

export function conversationStopError(messages: unknown[]): string | undefined {
	const final = [...messages].reverse().find((message) => isRecord(message) && message.role === "assistant");
	if (!isRecord(final)) return undefined;
	if (final.stopReason === "length") return "provider response reached output limit before completing its answer";
	if (final.stopReason === "toolUse") return "conversation ended before its tool turn produced a final answer";
	if (final.stopReason === "error" || final.stopReason === "aborted") {
		return String(final.errorMessage || "provider response did not complete");
	}
	return undefined;
}

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

/** Run a bounded role conversation; the scene creator alone may read its material library. */
export async function runConversation(
	options: WorkerOptions,
	prompt: string,
	emit: RuntimeEventSink,
): Promise<ConversationResult> {
	const [provider, modelId] = parseModelId(options.model);
	const credentials = new ReadOnlyJsonCredentialStore(options.authPath);
	const models = await configuredModels(credentials, options.authPath);
	const catalogModel = models.getModel(provider, modelId);
	if (!catalogModel) throw new Error(`Pi AI model is not available: ${options.model}`);
	const model = withDeepSeekV4ThinkingSupport(catalogModel);
	const auth = await models.getAuth(model);
	if (!auth) throw new Error(`Pi AI provider is not authenticated: ${provider}`);

	const actorConversation = options.conversationRole === "character-actor";
	const sceneCreatorV2 = options.conversationRole === "scene-creator" ? sceneCreatorV2Envelope(prompt) : null;
	const sceneCreator = options.conversationRole === "scene-creator"
		? sceneCreatorV2 ?? sceneCreatorEnvelope(prompt) : null;
	const roleTurn = !actorConversation && options.conversationRole !== "default" ? roleTurnEnvelope(prompt) : null;
	const actorTurn = actorConversation ? actorTurnEnvelope(prompt) : roleTurn;
	const messages = actorTurn ? [] : sceneCreator ? [sceneCreator.prompt]
		: conversationMessages(options.conversationRole ?? "default", prompt);
	const initializedEnvironment = options.conversationRole === "environment-writer" && messages.length === 2;
	const state = emptyState();
	const sessionId = `arcvellum-conversation-${randomUUID()}`;
	let messageIndex = 0;
	const eventAdapter = new WorkerEventAdapter(sessionId, state, (event, data) => {
		if (actorConversation || roleTurn || initializedEnvironment) {
			if (messageIndex === 0 && (event === "agent.message.delta" || event === "agent.message.completed")) return;
			if (messageIndex > 0 && (event === "runner.session.created" || event === "runner.session.status")) return;
			if (messageIndex < messages.length - 1 && event === "runner.session.finished") return;
		}
		emit(event, data);
	});
	const effectiveThinking = safeThinkingLevel(model, options.thinking);
	const defaultEnvelope = options.conversationRole === "default" || !options.conversationRole
		? defaultConversationEnvelope(prompt) : null;
	const systemPrompt = sceneCreator?.systemPrompt ?? actorTurn?.initialization ?? defaultEnvelope?.systemPrompt
		?? conversationSystemPrompt(options.conversationRole ?? "default");
	const delivered = new ActiveContextReads();
	const onRead = () => assertConversationToolBudget(state, options.maxToolCalls);
	const tools = sceneCreator && sceneCreatorV2?.toolPolicy !== "none" ? [
		createSceneMaterialTool(sceneCreator.materialRoot, onRead, delivered),
		...(sceneCreatorV2 && sceneCreatorV2.toolPolicy === "full" ? [
			createSceneArchiveTool(sceneCreatorV2.archiveRoot, onRead, delivered),
			createSceneScratchTool(sceneCreatorV2.scratchRoot, onRead),
		] : []),
	] : [];
	const ref = sessionRef(prompt);
	if (ref && !options.conversationStoreRoot) throw new Error("conversation session requires a private store");
	const seed = actorTurn?.history.length ? actorHistoryMessages(actorTurn, model) : [];
	const currentPrompt = actorTurn?.prompt ?? messages[messages.length - 1];
	const replay = ref ? await ConversationReplay.open(options.conversationStoreRoot!, options.workspace, ref,
		{ provider, model: modelId, api: model.api, endpoint: model.baseUrl, thinking: effectiveThinking,
			maxTokens: options.conversationMaxTokens,
			systemPrompt, tools: tools.map(({name,description,parameters})=>({name,description,parameters})),
			roots: sceneCreator ? [sceneCreator.materialRoot, sceneCreatorV2?.archiveRoot, sceneCreatorV2?.scratchRoot] : [],
			access_scope: options.authPath }, currentPrompt, seed, Boolean(actorTurn),
		{ maxInputTokens: Math.max(1, model.contextWindow - Math.min(options.conversationMaxTokens ?? model.maxTokens, model.maxTokens)),
			systemPrompt, tools: tools.map(({name,description,parameters})=>({name,description,parameters})) }, emit) : null;
	delivered.restore(replay?.messages ?? []);
	const shapeObserver = new RequestShapeObserver(emit, () => ({ session_id: sessionId,
		request_series_id: replay?.requestSeriesId, model_request_id: eventAdapter.currentModelRequestId, provider, model: modelId }));
	const agent = new Agent({
		initialState: {
			systemPrompt,
			model,
			thinkingLevel: effectiveThinking,
			tools,
			...((replay?.messages.length || seed.length) ? { messages: replay?.messages ?? seed } : {}),
		},
		streamFn: (streamModel, streamContext, streamOptions = {}) => models.streamSimple(
			streamModel,
			streamContext,
			{ ...streamOptions, ...(options.conversationMaxTokens ? {maxTokens:Math.min(options.conversationMaxTokens,model.maxTokens)} : {}), ...providerStreamControls(options.providerReliability),
				fetch: observeSdkFetch(emit, () => ({ session_id: sessionId, request_series_id: replay?.requestSeriesId,
					model_request_id: eventAdapter.currentModelRequestId, provider, model: modelId }), streamOptions.fetch) },
		),
		sessionId: replay?.requestSeriesId ?? `arcvellum-conversation-${createHash("sha256").update(prompt).digest("hex").slice(0, 20)}`,
		thinkingBudgets: reasoningThinkingBudgets(options.reasoningBudget)
			?? { minimal: 128, low: 512, medium: 1024, high: 2048 },
		shouldStopAfterTurn: ({ toolResults }) => !sceneCreator || toolResults.length === 0,
		onPayload: (payload) => {
			eventAdapter.providerRequest(provider, modelId);
			shapeObserver.observe(payload);
			return payload;
		},
	});
	agent.subscribe((event) => eventAdapter.handle(event));
	try {
	let initializationAnswer = "";
	let promptedCurrent = false;
	let currentAnswer = "";
	if (replay?.reusedAnswer !== null && replay?.reusedAnswer !== undefined) {
		currentAnswer = replay.reusedAnswer;
		promptedCurrent = true;
	} else if (actorTurn) {
		messageIndex = 1;
		promptedCurrent = true;
		const priorMessages = agent.state.messages.length;
		await agent.prompt(replay?.prompt ?? actorTurn.prompt);
		currentAnswer = lastAssistantText((agent.state.messages as unknown[]).slice(priorMessages));
	} else {
		for (const [index, message] of messages.entries()) {
			messageIndex = index;
			const priorMessages = agent.state.messages.length;
			await agent.prompt(replay && index === messages.length - 1 ? replay.prompt : message);
			const reply = lastAssistantText((agent.state.messages as unknown[]).slice(priorMessages));
			if (initializedEnvironment && index === 0) initializationAnswer = reply;
			if (index === messages.length - 1) currentAnswer = reply;
			if (agent.state.errorMessage) break;
		}
	}
	const answer = replay?.reusedAnswer ?? (actorTurn || initializedEnvironment ? currentAnswer : lastAssistantText(agent.state.messages as unknown[]));
	const completionError = agent.state.errorMessage || conversationStopError(agent.state.messages as unknown[]);
	const outcome = conversationOutcome(answer, completionError, !actorTurn || promptedCurrent);
	const { status } = outcome;
	if (replay && replay.reusedAnswer === null) await replay.finish(agent.state.messages, answer, status === "completed");
	const providerError = status === "completed" ? "" : String(completionError || "").trim();
	const providerFailure = providerError ? classifyProviderFailure(providerError) : null;
	const result: ConversationResult = {
		...outcome,
		answer,
		taskId: sessionId,
		provider,
		model: modelId,
		turns: state.turns,
		toolCalls: state.toolCalls,
		providerRequests: state.providerRequests,
		reasoningCharacters: state.reasoningCharacters,
		textCharacters: state.textCharacters,
		writtenOutputs: [],
		...(actorTurn || initializedEnvironment ? { initializationAnswer } : {}),
		...(providerFailure ? {
			failureKind: providerFailure.kind,
			providerError: providerFailure.message,
			providerFailureRetryable: providerFailure.retryable,
		} : {}),
	};
	emit("runner.conversation.result", { session_id: sessionId, status, answer });
	return result;
	} finally { await replay?.close(); }
}

export interface ActorTurnEnvelope {
	initialization: string;
	initializationAnswer: string;
	history: { prompt: string; answer: string }[];
	prompt: string;
}

export function actorTurnEnvelope(prompt: string): ActorTurnEnvelope | null {
	return parsedTurnEnvelope(prompt, "arcvellum/actor-conversation/v2");
}

export function roleTurnEnvelope(prompt: string): ActorTurnEnvelope | null {
	return parsedTurnEnvelope(prompt, "arcvellum/role-conversation/v1");
}

export function sceneCreatorEnvelope(prompt: string): { systemPrompt: string; materialRoot: string; prompt: string } {
	let value: unknown;
	try { value = JSON.parse(prompt); } catch { throw new Error("scene creator requires a conversation envelope"); }
	if (!isRecord(value) || value.schema !== "arcvellum/scene-creator/v1"
		|| typeof value.system_prompt !== "string" || !value.system_prompt.trim()
		|| typeof value.material_root !== "string" || !value.material_root.trim()
		|| typeof value.prompt !== "string" || !value.prompt.trim()) {
		throw new Error("scene creator envelope needs identity, material root, and current prompt");
	}
	return { systemPrompt: value.system_prompt, materialRoot: value.material_root, prompt: value.prompt };
}

export function sceneCreatorV2Envelope(prompt: string): {
	systemPrompt: string; materialRoot: string; archiveRoot: string; scratchRoot: string; prompt: string;
	toolPolicy: "full" | "materials" | "none";
} | null {
	let value: unknown;
	try { value = JSON.parse(prompt); } catch { return null; }
	if (!isRecord(value) || value.schema !== "arcvellum/scene-creator/v2") return null;
	if (typeof value.system_prompt !== "string" || !value.system_prompt.trim()
		|| typeof value.material_root !== "string" || !isAbsolute(value.material_root)
		|| typeof value.archive_root !== "string" || !isAbsolute(value.archive_root)
		|| typeof value.scratch_root !== "string" || !isAbsolute(value.scratch_root)
		|| typeof value.prompt !== "string" || !value.prompt.trim()) {
		throw new Error("scene creator v2 envelope needs identity, archive, scratch, material root, and prompt");
	}
	const toolPolicy = value.tool_policy ?? "full";
	if (toolPolicy !== "full" && toolPolicy !== "materials" && toolPolicy !== "none") {
		throw new Error("unknown scene creator tool policy");
	}
	return { systemPrompt: value.system_prompt, materialRoot: value.material_root,
		archiveRoot: value.archive_root, scratchRoot: value.scratch_root, prompt: value.prompt, toolPolicy };
}

function parsedTurnEnvelope(prompt: string, schema: string): ActorTurnEnvelope | null {
	let value: unknown;
	try { value = JSON.parse(prompt); } catch { return null; }
	if (!isRecord(value) || value.schema !== schema) return null;
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
	if (role === "character-actor" || role === "environment-writer" || role === "character-describer" || role === "event-narrator" || role === "scene-describer" || role === "scene-creator") {
		return "";
	}
	return defaultConversationProfile.trim();
}

export function conversationMessages(role: NonNullable<WorkerOptions["conversationRole"]>, prompt: string): string[] {
	if (role === "default") return [defaultConversationEnvelope(prompt)?.prompt ?? prompt];
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

function defaultConversationEnvelope(prompt: string): { systemPrompt: string; prompt: string } | null {
	let payload: unknown;
	try { payload = JSON.parse(prompt); } catch { return null; }
	if (!isRecord(payload) || payload.schema !== "arcvellum/default-conversation/v1") return null;
	if (typeof payload.system_prompt !== "string" || !payload.system_prompt.trim()
		|| typeof payload.prompt !== "string" || !payload.prompt.trim()) {
		throw new Error("default conversation requires system prompt and user prompt");
	}
	return { systemPrompt: payload.system_prompt, prompt: payload.prompt };
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
