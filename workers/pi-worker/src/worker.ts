import { Agent } from "@earendil-works/pi-agent-core";
import { builtinModels } from "@earendil-works/pi-ai/providers/all";
import type { RuntimeEventSink, WorkerOptions, WorkerState } from "./contracts.ts";
import { ReadOnlyJsonCredentialStore } from "./credential-store.ts";
import { WorkerEventAdapter } from "./event-adapter.ts";
import {
	providerBudgetSupport,
	reasoningBudgetReceipt,
	reasoningStopReason,
	reasoningThinkingBudgets,
	safeThinkingLevel,
} from "./reasoning-budget.ts";
import { loadTaskContext } from "./task-context.ts";
import { createWorkerTools, progressDigest, validateSubmittedOutputs } from "./tools.ts";
import { workerProfile } from "./worker-profile.ts";
import { readAuthorizedFile } from "./path-policy.ts";
import { executionIdentities, type ExecutionIdentities } from "./execution-identity.ts";
import { workerExecutionStrategy } from "./worker-strategy.ts";
import {
	ProviderReliabilitySession,
	classifyProviderFailure,
	providerStreamControls,
	type ProviderFailureKind,
	type ProviderReliabilityReceipt,
} from "./provider-reliability.ts";

const TOOL_NAMES = new Set([
	"read_task_context",
	"read_authorized_source",
	"write_expected_output",
	"validate_output",
	"complete_task",
	"request_repair",
	"report_blocker",
]);

export interface WorkerResult {
	status: "completed" | "blocked" | "incomplete";
	message: string;
	failureKind?: "provider_empty_response" | ProviderFailureKind;
	providerError?: string;
	providerFailureRetryable?: boolean;
	taskId: string;
	provider: string;
	model: string;
	turns: number;
	toolCalls: number;
	providerRequests: number;
	reasoningCharacters: number;
	textCharacters: number;
	writtenOutputs: string[];
	validationPassed: boolean;
	reasoning_budget: ReturnType<typeof reasoningBudgetReceipt>;
	provider_reliability: ProviderReliabilityReceipt;
	runSessionId: string;
	promptCacheKey: string;
	executionStrategy: string;
}

export async function runWorker(options: WorkerOptions, prompt: string, emit: RuntimeEventSink): Promise<WorkerResult> {
	const context = await loadTaskContext(options.workspace, options.allowedStates, options.repairTargets);
	const [provider, modelId] = parseModelId(options.model);
	const credentials = new ReadOnlyJsonCredentialStore(options.authPath);
	const models = builtinModels({ credentials });
	const model = models.getModel(provider, modelId);
	if (!model) throw new Error(`Pi AI model is not available: ${options.model}`);
	const auth = await models.getAuth(model);
	if (!auth) throw new Error(`Pi AI provider is not authenticated: ${provider}`);

	const state: WorkerState = {
		completed: false,
		blocked: false,
		blockerReason: "",
		turns: 0,
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
	const profile = workerProfile(context.agentRole, options.mode);
	const identities = executionIdentities(context, profile, options.model, options.mode);
	const sessionId = identities.runSessionId;
	const strategy = workerExecutionStrategy(context.agentRole);
	const repairSources = options.mode === "repair"
		? await existingRepairSources(context, options.workspace)
		: [];
	emit("runner.profile.bound", {
		schema: profile.schema,
		version: profile.version,
		role: profile.role,
		digest: profile.digest,
	});
	emit("runner.execution.identity", {
		run_session_id: identities.runSessionId,
		prompt_cache_key: identities.promptCacheKey,
	});
	emit("runner.strategy.bound", {
		strategy: strategy.id,
		semantic_judgment: strategy.semanticJudgment,
	});
	const budgetSupport = providerBudgetSupport(model, options.reasoningBudget);
	const effectiveThinking = safeThinkingLevel(model, options.thinking);
	if (effectiveThinking !== options.thinking) {
		emit("runner.reasoning.level.degraded", {
			requested_level: options.thinking,
			effective_level: effectiveThinking,
			reason: "provider-does-not-support-requested-level-without-upshift",
		});
	}
	const eventAdapter = new WorkerEventAdapter(sessionId, state, emit);
	const tools = createWorkerTools(context, options, state, emit);
	let requiredToolLease = "";
	let agent!: Agent;
	const reliability = new ProviderReliabilitySession(options.providerReliability, () => agent.abort());
	const streamControls = providerStreamControls(options.providerReliability);
	agent = new Agent({
		initialState: {
			systemPrompt: profile.systemPrompt,
			model,
			thinkingLevel: effectiveThinking,
			tools,
		},
		streamFn: (streamModel, streamContext, streamOptions = {}) => models.streamSimple(
			streamModel,
			streamContext,
			{ ...streamOptions, ...streamControls },
		),
		sessionId: identities.promptCacheKey,
		toolExecution: "sequential",
		thinkingBudgets: reasoningThinkingBudgets(options.reasoningBudget)
			?? { minimal: 128, low: 512, medium: 1024, high: 2048 },
		onPayload: (payload) => {
			reliability.beforeRequest(
				state.providerRequests,
				options.reasoningBudget.enabled
					? options.reasoningBudget.maxProviderRequests
					: Number.MAX_SAFE_INTEGER,
			);
			eventAdapter.providerRequest(provider, modelId);
			requiredToolLease = desiredWorkerTool(options, context, repairSources, state);
			return requiredToolLease ? bindRequiredTool(payload, model.api, requiredToolLease) : payload;
		},
		onResponse: (response) => reliability.observeResponse(response.status),
		beforeToolCall: async ({ toolCall }) => {
			if (!TOOL_NAMES.has(toolCall.name)) return { block: true, reason: "tool is outside the ArcVellum whitelist", terminate: true };
			if (state.completed || state.blocked) return { block: true, reason: "worker is already terminal", terminate: true };
			// A model may emit several sibling tool calls in one response. Freeze the
			// protocol requirement at provider-request time so the first sibling
			// cannot mutate state and retroactively invalidate the remaining calls.
			if (!toolMatchesLease(requiredToolLease, toolCall.name)) {
				return {
					block: true,
					reason: `worker protocol requires ${requiredToolLease} at this stage`,
					terminate: false,
				};
			}
			if (state.toolCalls > options.maxToolCalls) {
				state.blocked = true;
				state.blockerReason = "tool-call budget exhausted";
				return { block: true, reason: state.blockerReason, terminate: true };
			}
			return undefined;
		},
		afterToolCall: async ({ result }) => ({
			content: result.content.map((item) =>
				item.type === "text" && item.text.length > context.maxResultChars
					? { ...item, text: `${item.text.slice(0, context.maxResultChars)}\n[truncated by ArcVellum Worker]` }
					: item,
			),
		}),
		shouldStopAfterTurn: async () => {
			if (state.completed || state.blocked) return true;
			if (await settleValidOutputs(context, options.workspace, state)) return true;
			const budgetStop = reasoningStopReason(options.reasoningBudget, state);
			if (budgetStop) {
				state.reasoningStopReason = budgetStop;
				state.lastValidation = await validateSubmittedOutputs(
					context,
					options.workspace,
					state.writtenPaths,
				);
				if (state.lastValidation.passed && options.reasoningBudget.overBudgetAction === "validate_then_stop") {
					state.completed = true;
					return true;
				}
				state.blocked = true;
				state.blockerReason = budgetStop;
				return true;
			}
			const digest = await progressDigest(context, options.workspace, state);
			state.progressDigests.push(digest);
			if (state.progressDigests.length > 3) state.progressDigests.shift();
			const last = state.progressDigests;
			const repeated = repeatedProgressCount(last);
			if (repeated >= strategy.noProgressTurnLimit) {
				state.blocked = true;
				state.blockerReason = state.lastToolError
					? `no-progress guard stopped repeated tool failure: ${state.lastToolError.tool}: ${state.lastToolError.reason}`
					: `no-progress guard stopped ${repeated} identical turns`;
				return true;
			}
			if (state.turns >= options.maxTurns) {
				await settleTurnBudget(context, options.workspace, state);
				return true;
			}
			return false;
		},
	});
	agent.subscribe((event) => {
		reliability.observeAgentEvent(event);
		eventAdapter.handle(event);
	});
	let promptFailure = "";
	try {
		await agent.prompt(prompt);
	} catch (error) {
		promptFailure = sanitizeProviderError(error instanceof Error ? error.message : error);
	}

	const providerError = sanitizeProviderError(promptFailure || agent.state.errorMessage);
	const providerFailure = reliability.complete(providerError);
	if (providerFailure) {
		emit("runner.warning", {
			kind: providerFailure.kind,
			detail: sanitizeProviderError(providerFailure.message),
			retryable: providerFailure.retryable,
		});
		return buildResult(
			"blocked",
			providerFailure.message,
			context.taskId,
			provider,
			modelId,
			state,
			options,
			budgetSupport,
			effectiveThinking,
			providerFailure.kind,
			sanitizeProviderError(providerFailure.message),
			providerFailure.retryable,
			reliability.receipt(),
			identities,
			strategy.id,
		);
	}
	if (isProviderEmptyResponse(state)) {
		return buildResult(
			"incomplete",
			"provider returned an empty response with zero model activity",
			context.taskId,
			provider,
			modelId,
			state,
			options,
			budgetSupport,
			effectiveThinking,
			"provider_empty_response",
			undefined,
			true,
			reliability.receipt(),
			identities,
			strategy.id,
		);
	}
	if (state.completed) {
		return buildResult("completed", "outputs submitted for Studio preflight", context.taskId, provider, modelId, state, options, budgetSupport, effectiveThinking, undefined, undefined, undefined, reliability.receipt(), identities, strategy.id);
	}
	if (state.blocked) {
		return buildResult("blocked", state.blockerReason || "worker reported a blocker", context.taskId, provider, modelId, state, options, budgetSupport, effectiveThinking, undefined, undefined, undefined, reliability.receipt(), identities, strategy.id);
	}
	return buildResult("incomplete", "model stopped without calling complete_task", context.taskId, provider, modelId, state, options, budgetSupport, effectiveThinking, undefined, undefined, undefined, reliability.receipt(), identities, strategy.id);
}

export function toolMatchesLease(requiredToolLease: string, toolName: string): boolean {
	return !requiredToolLease || toolName === requiredToolLease;
}

async function existingRepairSources(
	context: Awaited<ReturnType<typeof loadTaskContext>>,
	workspace: string,
): Promise<string[]> {
	const existing: string[] = [];
	for (const output of context.agentOwnedOutputs) {
		try {
			await readAuthorizedFile(workspace, output.path);
			existing.push(output.path);
		} catch {
			// A missing repair target must be created directly.
		}
	}
	return existing;
}

export function desiredRepairTool(
	options: Pick<WorkerOptions, "mode">,
	repairSources: readonly string[],
	state: Pick<WorkerState, "readPaths" | "writtenPaths" | "lastValidation">,
	requiredOutputs: readonly string[] = repairSources,
): string {
	if (options.mode !== "repair") return "";
	if (repairSources.some((path) => !state.readPaths.has(path))) return "read_authorized_source";
	if (requiredOutputs.some((path) => !state.writtenPaths.has(path))) return "write_expected_output";
	if (state.lastValidation.issues.some((issue) => requiredOutputs.includes(issue.path))) {
		return "write_expected_output";
	}
	return "complete_task";
}

export function desiredWorkerTool(
	options: Pick<WorkerOptions, "mode">,
	context: Pick<Awaited<ReturnType<typeof loadTaskContext>>, "agentRole" | "agentOwnedOutputs">,
	repairSources: readonly string[],
	state: Pick<WorkerState, "completed" | "taskContextReads" | "readPaths" | "writtenPaths" | "lastValidation">,
): string {
	const requiredOutputs = context.agentOwnedOutputs.map((item) => item.path);
	const repairTool = desiredRepairTool(options, repairSources, state, requiredOutputs);
	if (repairTool) return repairTool;
	const submittedOutputFailedValidation = state.lastValidation.issues.some((issue) =>
		requiredOutputs.includes(issue.path) && state.writtenPaths.has(issue.path),
	);
	if (
		options.mode === "task"
		&& (
			requiredOutputs.some((path) => !state.writtenPaths.has(path))
			|| submittedOutputFailedValidation
		)
		&& !state.completed
	) {
		// A normal task prompt is a compiled, self-contained evidence program.
		// Enter the artifact channel immediately for every role; optional reads
		// here would contradict that contract, add a full provider round trip,
		// and let models oscillate between read and write phases. Repair mode is
		// the sole read-before-write path because it must inspect prior outputs.
		return "write_expected_output";
	}
	return "";
}

export function bindRequiredTool(payload: unknown, api: string, tool: string): unknown {
	if (!isRecord(payload)) return payload;
	if (api === "pi-messages") {
		const options = isRecord(payload.options) ? { ...payload.options } : {};
		const context = isRecord(payload.context)
			? restrictContextTools(payload.context, tool)
			: payload.context;
		return {
			...payload,
			context,
			options: {
				...options,
				toolChoice: { type: "function", function: { name: tool } },
			},
		};
	}
	if (api === "anthropic-messages") {
		return { ...payload, tools: restrictToolDefinitions(payload.tools, tool), tool_choice: { type: "tool", name: tool } };
	}
	if (api === "openai-responses" || api === "azure-openai-responses") {
		return { ...payload, tools: restrictToolDefinitions(payload.tools, tool), tool_choice: { type: "function", name: tool } };
	}
	if (api === "openai-codex-responses") {
		return { ...payload, tools: restrictToolDefinitions(payload.tools, tool), tool_choice: "required" };
	}
	if (api === "openai-completions" || api === "mistral-conversations") {
		return {
			...payload,
			tools: restrictToolDefinitions(payload.tools, tool),
			tool_choice: { type: "function", function: { name: tool } },
		};
	}
	if (api === "google-generative-ai" || api === "google-vertex" || api === "bedrock-converse-stream") {
		return restrictProviderToolConfig(payload, api, tool);
	}
	return payload;
}

/**
 * Treat the required tool as a capability lease, not only a sampling hint.
 * Some compatible gateways accept an exact tool choice while still exposing
 * stale tools to the underlying model. Removing those tools makes each Worker
 * protocol phase deterministic; beforeToolCall remains a fail-closed guard.
 */
export function restrictToolDefinitions(value: unknown, requiredTool: string): unknown {
	if (!Array.isArray(value)) return value;
	return value.filter((item) => toolDefinitionNames(item).includes(requiredTool));
}

function restrictContextTools(value: Record<string, unknown>, requiredTool: string): Record<string, unknown> {
	return { ...value, tools: restrictToolDefinitions(value.tools, requiredTool) };
}

function restrictProviderToolConfig(
	payload: Record<string, unknown>,
	api: string,
	requiredTool: string,
): Record<string, unknown> {
	if (api === "bedrock-converse-stream" && isRecord(payload.toolConfig)) {
		return {
			...payload,
			toolConfig: {
				...payload.toolConfig,
				tools: restrictToolDefinitions(payload.toolConfig.tools, requiredTool),
				toolChoice: { tool: { name: requiredTool } },
			},
		};
	}
	const tools = Array.isArray(payload.tools)
		? payload.tools.map((item) => {
			if (!isRecord(item) || !Array.isArray(item.functionDeclarations)) return item;
			return {
				...item,
				functionDeclarations: restrictToolDefinitions(item.functionDeclarations, requiredTool),
			};
		}).filter((item) => {
			if (!isRecord(item) || !Array.isArray(item.functionDeclarations)) return true;
			return item.functionDeclarations.length > 0;
		})
		: payload.tools;
	return { ...payload, tools, tool_choice: "any" };
}

function toolDefinitionNames(value: unknown): string[] {
	if (!isRecord(value)) return [];
	const names = [value.name];
	if (isRecord(value.function)) names.push(value.function.name);
	if (isRecord(value.toolSpec)) names.push(value.toolSpec.name);
	return names.filter((item): item is string => typeof item === "string" && item.length > 0);
}

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Close a bounded run safely when the model used its final turn to write or
 * validate outputs but did not have another turn available for complete_task.
 * Studio still performs the authoritative semantic preflight after process
 * exit, so this only accepts the Worker's narrow local output contract.
 */
export async function settleTurnBudget(
	context: Awaited<ReturnType<typeof loadTaskContext>>,
	workspace: string,
	state: WorkerState,
): Promise<void> {
	state.lastValidation = await validateSubmittedOutputs(
		context,
		workspace,
		state.writtenPaths,
	);
	if (state.lastValidation.passed) {
		state.completed = true;
		state.reasoningStopReason = "turn_limit_validated";
		return;
	}
	state.blocked = true;
	state.blockerReason = "turn budget exhausted before outputs passed local validation";
}

/**
 * Treat locally valid required outputs as a successful bounded handoff even
 * when a model forgets to call complete_task. Studio still owns semantic
 * preflight, so another identical validation turn has no useful work to do.
 */
export async function settleValidOutputs(
	context: Awaited<ReturnType<typeof loadTaskContext>>,
	workspace: string,
	state: WorkerState,
): Promise<boolean> {
	if (state.writtenPaths.size === 0) return false;
	const validation = await validateSubmittedOutputs(
		context,
		workspace,
		state.writtenPaths,
	);
	if (!validation.passed) {
		// This check is intentionally silent. The model must receive the exact
		// parser failures through validate_output/complete_task before a forced
		// rewrite. Publishing them only into internal state would make the next
		// provider turn guess at a repair and could trip the no-progress guard
		// before it had one informed correction attempt.
		return false;
	}
	state.lastValidation = validation;
	state.completed = true;
	state.reasoningStopReason = "local_outputs_validated";
	return true;
}

function buildResult(
	status: WorkerResult["status"],
	message: string,
	taskId: string,
	provider: string,
	model: string,
	state: WorkerState,
	options: WorkerOptions,
	budgetSupport: ReturnType<typeof providerBudgetSupport>,
	effectiveThinking: WorkerOptions["thinking"],
	failureKind?: WorkerResult["failureKind"],
	providerError?: string,
	providerFailureRetryable?: boolean,
	providerReliability?: ProviderReliabilityReceipt,
	identities: ExecutionIdentities = { runSessionId: "", promptCacheKey: "" },
	executionStrategy = "artifact",
): WorkerResult {
	const reliability = providerReliability ?? {
		policy: { ...options.providerReliability },
		request_count: state.providerRequests,
		response_count: 0,
		circuit_state: "closed" as const,
		failure: providerError ? classifyProviderFailure(providerError) : null,
	};
	return {
		status,
		message,
		...(failureKind ? { failureKind } : {}),
		...(providerError ? { providerError } : {}),
		...(providerFailureRetryable !== undefined ? { providerFailureRetryable } : {}),
		taskId,
		provider,
		model,
		turns: state.turns,
		toolCalls: state.toolCalls,
		providerRequests: state.providerRequests,
		reasoningCharacters: state.reasoningCharacters,
		textCharacters: state.textCharacters,
		writtenOutputs: [...state.writtenPaths].sort(),
		validationPassed: state.lastValidation.passed,
		reasoning_budget: reasoningBudgetReceipt(options.reasoningBudget, state, budgetSupport, effectiveThinking),
		provider_reliability: reliability,
		runSessionId: identities.runSessionId,
		promptCacheKey: identities.promptCacheKey,
		executionStrategy,
	};
}

export function isProviderEmptyResponse(state: WorkerState): boolean {
	return state.providerRequests > 0
		&& state.toolCalls === 0
		&& state.reasoningCharacters === 0
		&& state.textCharacters === 0
		&& state.writtenPaths.size === 0;
}

export function sanitizeProviderError(value: unknown): string {
	return String(value ?? "")
		.replace(/[A-Za-z]:[\\/][^\s'"`]+/g, "<redacted-path>")
		.replace(/sk-[A-Za-z0-9_-]{20,}/g, "<redacted-secret>")
		.replace(/(?:api[_ -]?key|authorization|bearer)\s*[:=]?\s*[A-Za-z0-9._-]{12,}/gi, "<redacted-credential>")
		.replace(/[\r\n\t]+/g, " ")
		.replace(/\s+/g, " ")
		.trim()
		.slice(0, 1000);
}

function parseModelId(value: string): [string, string] {
	const separator = value.indexOf("/");
	if (separator <= 0 || separator === value.length - 1) throw new Error("model must use provider/model format");
	return [value.slice(0, separator), value.slice(separator + 1)];
}

export function noProgressTurnLimit(agentRole: string): number {
	return workerExecutionStrategy(agentRole).noProgressTurnLimit;
}

function repeatedProgressCount(values: readonly string[]): number {
	const latest = values.at(-1);
	if (!latest) return 0;
	let count = 0;
	for (let index = values.length - 1; index >= 0 && values[index] === latest; index -= 1) count += 1;
	return count;
}
