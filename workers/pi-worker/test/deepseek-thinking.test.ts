import { describe, expect, it, vi } from "vitest";
import { builtinModels } from "@earendil-works/pi-ai/providers/all";
import { streamSimple } from "@earendil-works/pi-ai/api/openai-completions";
import { safeThinkingLevel, withDeepSeekV4ThinkingSupport } from "../src/reasoning-budget.ts";

describe("DeepSeek V4 low thinking compatibility", () => {
	it("preserves the catalog while making low visible to the selector and SDK", () => {
		const original = builtinModels().getModel("deepseek", "deepseek-v4-flash")!;
		const model = withDeepSeekV4ThinkingSupport(original);
		expect(original.thinkingLevelMap?.low).toBeNull();
		expect(model.thinkingLevelMap?.low).toBe("low");
		expect(safeThinkingLevel(model, "low")).toBe("low");
		expect(safeThinkingLevel(model, "off")).toBe("off");
		expect(safeThinkingLevel(model, "medium")).toBe("high");
		expect(model.id).toBe(original.id);
		expect(model.baseUrl).toBe(original.baseUrl);
		expect(model.cost).toBe(original.cost);
	});

	it("leaves older DeepSeek and other providers' capability claims alone", () => {
		const original = builtinModels().getModel("deepseek", "deepseek-v4-flash")!;
		for (const model of [{ ...original, id: "deepseek-chat" }, { ...original, provider: "other" }]) {
			expect(withDeepSeekV4ThinkingSupport(model)).toBe(model);
			expect(safeThinkingLevel(model, "low")).toBe("off");
		}
	});

	it.each(["low", "off"] as const)("serializes %s through the actual SDK without sending a request", async (level) => {
		const model = withDeepSeekV4ThinkingSupport(builtinModels().getModel("deepseek", "deepseek-v4-flash")!);
		let payload: Record<string, unknown> | undefined;
		const fetch = vi.fn(async () => { throw new Error("network forbidden in this test"); });
		const response = streamSimple(model, {
			messages: [{ role: "user", content: "Offline payload verification.", timestamp: 0 }],
		}, {
			apiKey: "offline-test-key", reasoning: safeThinkingLevel(model, level), fetch,
			onPayload: (value) => { payload = value as Record<string, unknown>; throw new Error("stop before network"); },
		});
		await response.result();
		expect(payload?.thinking).toEqual({ type: level === "off" ? "disabled" : "enabled" });
		expect(payload?.reasoning_effort).toBe(level === "off" ? undefined : "low");
		expect(payload?.model).toBe("deepseek-v4-flash");
		expect(payload).not.toHaveProperty("thinking_token_budget");
		expect(fetch).not.toHaveBeenCalled();
	});
});
