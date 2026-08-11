import { describe, expect, it } from "vitest";
import type { AgentEvent } from "@earendil-works/pi-agent-core";
import type { WorkerState } from "../src/contracts.ts";
import { WorkerEventAdapter } from "../src/event-adapter.ts";

function state(): WorkerState {
	return {
		completed: false,
		blocked: false,
		blockerReason: "",
		turns: 0,
		toolCalls: 0,
		repairRequests: 0,
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

describe("WorkerEventAdapter", () => {
	it("coalesces text deltas and closes reasoning after an earlier activity flush", () => {
		const workerState = state();
		const events: Array<{ event: string; data: Record<string, unknown> }> = [];
		const adapter = new WorkerEventAdapter("session", workerState, (event, data = {}) => {
			events.push({ event, data });
		});

		adapter.handle(messageUpdate("thinking_delta", "x".repeat(600)));
		for (let index = 0; index < 20; index += 1) adapter.handle(messageUpdate("text_delta", "片段"));
		adapter.handle(messageEnd());

		const names = events.map((item) => item.event);
		expect(names.filter((item) => item === "runner.reasoning.activity")).toHaveLength(1);
		expect(names.filter((item) => item === "runner.reasoning.completed")).toHaveLength(1);
		expect(names.filter((item) => item === "agent.message.delta")).toHaveLength(1);
		expect(events.find((item) => item.event === "agent.message.delta")?.data.delta_events).toBe(20);
		expect(workerState.reasoningCharacters).toBe(600);
		expect(workerState.textCharacters).toBe(40);
	});

	it("records provider requests and reported reasoning tokens without storing reasoning text", () => {
		const workerState = state();
		const adapter = new WorkerEventAdapter("session", workerState, () => undefined);
		adapter.providerRequest("fixture", "model");
		adapter.handle({
			type: "message_end",
			message: { role: "assistant", usage: { reasoning: 37, cost: {} }, content: [] },
		} as unknown as AgentEvent);

		expect(workerState.providerRequests).toBe(1);
		expect(workerState.reasoningTokens).toBe(37);
		expect(workerState.reasoningTokensReported).toBe(true);
	});

	it("records a bounded tool error reason and clears it after a successful tool call", () => {
		const workerState = state();
		const events: Array<{ event: string; data: Record<string, unknown> }> = [];
		const adapter = new WorkerEventAdapter("session", workerState, (event, data = {}) => {
			events.push({ event, data });
		});

		adapter.handle({
			type: "tool_execution_end",
			toolCallId: "denied",
			toolName: "read_authorized_source",
			result: { content: [{ type: "text", text: "source is not exact-on-demand for this task\nC:\\private\\file.json" }] },
			isError: true,
		} as unknown as AgentEvent);

		expect(workerState.lastToolError).toEqual({
			tool: "read_authorized_source",
			reason: "source is not exact-on-demand for this task <redacted-path>",
		});
		expect(events.at(-1)).toEqual({
			event: "tool.denied",
			data: {
				tool: "read_authorized_source",
				tool_use_id: "denied",
				status: "error",
				reason: "source is not exact-on-demand for this task <redacted-path>",
			},
		});

		adapter.handle({
			type: "tool_execution_end",
			toolCallId: "completed",
			toolName: "read_task_context",
			result: { content: [] },
			isError: false,
		} as unknown as AgentEvent);
		expect(workerState.lastToolError).toBeNull();
	});
});

function messageUpdate(type: string, delta: string): AgentEvent {
	return {
		type: "message_update",
		message: { role: "assistant" },
		assistantMessageEvent: { type, delta },
	} as unknown as AgentEvent;
}

function messageEnd(): AgentEvent {
	return {
		type: "message_end",
		message: { role: "assistant", usage: {}, content: [] },
	} as unknown as AgentEvent;
}
