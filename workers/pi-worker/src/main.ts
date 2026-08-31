#!/usr/bin/env node

import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { readFile } from "node:fs/promises";
import { builtinModels } from "@earendil-works/pi-ai/providers/all";
import type { ReasoningBudget, RuntimeEventSink, WorkerOptions } from "./contracts.ts";
import { ReadOnlyJsonCredentialStore } from "./credential-store.ts";
import { validateReasoningBudget } from "./reasoning-budget.ts";
import { runWorker } from "./worker.ts";
import { runConversation } from "./conversation.ts";

const VERSION = "0.99.2";
const DEFAULT_STATES = ["asset-creation-agent-task", "canon-review-agent-task", "candidate-review"];

async function main(): Promise<number> {
	const args = process.argv.slice(2);
	if (args.includes("--version")) {
		process.stdout.write(`arcvellum-pi-worker ${VERSION}\n`);
		return 0;
	}
	if (args.includes("--catalog")) {
		await writeCatalog(args);
		return 0;
	}
	const options = parseOptions(args);
	const prompt = (await readStdin()).trim() || await readFile(join(options.workspace, "AGENT_TASK.md"), "utf8");
	const emit: RuntimeEventSink = (event, data = {}) => {
		process.stdout.write(`${JSON.stringify({ event, data, at: new Date().toISOString() })}\n`);
	};
	try {
		emit("runner.ready", { runner_id: "pi-worker", version: VERSION });
		const result = options.mode === "conversation"
			? await runConversation(options, prompt, emit)
			: await runWorker(options, prompt, emit);
		emit("runner.worker.result", result as unknown as Record<string, unknown>);
		return result.status === "completed" ? 0 : 2;
	} catch (error) {
		emit("runner.warning", { kind: "worker_error", detail: sanitizeError(error, options) });
		return 1;
	}
}

async function writeCatalog(args: string[]): Promise<void> {
	const values = optionValues(args.filter((item) => item !== "--catalog"));
	const suppliedAuthPath = single(values, "--auth-path");
	const authPath = resolve(
		suppliedAuthPath
			|| (process.env.PI_CODING_AGENT_DIR
				? join(process.env.PI_CODING_AGENT_DIR, "auth.json")
				: join(homedir(), ".pi", "agent", "auth.json")),
	);
	const credentials = new ReadOnlyJsonCredentialStore(authPath);
	const connected = new Set((await credentials.list()).map((item) => item.providerId));
	const models = builtinModels({ credentials });
	const providers = models.getProviders().map((provider) => ({
		id: provider.id,
		name: provider.name,
		connected: connected.has(provider.id),
		auth_methods: Object.keys(provider.auth ?? {}),
		models: models.getModels(provider.id).map((model) => ({
			id: model.id,
			qualified_id: `${provider.id}/${model.id}`,
			name: model.name,
			context: model.contextWindow,
			max_output: model.maxTokens,
			reasoning: model.reasoning,
		})),
	}));
	process.stdout.write(`${JSON.stringify({
		schema: "arcvellum/pi-worker-catalog/v1",
		worker_version: VERSION,
		providers,
		connected_provider_count: providers.filter((item) => item.connected).length,
		available_model_count: providers.filter((item) => item.connected).reduce((count, item) => count + item.models.length, 0),
	})}\n`);
}

function parseOptions(args: string[]): WorkerOptions {
	const values = optionValues(args);
	const workspace = resolve(single(values, "--workspace") || process.cwd());
	const model = required(values, "--model");
	const suppliedAuthPath = single(values, "--auth-path");
	const authPath = resolve(
		suppliedAuthPath
			|| (process.env.PI_CODING_AGENT_DIR
				? join(process.env.PI_CODING_AGENT_DIR, "auth.json")
				: join(homedir(), ".pi", "agent", "auth.json")),
	);
	const thinkingValue = single(values, "--thinking") || "low";
	if (!isThinkingLevel(thinkingValue)) throw new Error(`unsupported thinking level: ${thinkingValue}`);
	const reasoningBudget = parseReasoningBudget(values, thinkingValue);
	validateReasoningBudget(reasoningBudget);
	const allowedStates = values.get("--allow-state") ?? DEFAULT_STATES;
	const mode = single(values, "--mode") || "task";
	if (!isWorkerMode(mode)) throw new Error(`unsupported worker mode: ${mode}`);
	const repairTargets = values.get("--repair-target") ?? [];
	const repairReferences = values.get("--repair-reference") ?? [];
	if (mode === "repair" && repairTargets.length === 0) {
		throw new Error("repair mode requires at least one --repair-target");
	}
	return {
		workspace,
		model,
		authPath,
		thinking: thinkingValue,
		maxTurns: positiveInteger(single(values, "--max-turns"), 6),
		maxToolCalls: positiveInteger(single(values, "--max-tools"), 12),
		maxRepairs: positiveInteger(single(values, "--max-repairs"), 1),
		allowedStates,
		reasoningBudget,
		providerReliability: {
			firstEventTimeoutMs: positiveInteger(single(values, "--first-event-timeout-ms"), 180_000),
			interEventTimeoutMs: positiveInteger(single(values, "--inter-event-timeout-ms"), 300_000),
			totalTimeoutMs: positiveInteger(single(values, "--provider-total-timeout-ms"), 900_000),
			maxRetries: nonNegativeInteger(single(values, "--provider-max-retries"), 1),
			circuitFailureThreshold: positiveInteger(single(values, "--provider-circuit-threshold"), 2),
			circuitCooldownMs: positiveInteger(single(values, "--provider-circuit-cooldown-ms"), 30_000),
		},
		mode,
		repairTargets,
		repairReferences,
	};
}

function optionValues(args: string[]): Map<string, string[]> {
	const values = new Map<string, string[]>();
	for (let index = 0; index < args.length; index += 1) {
		const name = args[index];
		if (!name?.startsWith("--")) throw new Error(`unexpected argument: ${name ?? ""}`);
		const value = args[index + 1];
		if (!value || value.startsWith("--")) throw new Error(`missing value for ${name}`);
		values.set(name, [...(values.get(name) ?? []), value]);
		index += 1;
	}
	return values;
}

function parseReasoningBudget(values: Map<string, string[]>, initialLevel: WorkerOptions["thinking"]): ReasoningBudget {
	const enabled = [
		"--max-thinking-level",
		"--reasoning-total",
		"--reasoning-per-request",
		"--max-provider-requests",
		"--max-reasoning-escalations",
	].some((name) => values.has(name));
	const maximumLevel = single(values, "--max-thinking-level") || initialLevel;
	if (!isThinkingLevel(maximumLevel)) throw new Error(`unsupported maximum thinking level: ${maximumLevel}`);
	return {
		enabled,
		initialLevel,
		maximumLevel,
		perRequestTokens: positiveInteger(single(values, "--reasoning-per-request"), 512),
		totalTokens: positiveInteger(single(values, "--reasoning-total"), 2048),
		maxProviderRequests: positiveInteger(single(values, "--max-provider-requests"), 4),
		maxEscalations: nonNegativeInteger(single(values, "--max-reasoning-escalations"), 0),
		overBudgetAction: "validate_then_stop",
	};
}

async function readStdin(): Promise<string> {
	let value = "";
	for await (const chunk of process.stdin) value += String(chunk);
	return value;
}

function required(values: Map<string, string[]>, name: string): string {
	const value = single(values, name);
	if (!value) throw new Error(`missing required option: ${name}`);
	return value;
}

function single(values: Map<string, string[]>, name: string): string {
	const items = values.get(name) ?? [];
	if (items.length > 1) throw new Error(`option may only be supplied once: ${name}`);
	return items[0] ?? "";
}

function positiveInteger(value: string, fallback: number): number {
	if (!value) return fallback;
	const parsed = Number(value);
	if (!Number.isInteger(parsed) || parsed <= 0) throw new Error(`expected a positive integer, received: ${value}`);
	return parsed;
}

function nonNegativeInteger(value: string, fallback: number): number {
	if (!value) return fallback;
	const parsed = Number(value);
	if (!Number.isInteger(parsed) || parsed < 0) throw new Error(`expected a non-negative integer, received: ${value}`);
	return parsed;
}

function isThinkingLevel(value: string): value is WorkerOptions["thinking"] {
	return ["off", "minimal", "low", "medium", "high", "xhigh", "max"].includes(value);
}

function isWorkerMode(value: string): value is WorkerOptions["mode"] {
	return value === "task" || value === "repair" || value === "conversation";
}

function sanitizeError(error: unknown, options: WorkerOptions): string {
	const message = error instanceof Error ? error.message : String(error);
	return message.replaceAll(options.workspace, "[workspace]").replaceAll(options.authPath, "[auth]");
}

process.exitCode = await main();
