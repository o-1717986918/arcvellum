import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
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

	it("enforces the bound Chinese prose length before Studio writeback", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-prose-length-"));
		roots.push(root);
		const path = "drafts/revisions/scene_0001_revision.md";
		await mkdir(join(root, "drafts", "revisions"), { recursive: true });
		await writeFile(join(root, path), "这是一段明显超过上限的中文修订正文。", "utf8");
		const taskContext: TaskContext = {
			...context(),
			currentState: "candidate-revision",
			expectedOutputs: [path],
			agentOwnedOutputs: [{ path, kind: "agent-authored", format: "markdown", schemaName: "" }],
			writablePaths: [path],
			wordCount: { target: 8, minimum: 6, maximum: 10 },
			semanticOutputContract: {
				source_binding: { candidate_path: path },
			},
		};

		const result = await validateOutputs(taskContext, root);

		expect(result.passed).toBe(false);
		expect(result.issues).toContainEqual(expect.objectContaining({
			path,
			code: "prose_above_word_count_maximum",
			message: expect.stringContaining("above max_chinese_chars=10"),
		}));
	});

	it("rejects revision evidence excerpts absent from the exact source", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-revision-source-"));
		roots.push(root);
		const sourcePath = "drafts/candidates/scene_0001-platform-agent.md";
		const candidatePath = "drafts/revisions/scene_0001_revision.md";
		const manifestPath = "drafts/revisions/scene_0001_revision.json";
		await mkdir(join(root, "drafts", "candidates"), { recursive: true });
		await mkdir(join(root, "drafts", "revisions"), { recursive: true });
		await writeFile(join(root, sourcePath), "原文只有这一句。", "utf8");
		await writeFile(join(root, candidatePath), "修订正文也只有这一句。", "utf8");
		await writeFile(join(root, manifestPath), JSON.stringify({
			anti_evasion_rows: [{
				source_excerpt: "模型虚构的原句",
				revised_excerpt: "修订正文也只有这一句。",
			}],
		}), "utf8");
		const taskContext: TaskContext = {
			...context(),
			currentState: "candidate-revision",
			expectedOutputs: [candidatePath, manifestPath],
			agentOwnedOutputs: [
				{ path: candidatePath, kind: "agent-authored", format: "markdown", schemaName: "" },
				{ path: manifestPath, kind: "agent-authored", format: "json", schemaName: "" },
			],
			writablePaths: [candidatePath, manifestPath],
			semanticOutputContract: {
				path: manifestPath,
				source_binding: {
					source_path: sourcePath,
					candidate_path: candidatePath,
				},
			},
		};

		const result = await validateOutputs(taskContext, root, manifestPath);

		expect(result.passed).toBe(false);
		expect(result.issues).toContainEqual(expect.objectContaining({
			code: "revision_source_excerpt_mismatch",
			message: expect.stringContaining("remove unsupported rows"),
		}));
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

	it("enforces conditional shape fields only when their predicate matches", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-conditional-semantic-"));
		roots.push(root);
		await mkdir(join(root, "out"), { recursive: true });
		const taskContext: TaskContext = {
			...context(),
			agentOwnedOutputs: [
				{ path: "out/candidate.json", kind: "agent-authored", format: "json", schemaName: "" },
			],
			writablePaths: ["out/candidate.json"],
			semanticOutputContract: {
				path: "out/candidate.json",
				required_fields: ["canon_writeback"],
				model_owned_fields: ["canon_writeback"],
				field_types: { canon_writeback: "dict" },
				object_shapes: {
					canon_writeback: {
						canon_change: "true | false | unknown",
						no_canon_change_reason: "required non-empty str when canon_change=false",
						candidate_patch: "optional project-relative str",
					},
				},
			},
		};

		await writeFile(join(root, "out", "candidate.json"), JSON.stringify({
			canon_writeback: { canon_change: true },
		}), "utf8");
		expect((await validateOutputs(taskContext, root)).passed).toBe(true);

		await writeFile(join(root, "out", "candidate.json"), JSON.stringify({
			canon_writeback: { canon_change: false },
		}), "utf8");
		const missingReason = await validateOutputs(taskContext, root);
		expect(missingReason.passed).toBe(false);
		expect(missingReason.issues).toEqual(expect.arrayContaining([
			expect.objectContaining({ code: "semantic_missing_field", message: expect.stringContaining("no_canon_change_reason") }),
		]));

		await writeFile(join(root, "out", "candidate.json"), JSON.stringify({
			canon_writeback: { canon_change: false, no_canon_change_reason: "No durable canon changed." },
		}), "utf8");
		expect((await validateOutputs(taskContext, root)).passed).toBe(true);
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

	it("assembles a long text artifact from bounded chunks before marking it submitted", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-chunks-"));
		roots.push(root);
		const taskContext = {
			...context(),
			expectedOutputs: ["out/long-plan.md"],
			agentOwnedOutputs: [{ path: "out/long-plan.md", kind: "agent-authored", format: "markdown", schemaName: "" }],
			writablePaths: ["out/long-plan.md"],
		};
		const workerState = state();
		const write = createWorkerTools(taskContext, options(root), workerState, () => undefined)
			.find((tool) => tool.name === "write_expected_output");

		const first = await write?.execute("call-1", {
			path: "out/long-plan.md",
			operation: "replace",
			continue_writing: true,
			content: "# Plan\n\nPart one.\n",
		});
		expect(workerState.writtenPaths.has("out/long-plan.md")).toBe(false);
		expect(JSON.parse(first?.content[0]?.text ?? "{}").message).toContain("chunk accepted");

		await write?.execute("call-2", {
			path: "out/long-plan.md",
			operation: "append",
			continue_writing: true,
			content: "\nPart two.\n",
		});
		await write?.execute("call-3", {
			path: "out/long-plan.md",
			operation: "append",
			continue_writing: false,
			content: "\nPart three.\n",
		});

		expect(await readFile(join(root, "out", "long-plan.md"), "utf8"))
			.toBe("# Plan\n\nPart one.\n\nPart two.\n\nPart three.\n");
		expect(workerState.writtenPaths.has("out/long-plan.md")).toBe(true);
		expect(workerState.lastValidation.passed).toBe(true);
	});

	it("treats provider-populated false defaults as a compact final write", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-provider-final-default-"));
		roots.push(root);
		const taskContext = {
			...context(),
			expectedOutputs: ["out/review.md"],
			agentOwnedOutputs: [{ path: "out/review.md", kind: "agent-authored", format: "markdown", schemaName: "" }],
			writablePaths: ["out/review.md"],
		};
		const workerState = state();
		const write = createWorkerTools(taskContext, options(root), workerState, () => undefined)
			.find((tool) => tool.name === "write_expected_output");

		await write?.execute("call", {
			path: "out/review.md",
			operation: "replace",
			final: false,
			continue_writing: false,
			content: "# Review\n",
		});

		expect(workerState.writtenPaths.has("out/review.md")).toBe(true);
		expect(workerState.lastValidation.passed).toBe(true);
	});

	it("allows an unfinished text artifact to be finalized without adding content", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-empty-finalizer-"));
		roots.push(root);
		const taskContext = {
			...context(),
			expectedOutputs: ["out/prose.md"],
			agentOwnedOutputs: [{ path: "out/prose.md", kind: "agent-authored", format: "markdown", schemaName: "" }],
			writablePaths: ["out/prose.md"],
		};
		const workerState = state();
		const write = createWorkerTools(taskContext, options(root), workerState, () => undefined)
			.find((tool) => tool.name === "write_expected_output");

		await write?.execute("call-1", {
			path: "out/prose.md",
			operation: "replace",
			final: false,
			content: "Complete prose already emitted.",
		});
		await write?.execute("call-2", {
			path: "out/prose.md",
			operation: "append",
			final: true,
			content: "",
		});

		expect(await readFile(join(root, "out", "prose.md"), "utf8"))
			.toBe("Complete prose already emitted.");
		expect(workerState.writtenPaths.has("out/prose.md")).toBe(true);
		expect(workerState.lastValidation.passed).toBe(true);
	});

	it("repairs a small prose overage with one exact fragment replacement", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-fragment-repair-"));
		roots.push(root);
		const path = "drafts/revisions/scene_0001_revision.md";
		const taskContext: TaskContext = {
			...context(),
			currentState: "candidate-revision",
			expectedOutputs: [path],
			agentOwnedOutputs: [{ path, kind: "agent-authored", format: "markdown", schemaName: "" }],
			writablePaths: [path],
			wordCount: { target: 8, minimum: 6, maximum: 10 },
			semanticOutputContract: { source_binding: { candidate_path: path } },
		};
		const workerState = state();
		const write = createWorkerTools(taskContext, options(root), workerState, () => undefined)
			.find((tool) => tool.name === "write_expected_output");

		const first = await write?.execute("call-1", {
			path,
			operation: "replace",
			final: true,
			content: "甲乙丙丁戊己庚辛壬癸子丑",
		});
		expect(JSON.parse(first?.content[0]?.text ?? "{}").validation.issues)
			.toContainEqual(expect.objectContaining({ code: "prose_above_word_count_maximum" }));
		await expect(write?.execute("call-full-rewrite", {
			path,
			operation: "replace",
			content: "甲乙丙丁戊己庚辛壬癸子",
		})).rejects.toThrow("use operation=replace_fragment");
		await expect(write?.execute("call-too-small", {
			path,
			operation: "replace_fragment",
			final: false,
			find: "丑",
			replacement: "",
		})).rejects.toThrow("must make substantial progress on the current prose overage");
		expect(await readFile(join(root, path), "utf8")).toBe("甲乙丙丁戊己庚辛壬癸子丑");

		const repaired = await write?.execute("call-2", {
			path,
			operation: "replace_fragment",
			final: false,
			find: "子丑",
			replacement: "",
		});
		const payload = JSON.parse(repaired?.content[0]?.text ?? "{}");
		expect(await readFile(join(root, path), "utf8")).toBe("甲乙丙丁戊己庚辛壬癸");
		expect(payload.validation.passed).toBe(true);
		expect(payload.message).toContain("complete_task");
	});

	it("allows a materially shorter whole-prose replacement before fragment repair", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-large-prose-repair-"));
		roots.push(root);
		const path = "drafts/revisions/scene_0001_revision.md";
		const taskContext: TaskContext = {
			...context(),
			currentState: "candidate-revision",
			expectedOutputs: [path],
			agentOwnedOutputs: [{ path, kind: "agent-authored", format: "markdown", schemaName: "" }],
			writablePaths: [path],
			wordCount: { target: 100, minimum: 90, maximum: 100 },
			semanticOutputContract: { source_binding: { candidate_path: path } },
		};
		const workerState = state();
		const write = createWorkerTools(taskContext, options(root), workerState, () => undefined)
			.find((tool) => tool.name === "write_expected_output");

		await write?.execute("call-1", {
			path,
			operation: "replace",
			content: "甲".repeat(220),
		});
		const repaired = await write?.execute("call-2", {
			path,
			operation: "replace",
			content: "甲".repeat(130),
		});

		const payload = JSON.parse(repaired?.content[0]?.text ?? "{}");
		expect(await readFile(join(root, path), "utf8")).toBe("甲".repeat(130));
		expect(payload.validation.issues).toContainEqual(expect.objectContaining({
			code: "prose_above_word_count_maximum",
		}));
	});

	it("accepts a coherent finishing trim when prose is modestly above its maximum", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-finishing-trim-"));
		roots.push(root);
		const path = "drafts/revisions/scene_0001_revision.md";
		const taskContext: TaskContext = {
			...context(),
			currentState: "candidate-revision",
			expectedOutputs: [path],
			agentOwnedOutputs: [{ path, kind: "agent-authored", format: "markdown", schemaName: "" }],
			writablePaths: [path],
			wordCount: { target: 100, minimum: 90, maximum: 100 },
			semanticOutputContract: { source_binding: { candidate_path: path } },
		};
		const workerState = state();
		const write = createWorkerTools(taskContext, options(root), workerState, () => undefined)
			.find((tool) => tool.name === "write_expected_output");

		await write?.execute("call-1", {
			path,
			operation: "replace",
			content: `${"甲".repeat(164)}${"乙".repeat(13)}`,
		});
		const repaired = await write?.execute("call-2", {
			path,
			operation: "replace_fragment",
			find: "乙".repeat(13),
			replacement: "乙",
		});

		const payload = JSON.parse(repaired?.content[0]?.text ?? "{}");
		expect(await readFile(join(root, path), "utf8").then((text) => text.length)).toBe(165);
		expect(payload.validation.issues).toContainEqual(expect.objectContaining({
			code: "prose_above_word_count_maximum",
		}));
	});

	it("locks a valid submitted output and directs the Worker to the next artifact", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-output-lock-"));
		roots.push(root);
		const workerState = state();
		const write = createWorkerTools(context(), options(root), workerState, () => undefined)
			.find((tool) => tool.name === "write_expected_output");

		const first = await write?.execute("call-1", {
			path: "out/review.json",
			json: {},
		});
		const payload = JSON.parse(first?.content[0]?.text ?? "{}");
		expect(payload.message).toContain("accepted and locked");
		expect(payload.next_output).toBe("out/review.md");

		await expect(write?.execute("call-2", {
			path: "out/review.json",
			content: "{}\n",
		})).rejects.toThrow("output already passes local validation");
	});

	it("rejects append when no unfinished artifact owns the target", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-orphan-chunk-"));
		roots.push(root);
		const write = createWorkerTools(context(), options(root), state(), () => undefined)
			.find((tool) => tool.name === "write_expected_output");

		await expect(write?.execute("call", {
			path: "out/review.md",
			operation: "append",
			final: true,
			content: "orphan",
		})).rejects.toThrow("append requires an unfinished output");
	});

	it("emits an honest snapshot when only the completed write tool is observable", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-snapshot-fallback-"));
		roots.push(root);
		const taskContext = {
			...context(),
			agentRole: "main-writing-agent",
			expectedOutputs: ["drafts/scenes/scene_0001_candidate.md"],
			agentOwnedOutputs: [{
				path: "drafts/scenes/scene_0001_candidate.md",
				kind: "prose",
				format: "markdown",
				schemaName: "",
			}],
			writablePaths: ["drafts/scenes/scene_0001_candidate.md"],
		};
		const events: Array<{ event: string; data: Record<string, unknown> }> = [];
		const write = createWorkerTools(taskContext, options(root), state(), (event, data = {}) => {
			events.push({ event, data });
		}).find((tool) => tool.name === "write_expected_output");

		await write?.execute("call", {
			path: "drafts/scenes/scene_0001_candidate.md",
			content: "完整候选正文。",
		});

		expect(events).toContainEqual(expect.objectContaining({
			event: "artifact.preview.snapshot",
			data: expect.objectContaining({
				content: "完整候选正文。",
				source: "tool-commit",
				identity: "streaming_preview",
			}),
		}));
		expect(events).toContainEqual(expect.objectContaining({
			event: "artifact.checkpoint.written",
			data: expect.objectContaining({ identity: "candidate_written" }),
		}));
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

	it("accepts a large structured JSON asset without applying the text chunk limit", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-large-json-"));
		roots.push(root);
		const workerState = state();
		const write = createWorkerTools(context(), options(root), workerState, () => undefined)
			.find((tool) => tool.name === "write_expected_output");
		const longField = "角色背景与行为证据。".repeat(600);

		await write?.execute("call", {
			path: "out/review.json",
			json: { verdict: "pass", longField },
		});

		const payload = JSON.parse(await readFile(join(root, "out", "review.json"), "utf8"));
		expect(payload.longField).toBe(longField);
		expect(workerState.writtenPaths.has("out/review.json")).toBe(true);
	});

	it("patches one existing JSON repair target without regenerating the document", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-json-patch-"));
		roots.push(root);
		await mkdir(join(root, "out"), { recursive: true });
		await writeFile(join(root, "out", "review.json"), JSON.stringify({
			status: "revise_required",
			revision_actions: [
				{ id: "R1", target: "candidate.json" },
				{ id: "R2", target: "review.md" },
			],
			preserved: { evidence: "keep" },
		}, null, 2), "utf8");
		const workerState = state();
		const repairOptions = {
			...options(root),
			mode: "repair" as const,
			repairTargets: ["out/review.json"],
		};
		const write = createWorkerTools(context(), repairOptions, workerState, () => undefined)
			.find((tool) => tool.name === "write_expected_output");

		await write?.execute("call", {
			path: "out/review.json",
			operation: "patch_json",
			patches: [{ op: "remove", selector: "revision_actions[1]" }],
		});

		const payload = JSON.parse(await readFile(join(root, "out", "review.json"), "utf8"));
		expect(payload.revision_actions).toEqual([{ id: "R1", target: "candidate.json" }]);
		expect(payload.preserved).toEqual({ evidence: "keep" });
		expect(workerState.writtenPaths.has("out/review.json")).toBe(true);
	});

	it("limits JSON patches to declared repair targets and safe existing selectors", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-json-patch-policy-"));
		roots.push(root);
		await mkdir(join(root, "out"), { recursive: true });
		await writeFile(join(root, "out", "review.json"), '{"status":"revise_required"}\n', "utf8");
		const normalWrite = createWorkerTools(context(), options(root), state(), () => undefined)
			.find((tool) => tool.name === "write_expected_output");
		await expect(normalWrite?.execute("call", {
			path: "out/review.json",
			operation: "patch_json",
			patches: [{ op: "replace", selector: "status", value: "pass" }],
		})).rejects.toThrow("only during a bounded repair run");

		const repairWrite = createWorkerTools(context(), {
			...options(root),
			mode: "repair",
			repairTargets: ["out/review.json"],
		}, state(), () => undefined).find((tool) => tool.name === "write_expected_output");
		await expect(repairWrite?.execute("call", {
			path: "out/review.json",
			operation: "patch_json",
			patches: [{ op: "replace", selector: "missing.value", value: "pass" }],
		})).rejects.toThrow("selector is absent");
		await expect(repairWrite?.execute("call", {
			path: "out/review.json",
			operation: "patch_json",
			patches: [{ op: "replace", selector: "__proto__.polluted", value: true }],
		})).rejects.toThrow("forbidden key");
	});

	it("normalizes provider null placeholders and uniquely infers omitted paths", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-provider-args-"));
		roots.push(root);
		const workerState = state();
		const write = createWorkerTools(context(), options(root), workerState, () => undefined)
			.find((tool) => tool.name === "write_expected_output");

		await write?.execute("call", {
			outputs: [
				{ path: null, content: "", json: { verdict: "pass" } },
				{ path: null, content: "# Review\n", json: null },
			],
		});

		expect((await validateOutputs(context(), root)).passed).toBe(true);
		expect([...workerState.writtenPaths].sort()).toEqual(["out/review.json", "out/review.md"]);
	});

	it("ignores an empty JSON object placeholder beside real text content", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-provider-empty-object-"));
		roots.push(root);
		const workerState = state();
		const write = createWorkerTools(context(), options(root), workerState, () => undefined)
			.find((tool) => tool.name === "write_expected_output");

		await write?.execute("call", {
			path: "out/review.md",
			content: "# Review\n",
			json: {},
		});

		expect(await readFile(join(root, "out", "review.md"), "utf8")).toBe("# Review\n");
		expect(workerState.writtenPaths.has("out/review.md")).toBe(true);
	});

	it("ignores top-level null placeholders when a provider submits a batch", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-provider-batch-placeholders-"));
		roots.push(root);
		const workerState = state();
		const write = createWorkerTools(context(), options(root), workerState, () => undefined)
			.find((tool) => tool.name === "write_expected_output");

		await write?.execute("call", {
			path: null,
			content: "",
			json: null,
			outputs: [
				{ path: "out/review.json", json: { verdict: "pass" } },
				{ path: "out/review.md", content: "# Review\n" },
			],
		});

		expect((await validateOutputs(context(), root)).passed).toBe(true);
		expect([...workerState.writtenPaths].sort()).toEqual(["out/review.json", "out/review.md"]);
	});

	it("still rejects a batch mixed with a real top-level payload", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-provider-mixed-batch-"));
		roots.push(root);
		const write = createWorkerTools(context(), options(root), state(), () => undefined)
			.find((tool) => tool.name === "write_expected_output");

		await expect(write?.execute("call", {
			path: "out/review.md",
			content: "# Conflicting single output\n",
			json: null,
			outputs: [{ path: "out/review.json", json: { verdict: "pass" } }],
		})).rejects.toThrow("provide either one path payload or outputs");
	});

	it("rejects an omitted path when the remaining output type is ambiguous", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-provider-ambiguous-"));
		roots.push(root);
		const taskContext = {
			...context(),
			expectedOutputs: ["out/a.md", "out/b.md"],
			agentOwnedOutputs: [
				{ path: "out/a.md", kind: "agent-authored", format: "markdown", schemaName: "" },
				{ path: "out/b.md", kind: "agent-authored", format: "markdown", schemaName: "" },
			],
			writablePaths: ["out/a.md", "out/b.md"],
		};
		const write = createWorkerTools(taskContext, options(root), state(), () => undefined)
			.find((tool) => tool.name === "write_expected_output");

		await expect(write?.execute("call", { content: "ambiguous" }))
			.rejects.toThrow("cannot be inferred uniquely");
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
		await writeFile(join(root, "source.md"), "exact revision source\n", "utf8");
		const workerState = state();
		const repairOptions = { ...options(root), mode: "repair" as const };
		const repairContext = { ...context(), repairReferences: ["source.md"] };
		const read = createWorkerTools(repairContext, repairOptions, workerState, () => undefined)
			.find((tool) => tool.name === "read_repair_target");

		const first = await read?.execute("call", {});
		const second = await read?.execute("call", {
			path: "outside.md",
			evidence_id: "D999",
		});

		expect(first?.content[0]?.text).toContain("needs_revision");
		expect(second?.content[0]?.text).toContain("Needs revision");
		const reference = await read?.execute("call", {});
		expect(reference?.content[0]?.text).toContain("exact revision source");
		expect([...workerState.readPaths]).toEqual(["out/review.json", "out/review.md", "source.md"]);
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
		repairReferences: [],
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
		repairReferences: [],
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
