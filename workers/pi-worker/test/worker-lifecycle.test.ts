import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import type { TaskContext, WorkerState } from "../src/contracts.ts";
import {
	isProviderEmptyResponse,
	noProgressTurnLimit,
	sanitizeProviderError,
	bindRequiredTool,
	desiredRepairTool,
	desiredWorkerTool,
	settleValidOutputs,
	settleTurnBudget,
	toolMatchesLease,
} from "../src/worker.ts";
import { validateSubmittedOutputs } from "../src/tools.ts";
import { workerProfile } from "../src/worker-profile.ts";

const roots: string[] = [];

afterEach(async () => {
	await Promise.all(roots.splice(0).map((root) => rm(root, { recursive: true, force: true })));
});

describe("bounded worker lifecycle", () => {
	it("binds stable role-isolated Worker profiles instead of task text", () => {
		const writer = workerProfile("main-creative-agent");
		const writerAgain = workerProfile("main-creative-agent");
		const reviewer = workerProfile("main-review-agent");

		expect(writer.digest).toBe(writerAgain.digest);
		expect(writer.digest).not.toBe(reviewer.digest);
		expect(writer.systemPrompt).toContain("FIRST assistant action");
		expect(reviewer.systemPrompt).not.toContain("FIRST assistant action");
		expect(writer.systemPrompt).not.toContain("SKILL.md");
		const repair = workerProfile("main-creative-agent", "repair");
		expect(repair.systemPrompt).toContain("incremental-repair Worker");
		expect(repair.systemPrompt).not.toContain("FIRST assistant action");
		expect(repair.digest).not.toBe(writer.digest);
	});

	it("forces repair turns through read, write, then completion tools", () => {
		const workerState = state();
		expect(desiredRepairTool({ mode: "repair" }, ["out/review.md"], workerState)).toBe("read_authorized_source");
		workerState.readPaths.add("out/review.md");
		expect(desiredRepairTool({ mode: "repair" }, ["out/review.md"], workerState)).toBe("write_expected_output");
		workerState.writtenPaths.add("out/review.md");
		expect(desiredRepairTool({ mode: "repair" }, ["out/review.md"], workerState)).toBe("complete_task");
		expect(desiredRepairTool({ mode: "task" }, ["out/review.md"], workerState)).toBe("");
	});

	it("forces prose immediately and makes partial review submissions converge", () => {
		const workerState = state();
		const creative = {
			agentRole: "main-creative-agent",
			agentOwnedOutputs: [{ path: "draft.md", kind: "agent-authored", format: "markdown", schemaName: "" }],
		};
		const review = { ...creative, agentRole: "main-review-agent" };

		expect(desiredWorkerTool({ mode: "task" }, creative, [], workerState)).toBe("write_expected_output");
		workerState.writtenPaths.add("draft.md");
		expect(desiredWorkerTool({ mode: "task" }, creative, [], workerState)).toBe("");
		const freshReviewState = state();
		expect(desiredWorkerTool({ mode: "task" }, review, [], freshReviewState)).toBe("");
		freshReviewState.taskContextReads = 1;
		expect(desiredWorkerTool({ mode: "task" }, review, [], freshReviewState)).toBe("write_expected_output");
		freshReviewState.writtenPaths.add("other-output.md");
		expect(desiredWorkerTool({ mode: "task" }, review, [], freshReviewState)).toBe("write_expected_output");
		freshReviewState.writtenPaths.add("draft.md");
		freshReviewState.lastValidation = {
			passed: false,
			issues: [{ path: "draft.md", code: "invalid_json", message: "missing comma" }],
		};
		expect(desiredWorkerTool({ mode: "task" }, review, [], freshReviewState)).toBe("write_expected_output");
		workerState.completed = true;
		expect(desiredWorkerTool({ mode: "task" }, creative, [], workerState)).toBe("");
	});

	it("projects required tool choice using provider-native payload shapes", () => {
		expect(bindRequiredTool({}, "openai-completions", "write_expected_output")).toEqual({
			tool_choice: { type: "function", function: { name: "write_expected_output" } },
		});
		expect(bindRequiredTool({ options: { reasoning: "low" } }, "pi-messages", "complete_task")).toEqual({
			options: { reasoning: "low", toolChoice: { type: "function", function: { name: "complete_task" } } },
		});
	});

	it("holds one required-tool lease for every sibling call in a provider response", () => {
		expect(toolMatchesLease("", "validate_output")).toBe(true);
		expect(toolMatchesLease("", "complete_task")).toBe(true);
		expect(toolMatchesLease("write_expected_output", "write_expected_output")).toBe(true);
		expect(toolMatchesLease("write_expected_output", "validate_output")).toBe(false);
	});

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

	it("redacts credentials while preserving provider failure evidence", () => {
		const value = sanitizeProviderError(
			"DeepSeek API error (402) Payment Required api_key=sk-abcdefghijklmnopqrstuvwxyz",
		);

		expect(value).toContain("402");
		expect(value).toContain("Payment Required");
		expect(value).not.toContain("abcdefghijklmnopqrstuvwxyz");
	});

	it("completes at the turn boundary when all local output contracts pass", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-turn-"));
		roots.push(root);
		await mkdir(join(root, "out"), { recursive: true });
		await writeFile(join(root, "out", "review.json"), "{}\n", "utf8");
		await writeFile(join(root, "out", "review.md"), "# Review\n", "utf8");
		const workerState = state();
		workerState.writtenPaths.add("out/review.json");
		workerState.writtenPaths.add("out/review.md");

		await settleTurnBudget(context(), root, workerState);

		expect(workerState.completed).toBe(true);
		expect(workerState.blocked).toBe(false);
		expect(workerState.lastValidation.passed).toBe(true);
		expect(workerState.reasoningStopReason).toBe("turn_limit_validated");
	});

	it("does not accept valid scaffold files that were not submitted this run", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-scaffold-"));
		roots.push(root);
		await mkdir(join(root, "out"), { recursive: true });
		await writeFile(join(root, "out", "review.json"), "{}\n", "utf8");
		await writeFile(join(root, "out", "review.md"), "# Scaffold\n", "utf8");
		const workerState = state();
		workerState.writtenPaths.add("out/review.md");

		const complete = await settleValidOutputs(context(), root, workerState);
		const validation = await validateSubmittedOutputs(
			context(),
			root,
			workerState.writtenPaths,
		);

		expect(complete).toBe(false);
		expect(workerState.completed).toBe(false);
		expect(workerState.lastValidation).toEqual({ passed: false, issues: [] });
		expect(validation.issues).toContainEqual(expect.objectContaining({
			path: "out/review.json",
			code: "not_submitted_this_run",
		}));
	});

	it("preserves the last visible validation until the model receives parser feedback", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-invalid-"));
		roots.push(root);
		await mkdir(join(root, "out"), { recursive: true });
		await writeFile(join(root, "out", "review.json"), "{broken", "utf8");
		await writeFile(join(root, "out", "review.md"), "# Review\n", "utf8");
		const workerState = state();
		workerState.writtenPaths.add("out/review.json");
		workerState.writtenPaths.add("out/review.md");

		const complete = await settleValidOutputs(context(), root, workerState);

		expect(complete).toBe(false);
		expect(workerState.lastValidation).toEqual({ passed: false, issues: [] });
	});

	it("keeps multi-output repair in write mode until every target was submitted", () => {
		const workerState = state();
		const targets = ["out/review.json", "out/review.md"];
		workerState.readPaths.add("out/review.json");
		workerState.readPaths.add("out/review.md");
		workerState.writtenPaths.add("out/review.md");

		expect(desiredRepairTool({ mode: "repair" }, targets, workerState, targets))
			.toBe("write_expected_output");
		workerState.writtenPaths.add("out/review.json");
		expect(desiredRepairTool({ mode: "repair" }, targets, workerState, targets))
			.toBe("complete_task");
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

	it("hands valid written outputs to Studio before the no-progress guard", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-valid-"));
		roots.push(root);
		await mkdir(join(root, "out"), { recursive: true });
		await writeFile(join(root, "out", "review.json"), "{}\n", "utf8");
		await writeFile(join(root, "out", "review.md"), "# Review\n", "utf8");
		const workerState = state();
		workerState.writtenPaths.add("out/review.json");
		workerState.writtenPaths.add("out/review.md");

		const complete = await settleValidOutputs(context(), root, workerState);

		expect(complete).toBe(true);
		expect(workerState.completed).toBe(true);
		expect(workerState.blocked).toBe(false);
		expect(workerState.reasoningStopReason).toBe("local_outputs_validated");
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
		taskContextReads: 0,
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
