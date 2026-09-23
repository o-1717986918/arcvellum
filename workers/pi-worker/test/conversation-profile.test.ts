import { describe, expect, it } from "vitest";
import { conversationSystemPrompt } from "../src/conversation.ts";

describe("bounded scene performance profiles", () => {
	it("gives a character actor a distinct roleplay identity without project tools", () => {
		const prompt = conversationSystemPrompt("character-actor");
		expect(prompt).toContain("你在这一轮就是任务单指定的那个人");
		expect(prompt).toContain("从本场第一节拍到最后一节拍持续以“我”生活其中");
		expect(prompt).toContain("人物自己的语言声音是最高创作优先级");
		expect(prompt).toContain("词域、句法节奏、称呼习惯");
		expect(prompt).toContain("必须体现在 spoken 本身");
		expect(prompt).toContain("first_person_action");
		expect(prompt).toContain("no tools and no project write access");
		expect(prompt).not.toContain("You are an ArcVellum character actor");
	});

	it("gives an environment writer a distinct bounded prose role", () => {
		const prompt = conversationSystemPrompt("environment-writer");
		expect(prompt).toContain("Compose bounded candidate description");
		expect(prompt).toContain("Do not invent plot, canon, locations");
		expect(prompt).toContain("no tools and no project write access");
	});

	it("retains the legacy conversation identity for other roles", () => {
		expect(conversationSystemPrompt("default")).toContain("ArcVellum role worker");
	});
});
