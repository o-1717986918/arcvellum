#!/usr/bin/env node

import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { readFile } from "node:fs/promises";
import type { ReasoningBudget, RuntimeEventSink, WorkerOptions } from "./contracts.ts";
import { validateReasoningBudget } from "./reasoning-budget.ts";
import { runWorker } from "./worker.ts";

const VERSION = "0.1.0";
const DEFAULT_STATES = ["asset-creation-agent-task", "canon-review-agent-task", "candidate-review"];

async function main(): Promise<number> {
	const args = process.argv.slice(2);
	if (args.includes("--version")) {
		process.stdout.write(`arcvellum-pi-worker ${VERSION}\n`);
		return 0;
	}
	const options = parseOptions(args);
	const prompt = (await readStdin()).trim() || await readFile(join(options.workspace, "AGENT_TASK.md"), "utf8");
	const emit: RuntimeEventSink = (event, data = {}) => {
		process.stdout.write(`${JSON.stringify({ event, data, at: new Date().toISOString() })}\n`);
	};
	try {
		emit("runner.ready", { runner_id: "pi-worker", version: VERSION });
		const result = await runWorker(options, prompt, emit);
		emit("runner.worker.result", result as unknown as Record<string, unknown>);
		return result.status === "completed" ? 0 : 2;
	} catch (error) {
		emit("runner.warning", { kind: "worker_error", detail: sanitizeError(error, options) });
		return 1;
	}
}

function parseOptions(args: string[]): WorkerOptions {
	const values = new Map<string, string[]>();
	for (let index = 0; index < args.length; index += 1) {
		const name = args[index];
		if (!name?.startsWith("--")) throw new Error(`unexpected argument: ${name ?? ""}`);
		const value = args[index + 1];
		if (!value || value.startsWith("--")) throw new Error(`missing value for ${name}`);
		values.set(name, [...(values.get(name) ?? []), value]);
		index += 1;
	}
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
	};
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

function sanitizeError(error: unknown, options: WorkerOptions): string {
	const message = error instanceof Error ? error.message : String(error);
	return message.replaceAll(options.workspace, "[workspace]").replaceAll(options.authPath, "[auth]");
}

process.exitCode = await main();
