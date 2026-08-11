import { getSupportedThinkingLevels, type Model } from "@earendil-works/pi-ai";
import type { ReasoningBudget, ReasoningBudgetReceipt, ThinkingLevel, WorkerState } from "./contracts.ts";

const LEVELS: ThinkingLevel[] = ["off", "minimal", "low", "medium", "high", "xhigh", "max"];

export function validateReasoningBudget(budget: ReasoningBudget): void {
	if (!budget.enabled) return;
	if (levelIndex(budget.initialLevel) > levelIndex(budget.maximumLevel)) {
		throw new Error("initial thinking level exceeds maximum thinking level");
	}
	for (const [name, value] of Object.entries({
		perRequestTokens: budget.perRequestTokens,
		totalTokens: budget.totalTokens,
		maxProviderRequests: budget.maxProviderRequests,
	})) {
		if (!Number.isInteger(value) || value <= 0) throw new Error(`${name} must be a positive integer`);
	}
	if (!Number.isInteger(budget.maxEscalations) || budget.maxEscalations < 0) {
		throw new Error("maxEscalations must be a non-negative integer");
	}
}

export function reasoningThinkingBudgets(budget: ReasoningBudget): Record<"minimal" | "low" | "medium" | "high", number> | undefined {
	if (!budget.enabled) return undefined;
	return {
		minimal: budget.perRequestTokens,
		low: budget.perRequestTokens,
		medium: budget.perRequestTokens,
		high: budget.perRequestTokens,
	};
}

export function safeThinkingLevel(
	model: Pick<Model<any>, "reasoning" | "thinkingLevelMap">,
	requested: ThinkingLevel,
): ThinkingLevel {
	const supported = getSupportedThinkingLevels(model as Model<any>) as ThinkingLevel[];
	const requestedIndex = levelIndex(requested);
	for (let index = requestedIndex; index >= 0; index -= 1) {
		const candidate = LEVELS[index];
		if (supported.includes(candidate)) return candidate;
	}
	throw new Error(`model cannot safely satisfy requested thinking level: ${requested}`);
}

export function providerBudgetSupport(
	model: Pick<Model<any>, "reasoning" | "compat">,
	budget: ReasoningBudget,
): ReasoningBudgetReceipt["provider_support"] {
	if (!budget.enabled) return "unknown";
	if (!model.reasoning || budget.initialLevel === "off") return "unsupported";
	const compat = model.compat as Record<string, unknown> | undefined;
	return compat?.supportsThinkingTokenBudget === true ? "supported" : "partial";
}

export function reasoningStopReason(budget: ReasoningBudget, state: WorkerState): string {
	if (!budget.enabled) return "";
	if (state.providerRequests >= budget.maxProviderRequests) return "provider_request_budget_exhausted";
	if (state.reasoningTokensReported && state.reasoningTokens >= budget.totalTokens) {
		return "reasoning_token_budget_exhausted";
	}
	return "";
}

export function reasoningBudgetReceipt(
	budget: ReasoningBudget,
	state: WorkerState,
	providerSupport: ReasoningBudgetReceipt["provider_support"],
	effectiveLevel: ThinkingLevel,
): ReasoningBudgetReceipt {
	return {
		requested: {
			enabled: budget.enabled,
			initial_level: budget.initialLevel,
			maximum_level: budget.maximumLevel,
			per_request_tokens: budget.perRequestTokens,
			total_tokens: budget.totalTokens,
			max_provider_requests: budget.maxProviderRequests,
			max_escalations: budget.maxEscalations,
			over_budget_action: budget.overBudgetAction,
		},
		effective_level: effectiveLevel,
		provider_support: providerSupport,
		actual_tokens: state.reasoningTokensReported ? state.reasoningTokens : null,
		actual_characters: state.reasoningCharacters,
		provider_requests: state.providerRequests,
		escalations: [...state.reasoningEscalations],
		stop_reason: state.reasoningStopReason,
	};
}

function levelIndex(level: ThinkingLevel): number {
	return LEVELS.indexOf(level);
}
