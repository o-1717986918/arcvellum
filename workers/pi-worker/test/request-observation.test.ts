import { describe, expect, it, vi } from "vitest";
import { observeSdkFetch } from "../src/request-observation.ts";
import { streamSimple } from "@earendil-works/pi-ai/api/openai-completions";
import { builtinModels } from "@earendil-works/pi-ai/providers/all";

describe("SDK HTTP attempt observation", () => {
	it("records a 402 once and leaves interrupted stream usage unknown",async () => {
		for (const response of [new Response("insufficient balance",{status:402}),
			new Response(new ReadableStream({start(controller){controller.error(new Error("simulated stream interruption"));}}),
				{headers:{"Content-Type":"text/event-stream"}})]) {
			const events:Array<{event:string;data:Record<string,unknown>}>=[];
			const transport=vi.fn(async()=>response);
			const fetch=observeSdkFetch((event,data={})=>events.push({event,data}),()=>({model_request_id:"test"}),transport);
			const output=await streamSimple(builtinModels().getModel("deepseek","deepseek-v4-flash")!,
				{messages:[{role:"user",content:"offline",timestamp:0}]},{apiKey:"offline",fetch,maxRetries:0}).result();
			expect(output.stopReason).toBe("error");
			expect(output.usage.totalTokens).toBe(0);
			expect(events.filter(row=>row.event==="runner.http.attempt.started")).toHaveLength(1);
			expect(transport).toHaveBeenCalledTimes(1);
		}
	});
	it("preserves the response stream and logs no URL, key, or request body", async () => {
		const events: unknown[] = [];
		const response = new Response("kept intact");
		const transport = vi.fn(async () => response);
		const fetch = observeSdkFetch((event, data) => events.push({ event, data }), () => ({ model_request_id: "one" }), transport);
		expect(await fetch("https://example.invalid", { body: "secret", headers: { Authorization: "secret" } })).toBe(response);
		expect(await response.text()).toBe("kept intact");
		expect(JSON.stringify(events)).not.toMatch(/secret|example/);
		expect(events).toHaveLength(2);
	});

	it("counts the SDK retry attempts separately from one logical model request", async () => {
		const events: Array<{event: string; data: Record<string, unknown>}> = [];
		const transport = vi.fn().mockResolvedValueOnce(new Response("unavailable", { status: 503 }))
			.mockResolvedValueOnce(new Response('data: {"choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}],"usage":{"prompt_tokens":2,"completion_tokens":1}}\n\ndata: [DONE]\n\n',
				{ headers: { "Content-Type": "text/event-stream" } }));
		const fetch = observeSdkFetch((event, data = {}) => events.push({ event, data }), () => ({ model_request_id: "same" }), transport);
		const response = streamSimple(builtinModels().getModel("deepseek", "deepseek-v4-flash")!,
			{ messages: [{ role: "user", content: "offline", timestamp: 0 }] },
			{ apiKey: "offline-test-key", fetch, maxRetries: 1, maxRetryDelayMs: 1 });
		await response.result();
		const started = events.filter(e => e.event === "runner.http.attempt.started");
		expect(started).toHaveLength(2);
		expect(new Set(started.map(e => e.data.http_attempt_id)).size).toBe(2);
		expect(started.every(e => e.data.model_request_id === "same")).toBe(true);
		expect(transport).toHaveBeenCalledTimes(2);
	});

	it("records a transport failure without leaking its message", async () => {
		const events: unknown[] = [];
		const fetch = observeSdkFetch((event, data) => events.push({ event, data }), () => ({}),
			async () => { throw new Error("credential-bearing error"); });
		await expect(fetch("https://example.invalid")).rejects.toThrow();
		expect(JSON.stringify(events)).toContain("transport-error");
		expect(JSON.stringify(events)).not.toContain("credential");
	});
});
