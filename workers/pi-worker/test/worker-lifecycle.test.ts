import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import type { TaskContext, WorkerState } from "../src/contracts.ts";
import { isProviderEmptyResponse, noProgressTurnLimit, settleTurnBudget } from "../src/worker.ts";

const roots: string[] = [];

afterEach(async () => {
	await Promise.all(roots.splice(0).map((root) => rm(root, { recursive: true, force: true })));
});

describe("bounded worker lifecycle", () => {
	it("allows one bounded landing turn only for the main prose agent", () => {
		expect(noProgressTurnLimit("main-creative-agent")).toBe(3);
		expect(noProgressTurnLimit("main-review-agent")).toBe(2);
		expect(noProgressTurnLimit("main-agent")).toBe(2);
	});

	it("distinguishes a provider empty response from an invalid literary output", () => {
		const workerState = state();
		workerState.providerRequests = 1;

		expect(isProviderEmptyResponse(workerState)).toBe(true);

		workerState.textCharacters = 1;
		expect(isProviderEmptyResponse(workerState)).toBe(false);
	});

	it("completes at the turn boundary when all local output contracts pass", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-turn-"));
		roots.push(root);
		await mkdir(join(root, "out"), { recursive: true });
		await writeFile(join(root, "out", "review.json"), "{}\n", "utf8");
		await writeFile(join(root, "out", "review.md"), "# Review\n", "utf8");
		const workerState = state();

		await settleTurnBudget(context(), root, workerState);

		expect(workerState.completed).toBe(true);
		expect(workerState.blocked).toBe(false);
		expect(workerState.lastValidation.passed).toBe(true);
		expect(workerState.reasoningStopReason).toBe("turn_limit_validated");
	});

	it("fails closed at the turn boundary when an output is missing", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-turn-"));
		roots.push(root);
		const workerState = state();

		await settleTurnBudget(context(), root, workerState);

		expect(workerState.completed).toBe(false);
		expect(workerState.blocked).toBe(true);
		expect(workerState.blockerReason).toContain("before outputs passed");
	});
});

function state(): WorkerState {
	return {
		completed: false,
		blocked: false,
		blockerReason: "",
		turns: 6,
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
		promptAccess: {},
		maxResultChars: 4000,
		raw: {},
	};
}
