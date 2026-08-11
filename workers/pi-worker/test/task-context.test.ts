import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { loadTaskContext } from "../src/task-context.ts";

const roots: string[] = [];

afterEach(async () => {
	await Promise.all(roots.splice(0).map((root) => rm(root, { recursive: true, force: true })));
});

describe("loadTaskContext", () => {
	it("keeps completion evidence outside Agent-owned outputs", async () => {
		const root = await workspace();
		const context = await loadTaskContext(root, ["candidate-review"]);
		expect(context.agentOwnedOutputs.map((item) => item.path)).toEqual(["reviews/scene.json"]);
		expect(context.expectedOutputs).toContain("reviews/scene.agent_completion.json");
	});

	it("fails closed when the task state is not allowed", async () => {
		const root = await workspace();
		await expect(loadTaskContext(root, ["asset-creation-agent-task"])).rejects.toThrow("outside the Pi Worker prototype allowlist");
	});

	it("rejects an exact-on-demand path outside the capability manifest", async () => {
		const root = await workspace({ readablePaths: [] });
		const payload = JSON.parse(await readFile(join(root, "TASK_CONTEXT.json"), "utf8")) as Record<string, any>;
		payload.controlled_capabilities.readable_paths = ["other.md"];
		await writeFile(join(root, "TASK_CONTEXT.json"), JSON.stringify(payload), "utf8");
		await expect(loadTaskContext(root, ["candidate-review"])).rejects.toThrow("exceeds the readable capability manifest");
	});

	it("uses the compiled prompt access contract instead of stale context tiers", async () => {
		const root = await workspace({
			readablePaths: ["draft.md", "review.agent_tasks.md"],
			promptAccessPaths: ["review.agent_tasks.md"],
		});
		const context = await loadTaskContext(root, ["candidate-review"]);
		expect(context.exactOnDemand).toEqual(["review.agent_tasks.md"]);
		expect(context.promptAccess.formal_version).toBe("v3");
	});

	it("rejects compiled prompt access outside the capability manifest", async () => {
		const root = await workspace({
			readablePaths: ["draft.md"],
			promptAccessPaths: ["review.agent_tasks.md"],
		});
		await expect(loadTaskContext(root, ["candidate-review"])).rejects.toThrow("exceeds the readable capability manifest");
	});
});

async function workspace(options: { readablePaths?: string[]; promptAccessPaths?: string[] } = {}): Promise<string> {
	const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-"));
	roots.push(root);
	await mkdir(join(root, "_task"), { recursive: true });
	const expected = ["reviews/scene.json", "reviews/scene.agent_completion.json"];
	const task = {
		task_id: "review-scene",
		route: "scene-development",
		current_state: "candidate-review",
	};
	const context = {
		schema: "literary-engineering-studio/task-context/v0.2",
		...task,
		agent_role: "main-review-agent",
		execution_policy: "agent-required",
		expected_outputs: expected,
		completion_contract: {
			agent_owned_outputs: [{ path: "reviews/scene.json", kind: "agent-authored", format: "json", schema_name: "review/v1" }],
			semantic_pass_condition: {},
		},
		execution_context: { exact_on_demand: ["draft.md"], excluded: [] },
		...(options.promptAccessPaths ? {
			prompt_access: {
				schema: "arcvellum/prompt-access/v1",
				formal_version: "v3",
				renderer: "tool-worker",
				program_digest: "program-digest",
				inline: [],
				exact_on_demand: options.promptAccessPaths,
				digest: "access-digest",
			},
		} : {}),
		controlled_capabilities: {
			readable_paths: options.readablePaths ?? ["draft.md"],
			writable_paths: expected,
			max_result_chars: 4000,
		},
	};
	await writeFile(join(root, "TASK_CONTEXT.json"), JSON.stringify(context), "utf8");
	await writeFile(join(root, "_task", "task.json"), JSON.stringify(task), "utf8");
	await writeFile(join(root, "_task", "execution_contract.json"), JSON.stringify({ execution_policy: "agent-required" }), "utf8");
	await writeFile(join(root, "draft.md"), "draft", "utf8");
	return root;
}
