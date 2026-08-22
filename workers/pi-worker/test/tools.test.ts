import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import type { TaskContext } from "../src/contracts.ts";
import { createWorkerTools, progressDigest, validateOutputs, validateSubmittedOutputs } from "../src/tools.ts";
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

	it("reports missing and mistyped model-owned semantic fields locally", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-semantic-"));
		roots.push(root);
		await mkdir(join(root, "out"), { recursive: true });
		await writeFile(join(root, "out", "review.json"), JSON.stringify({
			warnings: "none",
			new_character_register: {
				schema: "literary-engineering-workbench/new-character-register/v0.1",
				status: "none",
				introduced: [],
				ephemeral_waivers: [],
			},
		}), "utf8");
		await writeFile(join(root, "out", "review.md"), "# Review\n", "utf8");
		const taskContext = semanticContext();

		const result = await validateOutputs(taskContext, root);

		expect(result.passed).toBe(false);
		expect(result.issues).toEqual(expect.arrayContaining([
			expect.objectContaining({ code: "semantic_type_mismatch", message: expect.stringContaining("warnings") }),
			expect.objectContaining({ code: "semantic_missing_field", message: expect.stringContaining("new_character_register.blocking_issues") }),
		]));
	});

	it("accepts a complete semantic payload without requiring Studio-owned fields", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-semantic-pass-"));
		roots.push(root);
		await mkdir(join(root, "out"), { recursive: true });
		await writeFile(join(root, "out", "review.json"), JSON.stringify({
			warnings: [],
			new_character_register: {
				schema: "literary-engineering-workbench/new-character-register/v0.1",
				status: "none",
				introduced: [],
				ephemeral_waivers: [],
				blocking_issues: [],
			},
		}), "utf8");
		await writeFile(join(root, "out", "review.md"), "# Review\n", "utf8");

		expect((await validateOutputs(semanticContext(), root)).passed).toBe(true);
	});

	it("distinguishes an existing scaffold from a current Worker submission", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-tools-"));
		roots.push(root);
		await mkdir(join(root, "out"), { recursive: true });
		await writeFile(join(root, "out", "review.json"), "{}\n", "utf8");
		await writeFile(join(root, "out", "review.md"), "# Review\n", "utf8");

		const result = await validateSubmittedOutputs(
			context(),
			root,
			new Set(["out/review.md"]),
		);

		expect(result.passed).toBe(false);
		expect(result.issues).toContainEqual(expect.objectContaining({
			path: "out/review.json",
			code: "not_submitted_this_run",
		}));
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
		expect(workerState.lastValidation.passed).toBe(true);
	});

	it("serializes structured JSON without requiring escaped content", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-json-"));
		roots.push(root);
		const workerState = state();
		const write = createWorkerTools(context(), options(root), workerState, () => undefined)
			.find((tool) => tool.name === "write_expected_output");

		await write?.execute("call", {
			outputs: [
				{ path: "out/review.json", json: { verdict: "pass", findings: ["证据成立"] } },
				{ path: "out/review.md", content: "# Review\n" },
			],
		});

		expect((await validateOutputs(context(), root)).passed).toBe(true);
		expect(workerState.lastValidation.passed).toBe(true);
	});

	it("returns aggregate validation immediately after a partial or malformed write", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-write-feedback-"));
		roots.push(root);
		const workerState = state();
		const write = createWorkerTools(context(), options(root), workerState, () => undefined)
			.find((tool) => tool.name === "write_expected_output");

		const response = await write?.execute("call", {
			path: "out/review.json",
			content: "{broken",
		});
		const payload = JSON.parse(response?.content[0]?.text ?? "{}");

		expect(payload.validation.passed).toBe(false);
		expect(payload.validation.issues).toEqual(expect.arrayContaining([
			expect.objectContaining({ path: "out/review.json", code: "invalid_json" }),
			expect.objectContaining({ path: "out/review.md", code: "missing" }),
		]));
		expect(workerState.lastValidation).toEqual(payload.validation);
	});

	it("keeps aggregate failures when validating one passing sibling output", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-aggregate-validation-"));
		roots.push(root);
		await mkdir(join(root, "out"), { recursive: true });
		await writeFile(join(root, "out", "review.json"), "{broken", "utf8");
		await writeFile(join(root, "out", "review.md"), "# Review\n", "utf8");
		const workerState = state();
		workerState.writtenPaths.add("out/review.json");
		workerState.writtenPaths.add("out/review.md");
		const validate = createWorkerTools(context(), options(root), workerState, () => undefined)
			.find((tool) => tool.name === "validate_output");

		const response = await validate?.execute("call", { path: "out/review.md" });
		const payload = JSON.parse(response?.content[0]?.text ?? "{}");

		expect(payload.requested.passed).toBe(true);
		expect(payload.aggregate.passed).toBe(false);
		expect(workerState.lastValidation.issues).toContainEqual(expect.objectContaining({
			path: "out/review.json",
			code: "invalid_json",
		}));
	});

	it("rereads an Agent-owned output for a bounded repair turn", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-tools-"));
		roots.push(root);
		await mkdir(join(root, "out"), { recursive: true });
		await writeFile(join(root, "out", "review.json"), '{"status":"needs_revision"}\n', "utf8");
		const workerState = state();
		const read = createWorkerTools(context(), options(root), workerState, () => undefined)
			.find((tool) => tool.name === "read_authorized_source");

		const response = await read?.execute("call", { path: "out/review.json" });

		expect(response?.content[0]?.text).toContain("needs_revision");
		expect(workerState.readPaths.has("out/review.json")).toBe(true);
	});

	it("selects repair targets deterministically without model-supplied paths", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-repair-target-"));
		roots.push(root);
		await mkdir(join(root, "out"), { recursive: true });
		await writeFile(join(root, "out", "review.json"), '{"status":"needs_revision"}\n', "utf8");
		await writeFile(join(root, "out", "review.md"), "# Needs revision\n", "utf8");
		const workerState = state();
		const repairOptions = { ...options(root), mode: "repair" as const };
		const read = createWorkerTools(context(), repairOptions, workerState, () => undefined)
			.find((tool) => tool.name === "read_repair_target");

		const first = await read?.execute("call", {});
		const second = await read?.execute("call", {
			path: "outside.md",
			evidence_id: "D999",
		});

		expect(first?.content[0]?.text).toContain("needs_revision");
		expect(second?.content[0]?.text).toContain("Needs revision");
		expect([...workerState.readPaths]).toEqual(["out/review.json", "out/review.md"]);
		const handoff = await read?.execute("call", {});
		expect(handoff?.content[0]?.text).toContain('"status": "read_phase_complete"');
		expect(handoff?.content[0]?.text).toContain('"next_tool": "write_expected_output"');
		expect(handoff?.content[0]?.text).not.toContain("Needs revision");
		await expect(read?.execute("call", {})).rejects.toThrow("call write_expected_output");
	});

	it("does not expose the deterministic repair reader during normal tasks", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-normal-tools-"));
		roots.push(root);

		const names = createWorkerTools(context(), options(root), state(), () => undefined)
			.map((tool) => tool.name);

		expect(names).not.toContain("read_repair_target");
	});

	it("reads exact context by machine evidence id without exposing its path in the prompt", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-evidence-id-"));
		roots.push(root);
		await writeFile(join(root, "exact.md"), "authorized evidence", "utf8");
		const taskContext = {
			...context(),
			exactOnDemand: ["exact.md"],
			readablePaths: ["exact.md"],
			evidenceIndex: { D001: "exact.md" },
		};
		const workerState = state();
		const read = createWorkerTools(taskContext, options(root), workerState, () => undefined)
			.find((tool) => tool.name === "read_authorized_source");

		const response = await read?.execute("call", { evidence_id: "D001" });

		expect(response?.content[0]?.text).toContain("authorized evidence");
		expect(workerState.readPaths.has("exact.md")).toBe(true);
		await expect(read?.execute("call", { evidence_id: "D999" }))
			.rejects.toThrow("not an exact-on-demand source");
	});

	it("lists and reads a member of directory evidence without widening authorization", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-directory-evidence-"));
		roots.push(root);
		await mkdir(join(root, "canon"), { recursive: true });
		await writeFile(join(root, "canon", "world_rules.yaml"), "rules: [bounded]\n", "utf8");
		await writeFile(join(root, "outside.md"), "forbidden\n", "utf8");
		const taskContext = {
			...context(),
			exactOnDemand: ["canon"],
			readablePaths: ["canon"],
			evidenceIndex: { D001: "canon" },
		};
		const read = createWorkerTools(taskContext, options(root), state(), () => undefined)
			.find((tool) => tool.name === "read_authorized_source");

		const listing = await read?.execute("call", { evidence_id: "D001" });
		const member = await read?.execute("call", {
			evidence_id: "D001",
			member_path: "canon/world_rules.yaml",
		});

		expect(listing?.content[0]?.text).toContain("canon/world_rules.yaml");
		expect(member?.content[0]?.text).toContain("bounded");
		await expect(read?.execute("call", { evidence_id: "D001", member_path: "outside.md" }))
			.rejects.toThrow("outside the authorized directory evidence");
	});

	it("still rejects a path outside exact context and Agent-owned outputs", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-tools-"));
		roots.push(root);
		await writeFile(join(root, "secret.txt"), "hidden", "utf8");
		const read = createWorkerTools(context(), options(root), state(), () => undefined)
			.find((tool) => tool.name === "read_authorized_source");

		await expect(read?.execute("call", { path: "secret.txt" }))
			.rejects.toThrow("neither exact-on-demand nor an Agent-owned expected output");
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

	it("counts one task-contract inspection as progress", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-contract-read-"));
		roots.push(root);
		const workerState = state();
		const before = await progressDigest(context(), root, workerState);
		const read = createWorkerTools(context(), options(root), workerState, () => undefined)
			.find((tool) => tool.name === "read_task_context");

		await read?.execute("call", {});
		const after = await progressDigest(context(), root, workerState);

		expect(workerState.taskContextReads).toBe(1);
		expect(after).not.toBe(before);
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
		reasoningBudget: {
			enabled: false,
			initialLevel: "minimal",
			maximumLevel: "minimal",
			perRequestTokens: 512,
			totalTokens: 2048,
			maxProviderRequests: 4,
			maxEscalations: 0,
			overBudgetAction: "validate_then_stop",
		},
		mode: "task",
		repairTargets: [],
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
		repairReadHandoffs: 0,
		taskContextReads: 0,
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
		semanticOutputContract: {},
		semanticPassCondition: {},
		promptAsset: {},
		promptAccess: {},
		evidenceIndex: {},
		maxResultChars: 4000,
		raw: {},
	};
}

function semanticContext(): TaskContext {
	return {
		...context(),
		semanticOutputContract: {
			path: "out/review.json",
			required_fields: ["warnings", "new_character_register", "studio_digest"],
			model_owned_fields: ["warnings", "new_character_register"],
			studio_owned_fields: ["studio_digest"],
			field_types: {
				warnings: "list",
				new_character_register: "dict",
			},
			object_shapes: {
				new_character_register: {
					schema: "literary-engineering-workbench/new-character-register/v0.1",
					status: "none | existing_only | ephemeral_only | candidates_ready | resolved",
					introduced: "list",
					ephemeral_waivers: "list",
					blocking_issues: "list; must be empty for a clean result",
					candidate_path: "optional project-relative str",
				},
			},
		},
	};
}
