import { describe, expect, it } from "vitest";
import { createFauxCore, fauxAssistantMessage, fauxToolCall } from "@earendil-works/pi-ai/providers/faux";
import { runProjectAgentTurn, type ProjectAgentStart } from "../src/project-agent.ts";
import {
	envelope,
	MAX_BRIDGE_FRAME_BYTES,
	parseEnvelopeLine,
	ProjectToolBridge,
	type BridgeEnvelope,
} from "../src/project-agent-protocol.ts";

describe("Project Agent bridge protocol", () => {
	it("parses the versioned JSONL envelope and rejects malformed frames", () => {
		const value = envelope("turn.start", "turn-1", { prompt: "hello" }, "message-1");
		expect(parseEnvelopeLine(JSON.stringify(value))).toEqual(value);
		expect(() => parseEnvelopeLine("not-json")).toThrow("valid JSON");
		expect(() => parseEnvelopeLine(JSON.stringify({ ...value, schema: "legacy" }))).toThrow("unsupported");
		expect(() => parseEnvelopeLine("x".repeat(MAX_BRIDGE_FRAME_BYTES + 1))).toThrow("exceeds");
	});

	it("completes one scripted Pi tool roundtrip before returning visible text", async () => {
		const faux = createFauxCore({
			provider: "arcvellum-faux",
			models: [{ id: "project-agent-test", reasoning: false }],
		});
		faux.setResponses([
			fauxAssistantMessage(
				fauxToolCall("project_overview", { focus: "progress" }, { id: "model-tool-1" }),
				{ stopReason: "toolUse" },
			),
			fauxAssistantMessage("第一章正在审查，当前没有阻断。"),
		]);
		const outbound: BridgeEnvelope[] = [];
		let bridge: ProjectToolBridge;
		const write = (value: BridgeEnvelope) => {
			outbound.push(value);
			if (value.type !== "tool.call") return;
			queueMicrotask(() => bridge.receive(envelope("tool.result", "turn-1", {
				request_id: value.payload.request_id,
				name: value.payload.name,
				ok: true,
				result: { chapter: 1, stage: "review", blocked: false },
			})));
		};
		bridge = new ProjectToolBridge("turn-1", write, 1_000);
		const start: ProjectAgentStart = {
			sessionId: "session-1",
			turnId: "turn-1",
			prompt: "项目现在进行到哪里？",
			systemPrompt: "回答用户问题；需要事实时调用工具。",
			allowedTools: ["project_overview"],
			maxTurns: 4,
			maxToolCalls: 2,
		};

		const result = await runProjectAgentTurn(
			start,
			{ model: faux.getModel(), streamFn: faux.streamSimple },
			bridge,
			write,
		);

		expect(result.status).toBe("completed");
		expect(result.answer).toBe("第一章正在审查，当前没有阻断。");
		expect(result.toolCalls).toBe(1);
		expect(faux.state.callCount).toBe(2);
		expect(outbound.filter((item) => item.type === "tool.call")).toHaveLength(1);
		expect(outbound.filter((item) => item.type === "agent.event" && item.payload.event === "text.delta")).toHaveLength(1);
		expect(bridge.pendingCount).toBe(0);
	});

	it("exposes bounded autonomous write tools", async () => {
		const faux = createFauxCore({
			provider: "arcvellum-faux-actions",
			models: [{ id: "project-agent-action-test", reasoning: false }],
		});
		faux.setResponses([
			fauxAssistantMessage(
				fauxToolCall("project_record_direction", {
					message: "主角拒绝王位",
				}),
				{ stopReason: "toolUse" },
			),
			fauxAssistantMessage("这条方向已经记录。"),
		]);
		const outbound: BridgeEnvelope[] = [];
		let bridge: ProjectToolBridge;
		const write = (value: BridgeEnvelope) => {
			outbound.push(value);
			if (value.type !== "tool.call") return;
			queueMicrotask(() => bridge.receive(envelope("tool.result", "turn-action", {
				request_id: value.payload.request_id,
				name: value.payload.name,
				ok: true,
				result: { ok: true, receipt: { token: "receipt-1" } },
			})));
		};
		bridge = new ProjectToolBridge("turn-action", write, 1_000);

		const result = await runProjectAgentTurn(
			{
				sessionId: "session-action",
				turnId: "turn-action",
				prompt: "请记录为创作方向：主角拒绝王位。",
				systemPrompt: "在领域门禁内自主执行项目操作。",
				allowedTools: ["project_record_direction"],
				maxTurns: 3,
				maxToolCalls: 2,
			},
			{ model: faux.getModel(), streamFn: faux.streamSimple },
			bridge,
			write,
		);

		expect(result.status).toBe("completed");
		expect(result.toolCalls).toBe(1);
		expect(outbound.find((item) => item.type === "tool.call")?.payload.name).toBe("project_record_direction");
	});

	it("rejects timed out and cancelled tool requests without leaking pending calls", async () => {
		const timed = new ProjectToolBridge("turn-timeout", () => undefined, 5);
		await expect(timed.request("project_overview", {})).rejects.toThrow("timed out");
		expect(timed.pendingCount).toBe(0);

		const waiting = new ProjectToolBridge("turn-cancel", () => undefined, 1_000);
		const request = waiting.request("project_overview", {});
		waiting.cancel("turn cancelled");
		await expect(request).rejects.toMatchObject({ name: "AbortError" });
		expect(waiting.pendingCount).toBe(0);
	});

	it("exposes search and creation observation as separate bounded tools", async () => {
		const faux = createFauxCore({
			provider: "arcvellum-faux",
			models: [{ id: "project-agent-tools", reasoning: false }],
		});
		faux.setResponses([
			fauxAssistantMessage(fauxToolCall("project_search", { query: "地图", limit: 5 }), { stopReason: "toolUse" }),
			fauxAssistantMessage(fauxToolCall("creation_observe", { focus: "active" }), { stopReason: "toolUse" }),
			fauxAssistantMessage("资料已找到，创作现场正在运行。"),
		]);
		let bridge: ProjectToolBridge;
		const calls: string[] = [];
		const write = (value: BridgeEnvelope) => {
			if (value.type !== "tool.call") return;
			calls.push(String(value.payload.name));
			queueMicrotask(() => bridge.receive(envelope("tool.result", "turn-tools", {
				request_id: value.payload.request_id,
				name: value.payload.name,
				ok: true,
				result: { ok: true },
			})));
		};
		bridge = new ProjectToolBridge("turn-tools", write, 1_000);

		const result = await runProjectAgentTurn(
			{
				sessionId: "session-tools",
				turnId: "turn-tools",
				prompt: "找到地图，并告诉我现场是否仍在工作。",
				systemPrompt: "按需使用只读工具。",
				allowedTools: ["project_search", "creation_observe"],
				maxTurns: 4,
				maxToolCalls: 3,
			},
			{ model: faux.getModel(), streamFn: faux.streamSimple },
			bridge,
			write,
		);

		expect(result.status).toBe("completed");
		expect(calls).toEqual(["project_search", "creation_observe"]);
		expect(result.toolCalls).toBe(2);
	});

	it("supports work-catalog targeting and durable goal control", async () => {
		const faux = createFauxCore({
			provider: "arcvellum-faux",
			models: [{ id: "project-agent-goal", reasoning: false }],
		});
		const workId = "work-0123456789abcdef";
		faux.setResponses([
			fauxAssistantMessage(fauxToolCall("workspace_catalog", {}), { stopReason: "toolUse" }),
			fauxAssistantMessage(fauxToolCall("project_goal_manage", {
				work_id: workId,
				operation: "start",
				objective: "完成两章并形成可交付正文",
				stop_after_formal_units: 2,
			}), { stopReason: "toolUse" }),
			fauxAssistantMessage("长期目标已经开始，后台会持续推进。"),
		]);
		const calls: Array<{ name: string; arguments: unknown }> = [];
		let bridge: ProjectToolBridge;
		const write = (value: BridgeEnvelope) => {
			if (value.type !== "tool.call") return;
			calls.push({ name: String(value.payload.name), arguments: value.payload.arguments });
			queueMicrotask(() => bridge.receive(envelope("tool.result", "turn-goal", {
				request_id: value.payload.request_id,
				name: value.payload.name,
				ok: true,
				result: { ok: true, work_id: workId },
			})));
		};
		bridge = new ProjectToolBridge("turn-goal", write, 1_000);

		const result = await runProjectAgentTurn({
			sessionId: "session-goal",
			turnId: "turn-goal",
			prompt: "把这部作品作为长期目标推进到交付。",
			systemPrompt: "先确认作品，再启动长期目标。",
			allowedTools: ["workspace_catalog", "project_goal_manage"],
			maxTurns: 4,
			maxToolCalls: 3,
		}, { model: faux.getModel(), streamFn: faux.streamSimple }, bridge, write);

		expect(result.status).toBe("completed");
		expect(calls.map((item) => item.name)).toEqual(["workspace_catalog", "project_goal_manage"]);
		expect(calls[1].arguments).toMatchObject({
			work_id: workId,
			operation: "start",
			stop_after_formal_units: 2,
		});
	});

	it("fails closed for a mismatched tool result", async () => {
		let bridge: ProjectToolBridge;
		let outbound: BridgeEnvelope | null = null;
		bridge = new ProjectToolBridge("turn-1", (value) => {
			outbound = value;
		}, 1_000);
		const request = bridge.request("project_overview", {});
		const call = outbound as BridgeEnvelope | null;
		expect(call?.type).toBe("tool.call");
		bridge.receive(envelope("tool.result", "turn-1", {
			request_id: call?.payload.request_id,
			name: "wrong_tool",
			ok: true,
			result: {},
		}));
		await expect(request).rejects.toThrow("name mismatch");
		expect(bridge.pendingCount).toBe(0);
	});
});
