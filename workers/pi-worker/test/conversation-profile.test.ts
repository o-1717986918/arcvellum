import { describe, expect, it } from "vitest";
import { actorHistoryMessages, actorTurnEnvelope, conversationMessages, conversationSystemPrompt } from "../src/conversation.ts";

describe("bounded scene performance profiles", () => {
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

	it("retains the legacy conversation identity for other roles", () => {
		expect(conversationSystemPrompt("default")).toContain("ArcVellum role worker");
	});
});
