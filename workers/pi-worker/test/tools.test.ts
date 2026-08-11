import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import type { TaskContext } from "../src/contracts.ts";
import { createWorkerTools, progressDigest, validateOutputs } from "../src/tools.ts";
import type { WorkerOptions, WorkerState } from "../src/contracts.ts";

const roots: string[] = [];

afterEach(async () => {
	await Promise.all(roots.splice(0).map((root) => rm(root, { recursive: true, force: true })));
});

describe("local output validation", () => {
	it("reports all missing outputs and invalid JSON together", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-tools-"));
		roots.push(root);
		await mkdir(join(root, "out"), { recursive: true });
		await writeFile(join(root, "out", "review.json"), "{broken", "utf8");
		const result = await validateOutputs(context(), root);
		expect(result.passed).toBe(false);
		expect(result.issues.map((item) => item.code)).toEqual(["invalid_json", "missing"]);
	});

	it("passes nonempty valid machine and markdown outputs", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-tools-"));
		roots.push(root);
		await mkdir(join(root, "out"), { recursive: true });
		await writeFile(join(root, "out", "review.json"), "{}\n", "utf8");
		await writeFile(join(root, "out", "review.md"), "# Review\n", "utf8");
		expect((await validateOutputs(context(), root)).passed).toBe(true);
	});

	it("writes all authorized outputs in one bounded batch", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-tools-"));
		roots.push(root);
		const workerState = state();
		const write = createWorkerTools(context(), options(root), workerState, () => undefined)
			.find((tool) => tool.name === "write_expected_output");
		expect(write).toBeDefined();

		await write?.execute("call", {
			outputs: [
				{ path: "out/review.json", content: "{}\n" },
				{ path: "out/review.md", content: "# Review\n" },
			],
		});

		expect((await validateOutputs(context(), root)).passed).toBe(true);
		expect([...workerState.writtenPaths].sort()).toEqual(["out/review.json", "out/review.md"]);
	});

	it("treats a passing validation as progress even when files are unchanged", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-tools-"));
		roots.push(root);
		await mkdir(join(root, "out"), { recursive: true });
		await writeFile(join(root, "out", "review.json"), "{}\n", "utf8");
		await writeFile(join(root, "out", "review.md"), "# Review\n", "utf8");
		const workerState = state();
		const before = await progressDigest(context(), root, workerState);
		workerState.lastValidation = await validateOutputs(context(), root);
		const after = await progressDigest(context(), root, workerState);

		expect(workerState.lastValidation.passed).toBe(true);
		expect(after).not.toBe(before);
	});

	it("treats the first bounded tool error as progress but repeats remain stable", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-tools-"));
		roots.push(root);
		const workerState = state();
		const before = await progressDigest(context(), root, workerState);
		workerState.lastToolError = {
			tool: "read_authorized_source",
			reason: "source is not exact-on-demand for this task",
		};
		const after = await progressDigest(context(), root, workerState);
		const repeated = await progressDigest(context(), root, workerState);

		expect(after).not.toBe(before);
		expect(repeated).toBe(after);
	});
});

function options(workspace: string): WorkerOptions {
	return {
		workspace,
		model: "fixture/model",
		authPath: "auth.json",
		thinking: "minimal",
		maxTurns: 3,
		maxToolCalls: 6,
		maxRepairs: 1,
		allowedStates: ["candidate-review"],
	};
}

function state(): WorkerState {
	return {
		completed: false,
		blocked: false,
		blockerReason: "",
		turns: 0,
		toolCalls: 0,
		repairRequests: 0,
		reasoningCharacters: 0,
		textCharacters: 0,
		readPaths: new Set(),
		writtenPaths: new Set(),
		lastValidation: { passed: false, issues: [] },
		lastToolError: null,
		progressDigests: [],
	};
}

function context(): TaskContext {
	return {
		schema: "literary-engineering-studio/task-context/v0.2",
		taskId: "review-scene",
		route: "scene-development",
		currentState: "candidate-review",
		agentRole: "main-review-agent",
		executionPolicy: "agent-required",
		expectedOutputs: ["out/review.json", "out/review.md"],
		agentOwnedOutputs: [
			{ path: "out/review.json", kind: "agent-authored", format: "json", schemaName: "" },
			{ path: "out/review.md", kind: "agent-authored", format: "markdown", schemaName: "" },
		],
		exactOnDemand: [],
		excluded: [],
		readablePaths: [],
		writablePaths: ["out/review.json", "out/review.md"],
		hardConstraints: [],
		styleConstraints: [],
		validationGates: [],
		wordCount: {},
		semanticPassCondition: {},
		promptAsset: {},
		maxResultChars: 4000,
		raw: {},
	};
}
