import { describe, expect, it } from "vitest";
import { conversationSystemPrompt } from "../src/conversation.ts";

describe("bounded scene performance profiles", () => {
	it("gives a character actor a distinct roleplay identity without project tools", () => {
		const prompt = conversationSystemPrompt("character-actor");
		expect(prompt).toContain("Fully inhabit only the assigned character");
		expect(prompt).toContain("visible action");
		expect(prompt).toContain("no tools and no project write access");
		expect(prompt).not.toContain("finalized prose writer");
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
