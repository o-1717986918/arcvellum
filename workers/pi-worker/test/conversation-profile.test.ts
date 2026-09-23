import { describe, expect, it } from "vitest";
import { conversationSystemPrompt } from "../src/conversation.ts";

describe("bounded scene performance profiles", () => {
	it("gives a character actor a distinct roleplay identity without project tools", () => {
		const prompt = conversationSystemPrompt("character-actor");
		expect(prompt).toContain("你在这一轮就是任务单指定的那个人");
		expect(prompt).toContain("只经历当前请求覆盖的时刻");
		expect(prompt).toContain("持续以“我”感受并回应");
		expect(prompt).toContain("已发生的公共言行");
		expect(prompt).not.toContain("从本场第一个时刻到最后一个时刻");
		expect(prompt).toContain("你自己决定何时开口、回避、反问、沉默、行动");
		expect(prompt).toContain("同一处境下连续说话或行动");
		expect(prompt).toContain("不为填格制造手势或流程解释");
		expect(prompt).toContain("可挣脱的惯性");
		expect(prompt).toContain("普通可弃的现场细节可作为候选");
		expect(prompt).toContain("no tools and no project write access");
		expect(prompt).not.toContain("You are an ArcVellum character actor");
	});

	it("gives an environment writer a distinct bounded prose role", () => {
		const prompt = conversationSystemPrompt("environment-writer");
		expect(prompt).toContain("你自己决定注意什么、略过什么");
		expect(prompt).toContain("不必逐项写五感、铺满每拍");
		expect(prompt).toContain("一旦某处痕迹、器物状态或声音会被读者当成线索，就必须有来源");
		expect(prompt).toContain("不替人物说话、行动或解释心理");
		expect(prompt).toContain("no tools and no project write access");
	});

	it("retains the legacy conversation identity for other roles", () => {
		expect(conversationSystemPrompt("default")).toContain("ArcVellum role worker");
	});
});
