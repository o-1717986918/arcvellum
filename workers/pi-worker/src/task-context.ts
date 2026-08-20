import { readFile } from "node:fs/promises";
import { join } from "node:path";
import type { OutputContract, TaskContext } from "./contracts.ts";
import { normalizeRelativePath } from "./path-policy.ts";

export async function loadTaskContext(
	workspace: string,
	allowedStates: readonly string[],
	repairTargets: readonly string[] = [],
): Promise<TaskContext> {
	const raw = await readJson(join(workspace, "TASK_CONTEXT.json"));
	const task = await readJson(join(workspace, "_task", "task.json"));
	const execution = await readJson(join(workspace, "_task", "execution_contract.json"));
	const schema = stringValue(raw.schema);
	if (schema !== "literary-engineering-studio/task-context/v0.2") {
		throw new Error(`unsupported TASK_CONTEXT schema: ${schema || "missing"}`);
	}
	const taskId = requiredString(raw, "task_id");
	const route = requiredString(raw, "route");
	const currentState = requiredString(raw, "current_state");
	if (taskId !== stringValue(task.task_id) || route !== stringValue(task.route) || currentState !== stringValue(task.current_state)) {
		throw new Error("task identity differs between TASK_CONTEXT and task snapshot");
	}
	const executionPolicy = requiredString(raw, "execution_policy");
	if (executionPolicy !== "agent-required" || executionPolicy !== stringValue(execution.execution_policy)) {
		throw new Error("ArcVellum Pi Worker only accepts agent-required tasks");
	}
	if (!allowedStates.includes(currentState)) {
		throw new Error(`task state is outside the Pi Worker prototype allowlist: ${currentState}`);
	}

	const expectedOutputs = pathList(raw.expected_outputs);
	const completion = recordValue(raw.completion_contract);
	const completionOutputs = arrayValue(completion.agent_owned_outputs).map((item) => outputContract(recordValue(item)));
	const outputContracts = arrayValue(raw.output_contracts).map((item) => recordValue(item));
	const agentOwnedOutputs = completionOutputs.length > 0 ? completionOutputs : outputContracts
		.filter((item) => stringValue(item.kind) !== "completion-evidence")
		.map(outputContract);
	validateOutputSets(expectedOutputs, agentOwnedOutputs);

	const executionContext = recordValue(raw.execution_context);
	const promptAccess = promptAccessContract(raw);
	const exactOnDemand = promptAccess
		? pathList(promptAccess.exact_on_demand)
		: pathList(executionContext.exact_on_demand);
	const excluded = pathList(executionContext.excluded);
	const controlled = recordValue(raw.controlled_capabilities);
	const readablePaths = pathList(controlled.readable_paths);
	const writablePaths = pathList(controlled.writable_paths);
	if (readablePaths.length > 0 && exactOnDemand.some((item) => !readablePaths.includes(item))) {
		throw new Error("exact-on-demand context exceeds the readable capability manifest");
	}
	if (writablePaths.some((item) => !expectedOutputs.includes(item))) {
		throw new Error("writable capability manifest exceeds expected outputs");
	}

	const repairTargetSet = new Set(repairTargets.map(normalizeRelativePath));
	if ([...repairTargetSet].some((item) => !agentOwnedOutputs.some((output) => output.path === item))) {
		throw new Error("repair target exceeds Agent-owned expected outputs");
	}
	const activeOutputs = repairTargetSet.size > 0
		? agentOwnedOutputs.filter((item) => repairTargetSet.has(item.path))
		: agentOwnedOutputs;
	const activePaths = activeOutputs.map((item) => item.path);

	return {
		schema,
		taskId,
		projectId: stringValue(raw.project_id) || "project-legacy",
		route,
		currentState,
		agentRole: requiredString(raw, "agent_role"),
		executionPolicy,
		expectedOutputs: repairTargetSet.size > 0 ? activePaths : expectedOutputs,
		agentOwnedOutputs: activeOutputs,
		exactOnDemand: repairTargetSet.size > 0 ? [] : exactOnDemand,
		excluded,
		readablePaths: repairTargetSet.size > 0 ? activePaths : readablePaths,
		writablePaths: repairTargetSet.size > 0 ? activePaths : writablePaths,
		hardConstraints: stringList(raw.hard_constraints),
		styleConstraints: stringList(raw.style_constraints),
		validationGates: stringList(raw.validation_gates),
		wordCount: numberRecord(raw.word_count),
		semanticPassCondition: recordValue(completion.semantic_pass_condition),
		promptAsset: recordValue(raw.prompt_asset),
		promptAccess: promptAccess ?? {},
		maxResultChars: positiveInteger(controlled.max_result_chars, 24_000),
		raw,
	};
}

export function publicTaskProjection(context: TaskContext): Record<string, unknown> {
	return {
		schema: context.schema,
		task_id: context.taskId,
		project_id: context.projectId,
		route: context.route,
		current_state: context.currentState,
		agent_role: context.agentRole,
		agent_owned_outputs: context.agentOwnedOutputs.map((item) => ({
			path: item.path,
			format: item.format,
			schema_name: item.schemaName,
		})),
		exact_on_demand: context.exactOnDemand,
		word_count: context.wordCount,
		hard_constraints: context.hardConstraints,
		style_constraints: context.styleConstraints,
		validation_gates: context.validationGates,
		semantic_pass_condition: context.semanticPassCondition,
		prompt_asset: context.promptAsset,
		prompt_access: {
			schema: stringValue(context.promptAccess.schema),
			formal_version: stringValue(context.promptAccess.formal_version),
			renderer: stringValue(context.promptAccess.renderer),
			digest: stringValue(context.promptAccess.digest),
		},
	};
}

function promptAccessContract(raw: Record<string, unknown>): Record<string, unknown> | null {
	if (!("prompt_access" in raw)) return null;
	if (!isRecord(raw.prompt_access)) throw new Error("TASK_CONTEXT prompt_access must be an object");
	if (Object.keys(raw.prompt_access).length === 0) return null;
	const schema = requiredString(raw.prompt_access, "schema");
	if (schema !== "arcvellum/prompt-access/v1") {
		throw new Error(`unsupported prompt access schema: ${schema}`);
	}
	requiredString(raw.prompt_access, "formal_version");
	requiredString(raw.prompt_access, "digest");
	return raw.prompt_access;
}

async function readJson(path: string): Promise<Record<string, unknown>> {
	const parsed: unknown = JSON.parse(await readFile(path, "utf8"));
	if (!isRecord(parsed)) throw new Error(`expected a JSON object: ${path}`);
	return parsed;
}

function validateOutputSets(expected: string[], outputs: OutputContract[]): void {
	if (outputs.length === 0) throw new Error("task has no Agent-owned outputs");
	const paths = outputs.map((item) => item.path);
	if (new Set(paths).size !== paths.length) throw new Error("Agent-owned outputs contain duplicates");
	if (paths.some((item) => !expected.includes(item))) throw new Error("Agent-owned outputs exceed expected outputs");
	for (const item of outputs) {
		if (item.kind === "completion-evidence" || item.path.endsWith(".agent_completion.json")) {
			throw new Error("completion evidence cannot be Agent-owned");
		}
	}
}

function outputContract(value: Record<string, unknown>): OutputContract {
	const path = normalizeRelativePath(requiredString(value, "path"));
	return {
		path,
		kind: stringValue(value.kind) || "agent-authored",
		format: stringValue(value.format) || inferFormat(path),
		schemaName: stringValue(value.schema_name),
	};
}

function inferFormat(path: string): string {
	if (path.endsWith(".json")) return "json";
	if (path.endsWith(".md")) return "markdown";
	if (path.endsWith(".yaml") || path.endsWith(".yml")) return "yaml";
	return "text";
}

function pathList(value: unknown): string[] {
	return stringList(value).map(normalizeRelativePath);
}

function stringList(value: unknown): string[] {
	return arrayValue(value).map(stringValue).filter(Boolean);
}

function arrayValue(value: unknown): unknown[] {
	return Array.isArray(value) ? value : [];
}

function recordValue(value: unknown): Record<string, unknown> {
	return isRecord(value) ? value : {};
}

function numberRecord(value: unknown): Record<string, number> {
	const record = recordValue(value);
	return Object.fromEntries(Object.entries(record).map(([key, item]) => [key, Number(item) || 0]));
}

function requiredString(value: Record<string, unknown>, key: string): string {
	const result = stringValue(value[key]);
	if (!result) throw new Error(`TASK_CONTEXT is missing ${key}`);
	return result;
}

function stringValue(value: unknown): string {
	return typeof value === "string" ? value.trim() : "";
}

function positiveInteger(value: unknown, fallback: number): number {
	const parsed = Number(value);
	return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}
