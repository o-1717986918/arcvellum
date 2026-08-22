import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import type { AgentTool } from "@earendil-works/pi-agent-core";
import { Type } from "@earendil-works/pi-ai";
import type { RuntimeEventSink, TaskContext, ValidationIssue, ValidationResult, WorkerOptions, WorkerState } from "./contracts.ts";
import { atomicWriteAuthorizedFile, normalizeRelativePath, readAuthorizedFile, readAuthorizedSource, resolveWorkspacePath } from "./path-policy.ts";
import { publicTaskProjection } from "./task-context.ts";
import { completeRepairReadHandoff } from "./repair-phase.ts";
import { validateSemanticOutput } from "./semantic-output.ts";

const EMPTY_PARAMETERS = Type.Object({});

export function createWorkerTools(
	context: TaskContext,
	options: WorkerOptions,
	state: WorkerState,
	emit: RuntimeEventSink,
): AgentTool[] {
	const ownedPaths = new Set(context.agentOwnedOutputs.map((item) => item.path));
	const readablePaths = new Set([...context.exactOnDemand, ...ownedPaths]);
	const tools: AgentTool[] = [
		{
			name: "read_task_context",
			label: "Read Task Contract",
			description: "Return the safe, machine-readable ArcVellum task contract and completion checklist.",
			parameters: EMPTY_PARAMETERS,
			executionMode: "sequential",
			execute: async () => {
				state.taskContextReads += 1;
				return result(publicTaskProjection(context), { taskId: context.taskId });
			},
		},
		{
			name: "read_authorized_source",
			label: "Read Exact Context Or Output",
			description: "Read one exact-on-demand source by evidence_id, or reread an Agent-owned expected output by path. Directory evidence returns an inventory; pass the same evidence_id with one listed member_path to read that file. Must-inline sources cannot be reread.",
			parameters: Type.Object({
				evidence_id: Type.Optional(Type.String()),
				path: Type.Optional(Type.String()),
				member_path: Type.Optional(Type.String()),
				offset: Type.Optional(Type.Integer({ minimum: 0 })),
				limit: Type.Optional(Type.Integer({ minimum: 1, maximum: context.maxResultChars })),
			}),
			executionMode: "sequential",
			execute: async (_id, params) => {
				const input = params as { evidence_id?: string; path?: string; member_path?: string; offset?: number; limit?: number };
				const target = readTarget(input, context.evidenceIndex);
				if (!readablePaths.has(target.authorizationRoot)) throw new Error("path is neither exact-on-demand nor an Agent-owned expected output");
				const content = target.memberPath
					? await readAuthorizedFile(options.workspace, target.memberPath)
					: await readAuthorizedSource(options.workspace, target.authorizationRoot);
				const path = target.memberPath ?? target.authorizationRoot;
				const offset = input.offset ?? 0;
				const limit = input.limit ?? context.maxResultChars;
				const text = content.slice(offset, offset + limit);
				state.readPaths.add(path);
				return result(text, { path, offset, returned: text.length, total: content.length, truncated: offset + text.length < content.length });
			},
		},
		{
			name: "write_expected_output",
			label: "Write Expected Output",
			description: "Atomically write one or several Agent-owned expected outputs. For JSON artifacts, pass a structured json object instead of an escaped content string; Studio serializes it and later restores protected machine fields. Batch only compact artifacts whose combined content is safely below 12000 characters; otherwise write one complete artifact per call. The result includes aggregate local validation. Completion receipts are never writable by the Agent.",
			parameters: Type.Object({
				path: Type.Optional(Type.String()),
				content: Type.Optional(Type.String({ minLength: 1, maxLength: 2_000_000 })),
				json: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
				outputs: Type.Optional(Type.Array(
					Type.Object({
						path: Type.String(),
						content: Type.Optional(Type.String({ minLength: 1, maxLength: 2_000_000 })),
						json: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
					}),
					{ minItems: 1, maxItems: 64 },
				)),
			}),
			executionMode: "sequential",
			execute: async (_id, params) => {
				const input = params as {
					path?: string;
					content?: string;
					json?: Record<string, unknown>;
					outputs?: Array<{
						path: string;
						content?: string;
						json?: Record<string, unknown>;
					}>;
				};
				const values = outputWrites(input);
				const normalized = values.map((item) => ({
					path: normalizeRelativePath(item.path),
					content: normalizeText(item.content),
				}));
				if (new Set(normalized.map((item) => item.path)).size !== normalized.length) {
					throw new Error("a batch cannot contain duplicate output paths");
				}
				if (normalized.some((item) => !ownedPaths.has(item.path))) {
					throw new Error("path is not an Agent-owned expected output");
				}
				for (const item of normalized) {
					await atomicWriteAuthorizedFile(options.workspace, item.path, item.content);
					state.writtenPaths.add(item.path);
					emit("file.changed", { path: item.path });
				}
				state.lastValidation = await validateSubmittedOutputs(
					context,
					options.workspace,
					state.writtenPaths,
				);
				return result({
					message: "outputs written",
					validation: state.lastValidation,
				}, {
					paths: normalized.map((item) => item.path),
					characters: normalized.reduce((total, item) => total + item.content.length, 0),
					validationPassed: state.lastValidation.passed,
				});
			},
		},
		{
			name: "validate_output",
			label: "Validate Outputs",
			description: "Run local existence and machine-format checks for one or all Agent-owned outputs. Studio still owns formal preflight.",
			parameters: Type.Object({ path: Type.Optional(Type.String()) }),
			executionMode: "sequential",
			execute: async (_id, params) => {
				const input = params as { path?: string };
				const path = input.path ? normalizeRelativePath(input.path) : undefined;
				if (path && !ownedPaths.has(path)) throw new Error("path is not an Agent-owned expected output");
				const requestedValidation = await validateSubmittedOutputs(
					context,
					options.workspace,
					state.writtenPaths,
					path,
				);
				state.lastValidation = path
					? await validateSubmittedOutputs(context, options.workspace, state.writtenPaths)
					: requestedValidation;
				return result({
					requested: requestedValidation,
					aggregate: state.lastValidation,
				}, { checked: path ?? "all", aggregatePassed: state.lastValidation.passed });
			},
		},
		{
			name: "complete_task",
			label: "Complete Task",
			description: "Finish only after every Agent-owned output passes local validation. Studio will run authoritative preflight after exit.",
			parameters: EMPTY_PARAMETERS,
			executionMode: "sequential",
			execute: async () => {
				state.lastValidation = await validateSubmittedOutputs(
					context,
					options.workspace,
					state.writtenPaths,
				);
				if (!state.lastValidation.passed) {
					throw new Error(`outputs are incomplete: ${state.lastValidation.issues.map((item) => `${item.path}:${item.code}`).join(", ")}`);
				}
				state.completed = true;
				return { ...result("task outputs are ready for Studio preflight", { outputs: context.agentOwnedOutputs.map((item) => item.path) }), terminate: true };
			},
		},
		{
			name: "request_repair",
			label: "Request Local Repair",
			description: "Request one bounded local repair pass using only current validation failures and existing task context.",
			parameters: Type.Object({ reason: Type.String({ minLength: 1, maxLength: 1000 }) }),
			executionMode: "sequential",
			execute: async (_id, params) => {
				const input = params as { reason: string };
				if (state.repairRequests >= options.maxRepairs) throw new Error("local repair budget exhausted");
				state.repairRequests += 1;
				state.lastValidation = await validateSubmittedOutputs(
					context,
					options.workspace,
					state.writtenPaths,
				);
				return result({ reason: input.reason, validation: state.lastValidation }, { repair: state.repairRequests });
			},
		},
		{
			name: "report_blocker",
			label: "Report Blocker",
			description: "Stop and return a structured blocker when the task cannot be completed within its contract.",
			parameters: Type.Object({ reason: Type.String({ minLength: 1, maxLength: 2000 }) }),
			executionMode: "sequential",
			execute: async (_id, params) => {
				const input = params as { reason: string };
				state.blocked = true;
				state.blockerReason = input.reason.trim();
				return { ...result("blocker recorded", { reason: state.blockerReason }), terminate: true };
			},
		},
	];
	if (options.mode === "repair") {
		const repairReadPaths = [
			...context.agentOwnedOutputs.map((item) => item.path),
			...context.repairReferences,
		];
		tools.splice(2, 0, {
			name: "read_repair_target",
			label: "Read Next Repair Target",
			description: "Read the next existing Studio-authorized repair target or read-only reference. Call with an empty object; the Worker chooses the exact path deterministically.",
			parameters: EMPTY_PARAMETERS,
			executionMode: "sequential",
			execute: async () => {
				for (const path of repairReadPaths) {
					if (state.readPaths.has(path)) continue;
					try {
						const content = await readAuthorizedFile(options.workspace, path);
						state.readPaths.add(path);
						return result(content, {
							path,
							returned: content.length,
							total: content.length,
							truncated: false,
						});
					} catch (error) {
						if (!isMissingFileError(error)) throw error;
						// Missing repair targets are created directly in the write phase.
					}
				}
				const handoff = completeRepairReadHandoff(state);
				emit("runner.repair.phase_handoff", {
					from: "read_repair_target",
					to: handoff.next_tool,
					reason: "all-existing-repair-targets-read",
				});
				return result(handoff, { phaseHandoff: true, returned: 0 });
			},
		});
	}
	return tools;
}

function readTarget(
	input: { evidence_id?: string; path?: string; member_path?: string },
	evidenceIndex: Record<string, string>,
): { authorizationRoot: string; memberPath?: string } {
	const hasId = typeof input.evidence_id === "string" && input.evidence_id.length > 0;
	const hasPath = typeof input.path === "string" && input.path.length > 0;
	if (hasId === hasPath) throw new Error("provide exactly one of evidence_id or path");
	if (hasId) {
		const root = evidenceIndex[input.evidence_id ?? ""];
		if (!root) throw new Error("evidence_id is not an exact-on-demand source");
		if (!input.member_path) return { authorizationRoot: root };
		const member = normalizeRelativePath(input.member_path);
		if (!isWithin(member, root) || member === root) {
			throw new Error("member_path is outside the authorized directory evidence");
		}
		return { authorizationRoot: root, memberPath: member };
	}
	if (input.member_path) throw new Error("member_path requires evidence_id");
	return { authorizationRoot: normalizeRelativePath(input.path ?? "") };
}

function isWithin(path: string, root: string): boolean {
	return path.startsWith(`${root.replace(/\/$/, "")}/`);
}

export async function validateOutputs(context: TaskContext, workspace: string, onlyPath?: string): Promise<ValidationResult> {
	const contracts = onlyPath
		? context.agentOwnedOutputs.filter((item) => item.path === onlyPath)
		: context.agentOwnedOutputs;
	const issues: ValidationIssue[] = [];
	for (const contract of contracts) {
		let text: string;
		try {
			const target = await resolveWorkspacePath(workspace, contract.path, false);
			text = await readFile(target, "utf8");
		} catch (error) {
			issues.push({ path: contract.path, code: "missing", message: publicError(error) });
			continue;
		}
		if (!text.trim()) {
			issues.push({ path: contract.path, code: "empty", message: "output is empty" });
			continue;
		}
		if (contract.format === "json") {
			try {
				const parsed: unknown = JSON.parse(text);
				issues.push(...validateSemanticOutput(context, contract.path, parsed));
			} catch (error) {
				issues.push({ path: contract.path, code: "invalid_json", message: publicError(error) });
			}
		}
	}
	return { passed: issues.length === 0, issues };
}

/**
 * Validate both file shape and this Worker's submission provenance.
 *
 * Deterministic preparation is allowed to scaffold Agent-owned paths. Those
 * files are useful templates, but their presence cannot prove that the Agent
 * completed the current task. A successful handoff therefore requires every
 * active output to have passed through write_expected_output in this run.
 */
export async function validateSubmittedOutputs(
	context: TaskContext,
	workspace: string,
	submittedPaths: ReadonlySet<string>,
	onlyPath?: string,
): Promise<ValidationResult> {
	const base = await validateOutputs(context, workspace, onlyPath);
	const contracts = onlyPath
		? context.agentOwnedOutputs.filter((item) => item.path === onlyPath)
		: context.agentOwnedOutputs;
	const submissionIssues: ValidationIssue[] = contracts
		.filter((contract) => !submittedPaths.has(contract.path))
		.map((contract) => ({
			path: contract.path,
			code: "not_submitted_this_run",
			message: "output exists only as prior/scaffold state and was not submitted by this Worker run",
		}));
	const issues = [...base.issues, ...submissionIssues];
	return { passed: issues.length === 0, issues };
}

export async function progressDigest(context: TaskContext, workspace: string, state: WorkerState): Promise<string> {
	const hash = createHash("sha256");
	for (const contract of context.agentOwnedOutputs) {
		hash.update(contract.path);
		try {
			hash.update(await readAuthorizedFile(workspace, contract.path));
		} catch {
			hash.update("missing");
		}
	}
	hash.update([...state.readPaths].sort().join("\n"));
	hash.update([...state.writtenPaths].sort().join("\n"));
	hash.update(`task-context-reads:${state.taskContextReads}`);
	hash.update(`repair-read-handoffs:${state.repairReadHandoffs}`);
	hash.update(state.lastValidation.passed ? "validation:passed" : "validation:not-passed");
	hash.update(state.lastValidation.issues.map((item) => `${item.path}:${item.code}`).sort().join("\n"));
	hash.update(
		state.lastToolError
			? `tool-error:${state.lastToolError.tool}:${state.lastToolError.reason}`
			: "tool-error:none",
	);
	return hash.digest("hex");
}

function result(value: unknown, details: Record<string, unknown>) {
	return {
		content: [{ type: "text" as const, text: typeof value === "string" ? value : JSON.stringify(value, null, 2) }],
		details,
	};
}

function normalizeText(value: string): string {
	return value.replaceAll("\r\n", "\n").replaceAll("\r", "\n").replace(/^\uFEFF/, "");
}

function outputWrites(input: {
	path?: string;
	content?: string;
	json?: Record<string, unknown>;
	outputs?: Array<{
		path: string;
		content?: string;
		json?: Record<string, unknown>;
	}>;
}): Array<{ path: string; content: string }> {
	const hasSingle = typeof input.path === "string"
		|| typeof input.content === "string"
		|| input.json !== undefined;
	const hasBatch = Array.isArray(input.outputs);
	if (hasSingle === hasBatch) throw new Error("provide either one path payload or outputs");
	if (hasBatch) {
		return (input.outputs ?? []).map((item) => ({
			path: item.path,
			content: serializedOutput(item.content, item.json),
		}));
	}
	if (!input.path) throw new Error("single output requires path");
	return [{ path: input.path, content: serializedOutput(input.content, input.json) }];
}

function serializedOutput(
	content: string | undefined,
	json: Record<string, unknown> | undefined,
): string {
	if ((typeof content === "string") === (json !== undefined)) {
		throw new Error("each output requires exactly one of content or json");
	}
	return json === undefined ? content ?? "" : `${JSON.stringify(json, null, 2)}\n`;
}

function publicError(error: unknown): string {
	return error instanceof Error ? error.message : String(error);
}

function isMissingFileError(error: unknown): boolean {
	return typeof error === "object"
		&& error !== null
		&& "code" in error
		&& (error as { code?: unknown }).code === "ENOENT";
}
