import { describe, expect, it } from "vitest";
import { actorHistoryMessages, actorTurnEnvelope, conversationMessages, conversationOutcome, conversationStopError, conversationSystemPrompt, roleTurnEnvelope, sceneCreatorEnvelope } from "../src/conversation.ts";

describe("bounded scene performance profiles", () => {
	it("does not accept an earlier tool explanation when the final answer exhausts its output budget", () => {
		const messages = [
			{ role: "assistant", content: [{ type: "text", text: "读完材料后动笔。" }], stopReason: "toolUse" },
			{ role: "toolResult", content: [{ type: "text", text: "只读档案" }] },
			{ role: "assistant", content: [{ type: "thinking", thinking: "未完成" }], stopReason: "length" },
		];
		expect(conversationOutcome("读完材料后动笔。", conversationStopError(messages)).status).toBe("blocked");
		expect(conversationStopError(messages)).toContain("output limit");
	});
	it("keeps completed final text successful and unfinished tool turns blocked", () => {
		expect(conversationStopError([{ role: "assistant", stopReason: "stop" }])).toBeUndefined();
		expect(conversationStopError([{ role: "assistant", stopReason: "toolUse" }])).toContain("tool turn");
		expect(conversationStopError([{ role: "assistant", stopReason: "error", errorMessage: "actual provider error" }]))
			.toBe("actual provider error");
	});
	it("keeps partial provider output blocked with its actual failure", () => {
		expect(conversationOutcome("刚写到这里", "terminated")).toEqual({
			status: "blocked", message: "terminated", validationPassed: false,
		});
		expect(conversationOutcome("完整答复")).toEqual({
			status: "completed", message: "conversation completed", validationPassed: true,
		});
		expect(conversationOutcome("   ").status).toBe("blocked");
	});
	it("gives the character actor no competing system prompt", () => {
		expect(conversationSystemPrompt("character-actor")).toBe("");
	});

	it("keeps initialization and any later messages in one ordered conversation", () => {
		const messages = ["你是甲。", "# 本场角色任务单", "# 继续扮演并回答追问"];
		const payload = JSON.stringify({ schema: "arcvellum/actor-conversation/v1", messages });
		expect(conversationMessages("character-actor", payload)).toEqual(messages);
		expect(() => conversationMessages("character-actor", "你是甲。\n# 本场角色任务单")).toThrow("conversation envelope");
		expect(() => conversationMessages("character-actor", JSON.stringify({ schema: "arcvellum/actor-conversation/v1", messages: ["你是甲。"] }))).toThrow("initialization and subsequent");
		expect(conversationMessages("environment-writer", "环境任务")).toEqual(["环境任务"]);
	});

	it("initializes an environment writer before its scene request without a competing system prompt", () => {
		expect(conversationSystemPrompt("environment-writer")).toBe("");
		const initialization = "【SCENE_LOAD】\nSCENE_CLAIM_LANDSCAPE_DESCRIBER\n\n[NOW_TO_DO]\nSTAND_BY";
		const prompt = "# Independent Environment Writing\n场景资料";
		const envelope = JSON.stringify({ schema: "arcvellum/environment-conversation/v1", initialization, prompt });
		expect(conversationMessages("environment-writer", envelope)).toEqual([initialization, prompt]);
		expect(() => conversationMessages("environment-writer", JSON.stringify({ schema: "arcvellum/environment-conversation/v1", initialization })))
			.toThrow("initialization and scene prompt");
	});

	it("keeps the persona in the system layer and replays only scene turns", () => {
		const payload = JSON.stringify({ schema: "arcvellum/actor-conversation/v2",
			initialization: "【PERSONA_LOAD】\nSELF_CLAIM_LIN", initialization_answer: "",
			history: [{ prompt: "第一轮", answer: "我等你。" }], prompt: "第二轮" });
		expect(actorTurnEnvelope(payload)?.history).toEqual([{ prompt: "第一轮", answer: "我等你。" }]);
		const transcript = actorHistoryMessages(actorTurnEnvelope(payload)!, { api: "openai-completions", provider: "openai", id: "fixture" });
		expect(transcript.map((message) => message.role)).toEqual(["user", "assistant"]);
		expect(actorTurnEnvelope("not json")).toBeNull();
		expect(() => actorTurnEnvelope(JSON.stringify({ schema: "arcvellum/actor-conversation/v2", history: [] })))
			.toThrow("actor turn requires");
	});

	it("initializes each describer with bounded scene history and no competing system prompt", () => {
		for (const role of ["character-describer", "event-narrator", "scene-describer"] as const) {
			expect(conversationSystemPrompt(role)).toBe("");
			const envelope = JSON.stringify({ schema: "arcvellum/role-conversation/v1",
				initialization: "观察方式", initialization_answer: "",
				history: [{ prompt: "第一轮", answer: "候选" }], prompt: "第二轮" });
			expect(roleTurnEnvelope(envelope)?.history).toEqual([{ prompt: "第一轮", answer: "候选" }]);
		}
	});

	it("gives the creator its author identity as a system prompt and a material library", () => {
		const payload = JSON.stringify({ schema: "arcvellum/scene-creator/v1", system_prompt: "作者意图",
			material_root: "C:\\scene-materials", prompt: "本场任务" });
		expect(sceneCreatorEnvelope(payload)).toEqual({ systemPrompt: "作者意图", materialRoot: "C:\\scene-materials", prompt: "本场任务" });
		expect(() => sceneCreatorEnvelope("本场任务")).toThrow("conversation envelope");
	});

	it("uses the supplied creative role without defensive wrapper directions", () => {
		expect(conversationSystemPrompt("default")).toContain("requested role, voice and form");
        expect(conversationSystemPrompt("default")).not.toContain("no tools");
		const envelope = JSON.stringify({ schema: "arcvellum/default-conversation/v1",
			system_prompt: conversationSystemPrompt("default"), prompt: "本轮任务" });
		expect(conversationMessages("default", envelope)).toEqual(["本轮任务"]);
		expect(() => conversationMessages("default", JSON.stringify({
			schema: "arcvellum/default-conversation/v1", system_prompt: "", prompt: "本轮任务",
		}))).toThrow("requires system prompt");
	});
});
