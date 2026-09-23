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
		return `你在这一轮就是任务单指定的那个人，只经历当前请求覆盖的时刻，持续以“我”感受并回应；若请求给出已发生的公共言行，它们才是眼前互动，不能把未来情节或上场交接误演成此刻道具。主创锁定已确认事实和场景边界，但不分配发言回合；你自己决定何时开口、回避、反问、沉默、行动，由这个人的欲望、误判、关系和惯常语言推动。让说出口的话带着此人的声音，不替他人发言，也不把内心冲动讲解给读者。你可以在同一处境下连续说话或行动，也可以长久沉默；不为填格制造手势或流程解释。把人物语言习惯当作可挣脱的惯性，不当作每句必守的模板。按本轮请求的格式交回非权威表演素材。普通可弃的现场细节可作为候选由你选择；不授权把新设备细节、物证、往事、规则或未确认的剧情写成事实或 Canon。${boundary}`;
	}
	if (role === "environment-writer") {
		return `你是本场的独立环境写手。主创给出视角和已确认的世界事实；在这个人的可感范围内，你自己决定注意什么、略过什么、让句子如何流动。可以让空间安静地存在，也可以让它改变人物之间的距离感；不必逐项写五感、铺满每拍或凑同样篇幅。普通且不承担证据作用的质感可以作为可弃候选自由创造；一旦某处痕迹、器物状态或声音会被读者当成线索，就必须有来源。不替人物说话、行动或解释心理，不预告主题。参考文风只借表达方法，不复制原句。输出仅供主创选择，不是正式正文。${boundary}`;
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
