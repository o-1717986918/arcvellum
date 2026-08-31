import { createHash } from "node:crypto";
import { Agent } from "@earendil-works/pi-agent-core";
import { builtinModels } from "@earendil-works/pi-ai/providers/all";
import type { RuntimeEventSink, WorkerOptions, WorkerState } from "./contracts.ts";
import { ReadOnlyJsonCredentialStore } from "./credential-store.ts";
import { WorkerEventAdapter } from "./event-adapter.ts";
import { reasoningThinkingBudgets, safeThinkingLevel } from "./reasoning-budget.ts";
import { providerStreamControls } from "./provider-reliability.ts";

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
	const agent = new Agent({
		initialState: {
			systemPrompt: "You are an ArcVellum role worker. Follow the supplied role contract exactly. You have no tools and no project write access. Return only the requested answer payload.",
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
	};
	emit("runner.conversation.result", { session_id: sessionId, status, answer });
	return result;
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
