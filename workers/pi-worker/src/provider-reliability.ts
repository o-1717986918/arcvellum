import type { AgentEvent } from "@earendil-works/pi-agent-core";
import type { ProviderReliabilityPolicy } from "./contracts.ts";

export const PROVIDER_FAILURE_KINDS = [
	"provider_quota",
	"authentication_failure",
	"transient_network",
	"first_event_timeout",
	"idle_timeout",
	"total_timeout",
	"model_error",
	"validation_failure",
	"cancelled",
] as const;

export type ProviderFailureKind = typeof PROVIDER_FAILURE_KINDS[number];

export interface ProviderFailure {
	kind: ProviderFailureKind;
	retryable: boolean;
	code: string;
	message: string;
}

export interface ProviderReliabilityReceipt {
	policy: ProviderReliabilityPolicy;
	request_count: number;
	response_count: number;
	circuit_state: "closed" | "open" | "half_open";
	failure: ProviderFailure | null;
}

export class ProviderReliabilityError extends Error {
	readonly failure: ProviderFailure;

	constructor(failure: ProviderFailure) {
		super(`[arcvellum:${failure.kind}] ${failure.message}`);
		this.name = "ProviderReliabilityError";
		this.failure = failure;
	}
}

export class ProviderCircuitBreaker {
	private consecutiveFailures = 0;
	private openedAt = 0;
	private terminalOpen = false;
	private readonly threshold: number;
	private readonly cooldownMs: number;
	private readonly now: () => number;

	constructor(threshold: number, cooldownMs: number, now: () => number = Date.now) {
		this.threshold = Math.max(1, Math.trunc(threshold));
		this.cooldownMs = Math.max(1, Math.trunc(cooldownMs));
		this.now = now;
	}

	assertRequestAllowed(): void {
		if (this.state() === "open") {
			throw new ProviderReliabilityError({
				kind: "transient_network",
				retryable: false,
				code: "provider_circuit_open",
				message: "provider circuit is open after repeated transport failures",
			});
		}
	}

	recordSuccess(): void {
		this.consecutiveFailures = 0;
		this.openedAt = 0;
		this.terminalOpen = false;
	}

	recordFailure(failure: ProviderFailure): void {
		if (failure.kind === "authentication_failure" || failure.kind === "provider_quota") {
			this.terminalOpen = true;
			this.openedAt = this.now();
			return;
		}
		if (!failure.retryable) return;
		this.consecutiveFailures += 1;
		if (this.consecutiveFailures >= this.threshold) this.openedAt = this.now();
	}

	state(): "closed" | "open" | "half_open" {
		if (this.terminalOpen) return "open";
		if (!this.openedAt) return "closed";
		return this.now() - this.openedAt >= this.cooldownMs ? "half_open" : "open";
	}
}

export class ProviderActivityWatchdog {
	private firstTimer: ReturnType<typeof setTimeout> | undefined;
	private idleTimer: ReturnType<typeof setTimeout> | undefined;
	private totalTimer: ReturnType<typeof setTimeout> | undefined;
	private abortRequest: (() => void) | undefined;
	private active = false;
	private _failure: ProviderFailure | null = null;
	private readonly policy: ProviderReliabilityPolicy;
	private readonly onFailure: (failure: ProviderFailure) => void;

	constructor(policy: ProviderReliabilityPolicy, onFailure: (failure: ProviderFailure) => void = () => undefined) {
		this.policy = policy;
		this.onFailure = onFailure;
	}

	get failure(): ProviderFailure | null {
		return this._failure;
	}

	arm(abortRequest: () => void): void {
		this.completeRequest();
		this._failure = null;
		this.abortRequest = abortRequest;
		this.active = true;
		this.firstTimer = armTimer(this.policy.firstEventTimeoutMs, () => this.trip("first_event_timeout"));
		this.totalTimer = armTimer(this.policy.totalTimeoutMs, () => this.trip("total_timeout"));
	}

	observeResponse(): void {
		if (!this.active) return;
		clearTimer(this.firstTimer);
		this.firstTimer = undefined;
		this.resetIdleTimer();
	}

	observeAgentEvent(event: AgentEvent): void {
		if (!this.active) return;
		if (event.type === "message_start" || event.type === "message_update") {
			this.observeResponse();
			return;
		}
		if (event.type === "message_end" || event.type === "agent_end") this.completeRequest();
	}

	completeRequest(): void {
		clearTimer(this.firstTimer);
		clearTimer(this.idleTimer);
		clearTimer(this.totalTimer);
		this.firstTimer = undefined;
		this.idleTimer = undefined;
		this.totalTimer = undefined;
		this.abortRequest = undefined;
		this.active = false;
	}

	private resetIdleTimer(): void {
		clearTimer(this.idleTimer);
		this.idleTimer = armTimer(this.policy.interEventTimeoutMs, () => this.trip("idle_timeout"));
	}

	private trip(kind: "first_event_timeout" | "idle_timeout" | "total_timeout"): void {
		if (!this.active || this._failure) return;
		const failure: ProviderFailure = {
			kind,
			retryable: true,
			code: kind,
			message: timeoutMessage(kind),
		};
		this._failure = failure;
		const abort = this.abortRequest;
		this.completeRequest();
		this.onFailure(failure);
		abort?.();
	}
}

export class ProviderReliabilitySession {
	private requests = 0;
	private responses = 0;
	private _failure: ProviderFailure | null = null;
	readonly circuit: ProviderCircuitBreaker;
	readonly watchdog: ProviderActivityWatchdog;
	readonly policy: ProviderReliabilityPolicy;

	constructor(policy: ProviderReliabilityPolicy, abortRequest: () => void) {
		this.policy = policy;
		this.circuit = new ProviderCircuitBreaker(policy.circuitFailureThreshold, policy.circuitCooldownMs);
		this.watchdog = new ProviderActivityWatchdog(policy, (failure) => this.recordFailure(failure));
		this.abortRequest = abortRequest;
	}

	private readonly abortRequest: () => void;

	beforeRequest(currentRequests: number, maximumRequests: number): void {
		if (currentRequests >= maximumRequests) {
			throw new ProviderReliabilityError({
				kind: "validation_failure",
				retryable: false,
				code: "provider_request_budget_exhausted",
				message: "provider request budget exhausted before the next request",
			});
		}
		this.circuit.assertRequestAllowed();
		this.requests += 1;
		this.watchdog.arm(this.abortRequest);
	}

	observeResponse(status: number): void {
		this.responses += 1;
		this.watchdog.observeResponse();
		const failure = classifyProviderFailure("", status);
		if (failure) this.recordFailure(failure);
		else {
			this._failure = null;
			this.circuit.recordSuccess();
		}
	}

	observeAgentEvent(event: AgentEvent): void {
		this.watchdog.observeAgentEvent(event);
	}

	recordFailure(failure: ProviderFailure): void {
		this._failure = failure;
		this.circuit.recordFailure(failure);
	}

	complete(error: unknown): ProviderFailure | null {
		this.watchdog.completeRequest();
		const failure = this.watchdog.failure ?? classifyProviderFailure(error) ?? this._failure;
		if (failure) this.recordFailure(failure);
		else this.circuit.recordSuccess();
		return failure;
	}

	receipt(): ProviderReliabilityReceipt {
		return {
			policy: { ...this.policy },
			request_count: this.requests,
			response_count: this.responses,
			circuit_state: this.circuit.state(),
			failure: this._failure ? { ...this._failure } : null,
		};
	}
}

export function classifyProviderFailure(error: unknown, httpStatus = 0): ProviderFailure | null {
	const message = String(error instanceof Error ? error.message : error ?? "").trim();
	const normalized = message.toLowerCase();
	const tagged = taggedFailure(normalized);
	if (tagged) {
		return failure(
			tagged,
			message || tagged,
			["transient_network", "first_event_timeout", "idle_timeout", "total_timeout"].includes(tagged),
		);
	}
	if (httpStatus === 401 || httpStatus === 403 || /unauthori[sz]ed|invalid api key|authentication/.test(normalized)) {
		return failure("authentication_failure", message || `provider returned HTTP ${httpStatus}`, false);
	}
	if (httpStatus === 402 || /insufficient balance|billing|required quota|quota exceeded|payment required/.test(normalized)) {
		return failure("provider_quota", message || `provider returned HTTP ${httpStatus}`, false);
	}
	if (/\babort(ed)?\b|cancelled|canceled/.test(normalized)) return failure("cancelled", message, false);
	if (/schema|validation|invalid output|tool arguments/.test(normalized)) return failure("validation_failure", message, false);
	if (
		httpStatus === 408 || httpStatus === 409 || httpStatus === 425 || httpStatus === 429 || httpStatus >= 500
		|| /timed? out|timeout|econnreset|econnrefused|enotfound|network|socket|temporar|rate limit|overloaded/.test(normalized)
	) return failure("transient_network", message || `provider returned HTTP ${httpStatus}`, true);
	if (httpStatus === 400 || httpStatus === 404 || /model .*not found|unsupported model|context length/.test(normalized)) {
		return failure("model_error", message || `provider returned HTTP ${httpStatus}`, false);
	}
	return message ? failure("model_error", message, false) : null;
}

export function providerStreamControls(policy: ProviderReliabilityPolicy): {
	timeoutMs: number;
	maxRetries: number;
} {
	return {
		timeoutMs: policy.totalTimeoutMs,
		maxRetries: policy.maxRetries,
	};
}

function taggedFailure(value: string): ProviderFailureKind | null {
	for (const kind of PROVIDER_FAILURE_KINDS) {
		if (value.includes(`[arcvellum:${kind}]`)) return kind;
	}
	return null;
}

function failure(kind: ProviderFailureKind, message: string, retryable: boolean): ProviderFailure {
	return { kind, retryable, code: kind, message: message || kind };
}

function timeoutMessage(kind: "first_event_timeout" | "idle_timeout" | "total_timeout"): string {
	if (kind === "first_event_timeout") return "provider produced no HTTP response or model event before the first-event deadline";
	if (kind === "idle_timeout") return "provider stream stopped producing model events before completion";
	return "provider request exceeded its total deadline";
}

function armTimer(delayMs: number, callback: () => void): ReturnType<typeof setTimeout> {
	const timer = setTimeout(callback, Math.max(1, Math.trunc(delayMs)));
	timer.unref?.();
	return timer;
}

function clearTimer(timer: ReturnType<typeof setTimeout> | undefined): void {
	if (timer) clearTimeout(timer);
}
