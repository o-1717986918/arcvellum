import { describe, expect, it } from "vitest";
import type { TaskContext } from "../src/contracts.ts";
import {
	ArtifactPreviewExtractor,
	partialWrites,
	previewOutputContracts,
} from "../src/artifact-preview.ts";

describe("ArtifactPreviewExtractor", () => {
	it("emits append deltas from parsed write_expected_output arguments", () => {
		const events: Array<{ event: string; data: Record<string, unknown> }> = [];
		const extractor = new ArtifactPreviewExtractor(context(), (event, data = {}) => {
			events.push({ event, data });
		});

		extractor.handle(toolDelta("第一段。"));
		extractor.handle(toolDelta("第一段。\n第二段。"));

		expect(events).toHaveLength(2);
		expect(events[0]).toMatchObject({
			event: "artifact.preview.delta",
			data: { path: "drafts/scenes/scene_0001.md", delta: "第一段。", revision: 1 },
		});
		expect(events[1]).toMatchObject({
			event: "artifact.preview.delta",
			data: { delta: "\n第二段。", characters: 9 },
		});
	});

	it("uses a replace snapshot when a provider rewrites partial arguments", () => {
		const events: Array<{ event: string; data: Record<string, unknown> }> = [];
		const extractor = new ArtifactPreviewExtractor(context(), (event, data = {}) => {
			events.push({ event, data });
		});

		extractor.handle(toolDelta("旧开头"));
		extractor.handle(toolDelta("新开头"));

		expect(events.at(-1)).toMatchObject({
			event: "artifact.preview.snapshot",
			data: { content: "新开头", replace: true, revision: 2 },
		});
	});

	it("never streams half-formed semantic JSON", () => {
		const events: Array<{ event: string; data: Record<string, unknown> }> = [];
		const extractor = new ArtifactPreviewExtractor(context(), (event, data = {}) => {
			events.push({ event, data });
		});

		extractor.handle(toolDelta("{\"conclusion\":", "reviews/scene_0001.json"));

		expect(events).toHaveLength(0);
		expect(previewOutputContracts(context())[1].previewMode).toBe("semantic_on_commit");
	});

	it("extracts both single and batch writes without parsing raw JSON deltas", () => {
		expect(partialWrites({ path: "a.md", content: "A" })).toEqual([{ path: "a.md", content: "A" }]);
		expect(partialWrites({ outputs: [{ path: "b.md", content: "B" }, { path: "c.json", json: {} }] }))
			.toEqual([{ path: "b.md", content: "B" }]);
	});
});

function toolDelta(content: string, path = "drafts/scenes/scene_0001.md"): Record<string, unknown> {
	return {
		type: "toolcall_delta",
		contentIndex: 0,
		partial: {
			content: [{
				type: "toolCall",
				id: "tool-1",
				name: "write_expected_output",
				arguments: { path, content },
			}],
		},
	};
}

function context(): TaskContext {
	return {
		schema: "literary-engineering-studio/task-context/v0.2",
		taskId: "scene-1-prose",
		projectId: "project-1",
		route: "scene-development",
		currentState: "prose-agent-task",
		agentRole: "main-writing-agent",
		executionPolicy: "agent-required",
		expectedOutputs: ["drafts/scenes/scene_0001.md", "reviews/scene_0001.json"],
		agentOwnedOutputs: [
			{ path: "drafts/scenes/scene_0001.md", kind: "prose", format: "markdown", schemaName: "" },
			{ path: "reviews/scene_0001.json", kind: "review", format: "json", schemaName: "review/v1" },
		],
		exactOnDemand: [],
		excluded: [],
		readablePaths: [],
		writablePaths: [],
		hardConstraints: [],
		styleConstraints: [],
		validationGates: [],
		wordCount: {},
		semanticOutputContract: {},
		semanticPassCondition: {},
		promptAsset: {},
		promptAccess: {},
		evidenceIndex: {},
		repairReferences: [],
		maxResultChars: 24_000,
		raw: {},
	};
}
