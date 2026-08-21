import { describe, expect, it } from "vitest";
import type { ReasoningBudget, WorkerState } from "../src/contracts.ts";
import {
	providerBudgetSupport,
	reasoningBudgetReceipt,
	reasoningStopReason,
	reasoningThinkingBudgets,
	safeThinkingLevel,
	validateReasoningBudget,
} from "../src/reasoning-budget.ts";

const budget: ReasoningBudget = {
	enabled: true,
	initialLevel: "low",
	maximumLevel: "medium",
	perRequestTokens: 512,
	totalTokens: 2048,
	maxProviderRequests: 4,
	maxEscalations: 1,
	overBudgetAction: "validate_then_stop",
};

describe("reasoning budget", () => {
	it("validates the level range and projects per-request budgets", () => {
		expect(() => validateReasoningBudget(budget)).not.toThrow();
		expect(reasoningThinkingBudgets(budget)).toEqual({ minimal: 128, low: 256, medium: 512, high: 1024 });
		expect(() => validateReasoningBudget({ ...budget, initialLevel: "high" })).toThrow(/exceeds/);
	});

	it("stops at a reported token or provider-request boundary", () => {
		expect(reasoningStopReason(budget, state({ reasoningTokens: 2048, reasoningTokensReported: true }))).toBe(
			"reasoning_token_budget_exhausted",
		);
		expect(reasoningStopReason(budget, state({ providerRequests: 4 }))).toBe("provider_request_budget_exhausted");
		expect(reasoningStopReason(budget, state({ reasoningTokens: 9999, reasoningTokensReported: false }))).toBe("");
	});

	it("does not claim exact provider support without model capability evidence", () => {
		expect(providerBudgetSupport({ reasoning: false }, budget)).toBe("unsupported");
		expect(providerBudgetSupport({ reasoning: true }, budget)).toBe("partial");
		expect(providerBudgetSupport({ reasoning: true, compat: { supportsThinkingTokenBudget: true } }, budget)).toBe("supported");
	});

	it("never upgrades an unsupported requested thinking level", () => {
		const deepSeekLike = {
			reasoning: true,
			thinkingLevelMap: { minimal: null, low: null, medium: null, high: "high", max: "max" },
		};
		expect(safeThinkingLevel(deepSeekLike as never, "low")).toBe("off");
		expect(safeThinkingLevel(deepSeekLike as never, "high")).toBe("high");
		const sparseGatewayModel = {
			reasoning: true,
			thinkingLevelMap: { minimal: null, low: null, high: "high", max: "max" },
		};
		expect(safeThinkingLevel(sparseGatewayModel as never, "low")).toBe("off");
	});

	it("uses the nearest supported lower level when an exact level is absent", () => {
		const bounded = {
			reasoning: true,
			thinkingLevelMap: { off: "none", minimal: "minimal", low: "low", medium: null, high: "high" },
		};
		expect(safeThinkingLevel(bounded as never, "medium")).toBe("low");
	});

	it("uses null when a provider did not report reasoning tokens", () => {
		const receipt = reasoningBudgetReceipt(budget, state({ reasoningCharacters: 120 }), "partial", "off");
		expect(receipt.actual_tokens).toBeNull();
		expect(receipt.actual_characters).toBe(120);
		expect(receipt.requested.initial_level).toBe("low");
		expect(receipt.effective_level).toBe("off");
	});
});

function state(overrides: Partial<WorkerState> = {}): WorkerState {
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
		...overrides,
	};
}
