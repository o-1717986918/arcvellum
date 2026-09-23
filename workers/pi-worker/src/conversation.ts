import { createHash } from "node:crypto";
import { Agent } from "@earendil-works/pi-agent-core";
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

	const state = emptyState();
	const sessionId = `arcvellum-conversation-${createHash("sha256").update(prompt).digest("hex").slice(0, 20)}`;
	const eventAdapter = new WorkerEventAdapter(sessionId, state, emit);
	const effectiveThinking = safeThinkingLevel(model, options.thinking);
	const systemPrompt = conversationSystemPrompt(options.conversationRole ?? "default");
	const agent = new Agent({
		initialState: {
			systemPrompt,
			model,
			thinkingLevel: effectiveThinking,
			tools: [],
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
	await agent.prompt(prompt);
	const answer = lastAssistantText(agent.state.messages as unknown[]);
	const status = answer ? "completed" : "blocked";
	const providerError = answer ? "" : String(agent.state.errorMessage || "").trim();
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
		...(providerFailure ? {
			failureKind: providerFailure.kind,
			providerError: providerFailure.message,
			providerFailureRetryable: providerFailure.retryable,
		} : {}),
	};
	emit("runner.conversation.result", { session_id: sessionId, status, answer });
	return result;
}

export function conversationSystemPrompt(role: NonNullable<WorkerOptions["conversationRole"]>): string {
	const boundary = "You have no tools and no project write access. Return only the requested answer payload. Never create canon or finalized prose.";
	if (role === "character-actor") {
		return `你不是讨论人物的助手。收到角色任务单后，你在这一轮就是任务单指定的那个人；在心里只用“我”的位置感受所知、误判、欲望、恐惧、眼前的人和当下压力。先从我未说出口的冲动进入，再落到我做的动作，最后才让语言出口。剧情事实与结果已锁定，但这一轮采用什么微观话术和姿态由我自己决定；任务单不是台词清单。说话要有我独有的词域、句法节奏、称呼、礼貌边界与受压变调，不复读人物卡示例，也不照念导演的分析术语。不替别人说话，不决定新情节，不补造事实。private_impulse 是我未说出口的短促念头，first_person_action 是我亲手做的动作，spoken 是我实际说出口的话；前两项保持第一人称，不写旁观者解说。只交一个候选，不附加备选或解释。JSON 仅是交付容器；这些都只是可弃用候选，不是正式正文。${boundary}`;
	}
	if (role === "environment-writer") {
		return `You are an ArcVellum scene-environment writer. Compose bounded candidate description from the assigned viewpoint, physical space, action and style reference. Vary sentence motion; allow meaningful aesthetic dwell. Do not invent plot, canon, locations, or character dialogue. Your output is disposable candidate material, not final prose. ${boundary}`;
	}
	return "You are an ArcVellum role worker. Follow the supplied role contract exactly. You have no tools and no project write access. Return only the requested answer payload.";
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
