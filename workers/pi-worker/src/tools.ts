import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import type { AgentTool } from "@earendil-works/pi-agent-core";
import { Type } from "@earendil-works/pi-ai";
import type { RuntimeEventSink, TaskContext, ValidationIssue, ValidationResult, WorkerOptions, WorkerState } from "./contracts.ts";
import { atomicWriteAuthorizedFile, normalizeRelativePath, readAuthorizedFile, readAuthorizedSource, resolveWorkspacePath } from "./path-policy.ts";
import { publicTaskProjection } from "./task-context.ts";
import { completeRepairReadHandoff } from "./repair-phase.ts";
import { validateSemanticOutput } from "./semantic-output.ts";
import { previewOutputContracts } from "./artifact-preview.ts";
import { proseLengthMeasure, validateLiteraryOutput } from "./literary-output.ts";

const EMPTY_PARAMETERS = Type.Object({});
export const MAX_WRITE_CHUNK_CHARACTERS = 4_800;
export const MAX_STRUCTURED_JSON_CHARACTERS = 48_000;

export function createWorkerTools(
	context: TaskContext,
	options: WorkerOptions,
	state: WorkerState,
	emit: RuntimeEventSink,
): AgentTool[] {
	const ownedPaths = new Set(context.agentOwnedOutputs.map((item) => item.path));
	const previewContracts = new Map(
		previewOutputContracts(context).map((item) => [item.path, item]),
	);
	const partialPaths = new Set<string>();
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
				path: Type.Optional(Type.Union([Type.String(), Type.Null()])),
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
			description: "Atomically write Agent-owned expected outputs. Each text content argument is limited to 4800 characters. Compact text is complete by default. For a longer text artifact, start with operation=replace and continue_writing=true, continue with operation=append and continue_writing=true, then send the last append with continue_writing=false. When a completed text needs a small correction, use operation=replace_fragment with one exact unique find string and its replacement. During a repair run, correct an existing JSON output with operation=patch_json and one or more replace/remove patches addressed by selector. For a new JSON artifact, pass one complete structured json object up to 48000 serialized characters. Batch only compact final artifacts. Completion receipts are never writable by the Agent.",
			parameters: Type.Object({
				path: Type.Optional(Type.String()),
				operation: Type.Optional(Type.Union([Type.Literal("replace"), Type.Literal("append"), Type.Literal("replace_fragment"), Type.Literal("patch_json")])),
				final: Type.Optional(Type.Boolean()),
				continue_writing: Type.Optional(Type.Boolean()),
				content: Type.Optional(Type.Union([Type.String({ maxLength: MAX_WRITE_CHUNK_CHARACTERS }), Type.Null()])),
				json: Type.Optional(Type.Union([Type.Record(Type.String(), Type.Unknown()), Type.Null()])),
				find: Type.Optional(Type.String({ minLength: 1, maxLength: 2000 })),
				replacement: Type.Optional(Type.String({ maxLength: 2000 })),
				patches: Type.Optional(Type.Array(
					Type.Object({
						op: Type.Union([Type.Literal("replace"), Type.Literal("remove")]),
						selector: Type.String({ minLength: 1, maxLength: 500 }),
						value: Type.Optional(Type.Unknown()),
					}),
					{ minItems: 1, maxItems: 16 },
				)),
				outputs: Type.Optional(Type.Array(
					Type.Object({
						path: Type.Optional(Type.Union([Type.String(), Type.Null()])),
						content: Type.Optional(Type.Union([Type.String({ maxLength: MAX_WRITE_CHUNK_CHARACTERS }), Type.Null()])),
						json: Type.Optional(Type.Union([Type.Record(Type.String(), Type.Unknown()), Type.Null()])),
					}),
					{ minItems: 1, maxItems: 64 },
				)),
			}),
			executionMode: "sequential",
			execute: async (_id, params) => {
				const input = params as {
					path?: string | null;
					operation?: "replace" | "append" | "replace_fragment" | "patch_json";
					final?: boolean;
					continue_writing?: boolean;
					content?: string | null;
					json?: Record<string, unknown> | null;
					find?: string;
					replacement?: string;
					patches?: JsonPatch[];
					outputs?: Array<{
						path?: string | null;
						content?: string | null;
						json?: Record<string, unknown> | null;
					}>;
				};
				const values = input.operation === "replace_fragment"
					? [await fragmentReplacement(input, context, options.workspace, partialPaths)]
					: input.operation === "patch_json"
						? [await jsonPatchReplacement(input, context, options, partialPaths)]
						: outputWrites(input, context.agentOwnedOutputs, state.writtenPaths);
				const normalized = values.map((item) => ({
					path: normalizeRelativePath(item.path),
					content: normalizeText(item.content),
					format: item.format,
					operation: item.operation,
					final: item.final,
					payloadCharacters: "payloadCharacters" in item ? item.payloadCharacters : item.content.length,
				}));
				if (new Set(normalized.map((item) => item.path)).size !== normalized.length) {
					throw new Error("a batch cannot contain duplicate output paths");
				}
				if (normalized.some((item) => !ownedPaths.has(item.path))) {
					throw new Error("path is not an Agent-owned expected output");
				}
				for (const item of normalized) {
					if (item.format === "text" && item.payloadCharacters > MAX_WRITE_CHUNK_CHARACTERS) {
						throw new Error(`text chunks must not exceed ${MAX_WRITE_CHUNK_CHARACTERS} characters; use replace/append/final chunking`);
					}
					if (item.format === "json" && item.content.length > MAX_STRUCTURED_JSON_CHARACTERS) {
						throw new Error(`structured JSON must not exceed ${MAX_STRUCTURED_JSON_CHARACTERS} serialized characters`);
					}
					if (state.writtenPaths.has(item.path) && item.operation === "replace") {
						const current = await validateOutputs(context, options.workspace, item.path);
						if (current.passed) {
							const next = nextIncompleteOutput(context, state.writtenPaths, state.lastValidation, item.path);
							throw new Error(`output already passes local validation and is locked for this run; do not regenerate ${item.path}${next ? `; write ${next} next` : "; complete the task"}`);
						}
						const lengthIssues = current.issues.filter((issue) => issue.code === "prose_above_word_count_maximum" || issue.code === "prose_below_word_count_minimum");
						if (lengthIssues.length && lengthIssues.length === current.issues.length) {
							const currentText = await readAuthorizedFile(options.workspace, item.path);
							if (!item.final || !allowsWholeProseLengthRepair(context, item.path, currentText, item.content)) {
								throw new Error(`submitted prose has only a quantified length issue; do not regenerate the complete artifact; use operation=replace_fragment and make the substantial measured progress required by the tool: ${lengthIssues[0]?.message ?? "repair the exact length difference"}`);
							}
						}
					}
					let committedContent = item.content;
					if (item.operation === "append") {
						if (!partialPaths.has(item.path)) {
							throw new Error("append requires an unfinished output started with operation=replace and final=false");
						}
						committedContent = `${await readAuthorizedFile(options.workspace, item.path)}${item.content}`;
					}
					const preview = previewContracts.get(item.path);
					if (preview && (preview.previewMode === "prose_stream" || preview.previewMode === "markdown_stream")) {
						emit("artifact.preview.snapshot", {
							path: item.path,
							kind: preview.kind,
							format: preview.format,
							preview_mode: preview.previewMode,
							identity: "streaming_preview",
							revision: 1,
							content: committedContent,
							characters: committedContent.length,
							replace: true,
							source: "tool-commit",
						});
					}
					await atomicWriteAuthorizedFile(options.workspace, item.path, committedContent);
					if (item.final) {
						partialPaths.delete(item.path);
						state.writtenPaths.add(item.path);
					} else {
						partialPaths.add(item.path);
						state.writtenPaths.delete(item.path);
					}
					emit("file.changed", { path: item.path });
				}
				state.lastValidation = await validateSubmittedOutputs(
					context,
					options.workspace,
					state.writtenPaths,
				);
				for (const item of normalized.filter((candidate) => candidate.final)) {
					const contract = previewContracts.get(item.path);
					const committedContent = await readAuthorizedFile(options.workspace, item.path);
					emit("artifact.checkpoint.written", {
						path: item.path,
						kind: contract?.kind ?? "agent-authored",
						format: contract?.format ?? "text",
						preview_mode: contract?.previewMode ?? "metadata_only",
						identity: "candidate_written",
						characters: committedContent.length,
						sha256: createHash("sha256").update(committedContent, "utf8").digest("hex"),
						validation_passed: state.lastValidation.passed,
					});
				}
				const finalizedPaths = normalized.filter((item) => item.final).map((item) => item.path);
				const finalizedValidation = await Promise.all(finalizedPaths.map(async (path) => ({
					path,
					validation: await validateSubmittedOutputs(context, options.workspace, state.writtenPaths, path),
				})));
				const nextOutput = nextIncompleteOutput(context, state.writtenPaths, state.lastValidation);
				const currentFailures = finalizedValidation.flatMap((item) => item.validation.issues);
				const message = partialPaths.size
					? "output chunk accepted; continue and finalize the unfinished artifact"
					: currentFailures.length
						? `current output still fails local validation; repair only ${currentFailures[0]?.path ?? "the rejected output"} using the quantified issue below`
						: nextOutput
							? `current output accepted and locked; do not rewrite it; write ${nextOutput} next`
							: "all outputs accepted; call complete_task now";
				return result({
					message,
					current_output_validation: finalizedValidation,
					next_output: nextOutput,
					remaining_outputs: incompleteOutputs(context, state.writtenPaths, state.lastValidation),
					validation: state.lastValidation,
				}, {
					paths: normalized.map((item) => item.path),
					characters: normalized.reduce((total, item) => total + item.payloadCharacters, 0),
					unfinishedPaths: [...partialPaths].sort(),
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

async function fragmentReplacement(
	input: {
		path?: string | null;
		final?: boolean;
		content?: string | null;
		json?: Record<string, unknown> | null;
		find?: string;
		replacement?: string;
		outputs?: unknown[];
	},
	context: TaskContext,
	workspace: string,
	partialPaths: ReadonlySet<string>,
): Promise<{
	path: string;
	content: string;
	format: "text";
	operation: "replace_fragment";
	final: true;
	payloadCharacters: number;
}> {
	if (input.outputs || input.content !== undefined || input.json !== undefined) {
		throw new Error("replace_fragment accepts only path, find, and replacement");
	}
	const path = normalizeRelativePath(input.path ?? "");
	const contract = context.agentOwnedOutputs.find((item) => item.path === path);
	if (!contract || contract.format === "json") {
		throw new Error("replace_fragment requires an Agent-owned text output");
	}
	if (partialPaths.has(path)) {
		throw new Error("finish the current chunked write before applying a fragment replacement");
	}
	const find = normalizeText(input.find ?? "");
	const replacement = normalizeText(input.replacement ?? "");
	if (!find) throw new Error("replace_fragment requires a non-empty exact find string");
	const current = await readAuthorizedFile(workspace, path);
	const first = current.indexOf(find);
	if (first < 0) throw new Error("replace_fragment find string is absent from the current output");
	if (current.indexOf(find, first + find.length) >= 0) {
		throw new Error("replace_fragment find string is ambiguous; provide a longer unique excerpt");
	}
	if (find === replacement) throw new Error("replace_fragment must change the output");
	const content = `${current.slice(0, first)}${replacement}${current.slice(first + find.length)}`;
	const before = proseLengthMeasure(context, path, current);
	const after = proseLengthMeasure(context, path, content);
	if (before && after && before.maximum > 0 && before.count > before.maximum && after.count > before.maximum) {
		const remaining = before.count - before.maximum;
		const requiredProgress = requiredFragmentLengthProgress(remaining);
		const actualProgress = Math.max(0, before.count - after.count);
		if (actualProgress < requiredProgress) {
			throw new Error(`replace_fragment must make substantial progress on the current prose overage: ${remaining} Chinese content chars remain; reduce at least ${requiredProgress} in this edit; this replacement reduces only ${actualProgress}; choose one larger exact unique excerpt`);
		}
	}
	if (before && after && before.minimum > 0 && before.count < before.minimum && after.count < before.minimum) {
		const remaining = before.minimum - before.count;
		const requiredProgress = requiredFragmentLengthProgress(remaining);
		const actualProgress = Math.max(0, after.count - before.count);
		if (actualProgress < requiredProgress) {
			throw new Error(`replace_fragment must make substantial progress on the current prose shortfall: ${remaining} Chinese content chars remain; add at least ${requiredProgress} in this edit; this replacement adds only ${actualProgress}; provide one sufficient replacement`);
		}
	}
	return {
		path,
		content,
		format: "text",
		operation: "replace_fragment",
		final: true,
		payloadCharacters: find.length + replacement.length,
	};
}

type JsonPatch = {
	op: "replace" | "remove";
	selector: string;
	value?: unknown;
};

async function jsonPatchReplacement(
	input: {
		path?: string | null;
		final?: boolean;
		continue_writing?: boolean;
		content?: string | null;
		json?: Record<string, unknown> | null;
		find?: string;
		replacement?: string;
		patches?: JsonPatch[];
		outputs?: unknown[];
	},
	context: TaskContext,
	options: WorkerOptions,
	partialPaths: ReadonlySet<string>,
): Promise<{
	path: string;
	content: string;
	format: "json";
	operation: "patch_json";
	final: true;
	payloadCharacters: number;
}> {
	if (options.mode !== "repair") {
		throw new Error("patch_json is available only during a bounded repair run");
	}
	if (input.outputs || input.content != null || input.json != null || input.find || input.replacement) {
		throw new Error("patch_json accepts only path and patches");
	}
	const path = normalizeRelativePath(input.path ?? "");
	const contract = context.agentOwnedOutputs.find((item) => item.path === path);
	const repairTargets = new Set(options.repairTargets.map(normalizeRelativePath));
	if (!contract || contract.format !== "json" || !repairTargets.has(path)) {
		throw new Error("patch_json requires an Agent-owned JSON repair target");
	}
	if (partialPaths.has(path)) {
		throw new Error("finish the current chunked write before applying a JSON patch");
	}
	const patches = input.patches ?? [];
	if (patches.length === 0 || patches.length > 16) {
		throw new Error("patch_json requires between 1 and 16 patches");
	}
	let document: unknown;
	try {
		document = JSON.parse(await readAuthorizedFile(options.workspace, path));
	} catch (error) {
		throw new Error(`patch_json requires an existing valid JSON output: ${publicError(error)}`);
	}
	const before = JSON.stringify(document);
	for (const patch of patches) applyJsonPatch(document, patch);
	const after = JSON.stringify(document);
	if (after === before) throw new Error("patch_json must change the output");
	return {
		path,
		content: `${JSON.stringify(document, null, 2)}\n`,
		format: "json",
		operation: "patch_json",
		final: true,
		payloadCharacters: JSON.stringify(patches).length,
	};
}

function applyJsonPatch(document: unknown, patch: JsonPatch): void {
	const segments = parseJsonSelector(patch.selector);
	let parent: unknown = document;
	for (const segment of segments.slice(0, -1)) {
		parent = jsonChild(parent, segment, patch.selector);
	}
	const leaf = segments[segments.length - 1];
	if (leaf === undefined) throw new Error("patch_json selector must identify one existing value");
	assertSafeJsonKey(leaf);
	if (Array.isArray(parent) && typeof leaf === "number") {
		if (leaf < 0 || leaf >= parent.length) throw new Error(`patch_json selector is absent: ${patch.selector}`);
		if (patch.op === "remove") parent.splice(leaf, 1);
		else {
			if (!Object.prototype.hasOwnProperty.call(patch, "value")) throw new Error("patch_json replace requires value");
			parent[leaf] = patch.value;
		}
		return;
	}
	if (!isJsonRecord(parent) || typeof leaf !== "string" || !Object.prototype.hasOwnProperty.call(parent, leaf)) {
		throw new Error(`patch_json selector is absent: ${patch.selector}`);
	}
	if (patch.op === "remove") delete parent[leaf];
	else {
		if (!Object.prototype.hasOwnProperty.call(patch, "value")) throw new Error("patch_json replace requires value");
		parent[leaf] = patch.value;
	}
}

function jsonChild(parent: unknown, segment: string | number, selector: string): unknown {
	assertSafeJsonKey(segment);
	if (Array.isArray(parent) && typeof segment === "number" && segment >= 0 && segment < parent.length) {
		return parent[segment];
	}
	if (isJsonRecord(parent) && typeof segment === "string" && Object.prototype.hasOwnProperty.call(parent, segment)) {
		return parent[segment];
	}
	throw new Error(`patch_json selector is absent: ${selector}`);
}

function parseJsonSelector(selector: string): Array<string | number> {
	const value = selector.trim().replaceAll("/", ".");
	if (!value) throw new Error("patch_json selector is empty");
	const segments: Array<string | number> = [];
	let index = 0;
	while (index < value.length) {
		if (value[index] === ".") {
			index += 1;
			if (index >= value.length) throw new Error(`patch_json selector is invalid: ${selector}`);
			continue;
		}
		if (value[index] === "[") {
			const close = value.indexOf("]", index + 1);
			const raw = close < 0 ? "" : value.slice(index + 1, close);
			if (!/^\d+$/.test(raw)) throw new Error(`patch_json selector is invalid: ${selector}`);
			segments.push(Number(raw));
			index = close + 1;
			continue;
		}
		let end = index;
		while (end < value.length && value[end] !== "." && value[end] !== "[") end += 1;
		const key = value.slice(index, end);
		if (!key || key.includes("]")) throw new Error(`patch_json selector is invalid: ${selector}`);
		assertSafeJsonKey(key);
		segments.push(key);
		index = end;
	}
	if (segments.length === 0) throw new Error(`patch_json selector is invalid: ${selector}`);
	return segments;
}

function assertSafeJsonKey(segment: string | number): void {
	if (typeof segment === "string" && ["__proto__", "prototype", "constructor"].includes(segment)) {
		throw new Error("patch_json selector contains a forbidden key");
	}
}

function isJsonRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requiredFragmentLengthProgress(remaining: number): number {
	// Exact fragment edits are the low-risk finishing path. Requiring twenty
	// characters even when the draft is only a few dozen characters outside the
	// contract rejects useful edits and pushes the model back toward a stale
	// whole-document rewrite. A modest floor still prevents one-character
	// nibbling while allowing a short coherent sentence trim to make progress.
	return Math.min(remaining, Math.max(8, Math.ceil(remaining * 0.15)));
}

function allowsWholeProseLengthRepair(
	context: TaskContext,
	path: string,
	current: string,
	proposed: string,
): boolean {
	const before = proseLengthMeasure(context, path, current);
	const after = proseLengthMeasure(context, path, proposed);
	if (!before || !after) return false;
	if (before.maximum > 0 && before.count > before.maximum) {
		const gap = before.count - before.maximum;
		const largeGap = Math.max(80, Math.ceil(before.maximum * 0.1));
		const progress = gap - Math.max(0, after.count - before.maximum);
		return gap > largeGap && progress >= Math.min(gap, Math.max(20, Math.ceil(gap * 0.25)));
	}
	if (before.minimum > 0 && before.count < before.minimum) {
		const gap = before.minimum - before.count;
		const largeGap = Math.max(80, Math.ceil(before.minimum * 0.1));
		const progress = gap - Math.max(0, before.minimum - after.count);
		return gap > largeGap && progress >= Math.min(gap, Math.max(20, Math.ceil(gap * 0.25)));
	}
	return false;
}

function incompleteOutputs(
	context: TaskContext,
	submittedPaths: ReadonlySet<string>,
	validation: ValidationResult,
	excludePath = "",
): string[] {
	const invalid = new Set(validation.issues.map((issue) => issue.path));
	return context.agentOwnedOutputs
		.map((item) => item.path)
		.filter((path) => path !== excludePath && (!submittedPaths.has(path) || invalid.has(path)));
}

function nextIncompleteOutput(
	context: TaskContext,
	submittedPaths: ReadonlySet<string>,
	validation: ValidationResult,
	excludePath = "",
): string | null {
	return incompleteOutputs(context, submittedPaths, validation, excludePath)[0] ?? null;
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
				issues.push(...await validateLiteraryOutput(context, workspace, contract.path, text, parsed));
			} catch (error) {
				issues.push({ path: contract.path, code: "invalid_json", message: publicError(error) });
			}
		} else {
			issues.push(...await validateLiteraryOutput(context, workspace, contract.path, text));
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
	path?: string | null;
	operation?: "replace" | "append" | "replace_fragment" | "patch_json";
	final?: boolean;
	continue_writing?: boolean;
	content?: string | null;
	json?: Record<string, unknown> | null;
	outputs?: Array<{
		path?: string | null;
		content?: string | null;
		json?: Record<string, unknown> | null;
	}>;
}, contracts: readonly { path: string; format: string }[], writtenPaths: ReadonlySet<string>): Array<{ path: string; content: string; format: "json" | "text"; operation: "replace" | "append"; final: boolean }> {
	const hasBatch = Array.isArray(input.outputs);
	const hasSingleFields = (
		(typeof input.path === "string" && input.path.trim().length > 0)
		|| (typeof input.content === "string" && input.content.length > 0)
		|| structuredJson(input.json)
	);
	if (hasBatch && (input.operation !== undefined || input.final !== undefined || input.continue_writing !== undefined)) {
		throw new Error("chunk controls are only valid for a single output");
	}
	if (hasBatch && hasSingleFields) throw new Error("provide either one path payload or outputs");
	const entries = hasBatch ? input.outputs ?? [] : [input];
	const pending = contracts.filter((item) => !writtenPaths.has(item.path));
	const assigned = new Set<string>();
	return entries.map((item) => {
		const explicit = typeof item.path === "string" && item.path.trim() ? item.path : "";
		const operation = hasBatch ? "replace" : input.operation ?? "replace";
		if (operation === "replace_fragment" || operation === "patch_json") {
			throw new Error(`${operation} must use its targeted write path`);
		}
		// continue_writing is the canonical control because OpenAI-compatible
		// gateways commonly populate omitted optional booleans with false.  Its
		// safe default therefore means "this compact artifact is complete".  The
		// legacy final flag remains a fallback for older callers that omit it.
		const final = hasBatch
			? true
			: input.continue_writing !== undefined
				? !input.continue_writing
				: input.final ?? true;
		// Models commonly end a conservative chunked write with an empty final
		// append.  It is a valid commit marker only for one explicit unfinished
		// text path; the append ownership check below still rejects empty files or
		// accidental cross-output finalization.
		const emptyAppendFinalizer = !hasBatch
			&& operation === "append"
			&& final
			&& explicit.length > 0
			&& typeof item.content === "string"
			&& item.content.length === 0;
		const content = serializedOutput(item.content, item.json, emptyAppendFinalizer);
		const payloadFormat = structuredJson(item.json) && !emptyAppendFinalizer ? "json" : "text";
		const path = explicit || inferOutputPath(pending, assigned, payloadFormat);
		assigned.add(path);
		return {
			path,
			content,
			format: payloadFormat,
			operation,
			final,
		};
	});
}

function serializedOutput(
	content: string | null | undefined,
	json: Record<string, unknown> | null | undefined,
	allowEmptyText = false,
): string {
	const normalizedContent = typeof content === "string" && (content.length > 0 || allowEmptyText) ? content : undefined;
	// Several OpenAI-compatible gateways populate every optional object field
	// with `{}`.  When real text content is present, that empty object carries no
	// semantic payload and is safe to treat as an unused provider placeholder.
	const normalizedJson = structuredJson(json)
		&& (Object.keys(json).length > 0 || normalizedContent === undefined)
		? json
		: undefined;
	if ((normalizedContent !== undefined) === (normalizedJson !== undefined)) {
		throw new Error("each output requires exactly one of content or json");
	}
	return normalizedJson === undefined ? normalizedContent ?? "" : `${JSON.stringify(normalizedJson, null, 2)}\n`;
}

function structuredJson(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

function inferOutputPath(
	contracts: readonly { path: string; format: string }[],
	assigned: ReadonlySet<string>,
	payloadFormat: "json" | "text",
): string {
	const candidates = contracts.filter((item) =>
		!assigned.has(item.path)
		&& (payloadFormat === "json" ? item.format === "json" : item.format !== "json")
	);
	if (candidates.length !== 1) {
		throw new Error("output path is missing and cannot be inferred uniquely from remaining contracts");
	}
	return candidates[0].path;
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
