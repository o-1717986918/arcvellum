import type { AgentEvent } from "@earendil-works/pi-agent-core";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ProviderReliabilityPolicy } from "../src/contracts.ts";
import {
	ProviderActivityWatchdog,
	ProviderCircuitBreaker,
	ProviderReliabilityError,
	ProviderReliabilitySession,
	classifyProviderFailure,
	providerStreamControls,
} from "../src/provider-reliability.ts";

const policy: ProviderReliabilityPolicy = {
	firstEventTimeoutMs: 100,
	interEventTimeoutMs: 200,
	totalTimeoutMs: 500,
	maxRetries: 1,
	circuitFailureThreshold: 2,
	circuitCooldownMs: 1_000,
};

afterEach(() => vi.useRealTimers());

describe("provider failure classification", () => {
	it("keeps quota and authentication terminal while transport failures retryable", () => {
		expect(classifyProviderFailure("Insufficient Balance", 402)).toMatchObject({
			kind: "provider_quota",
			retryable: false,
		});
		expect(classifyProviderFailure("invalid API key", 401)).toMatchObject({
			kind: "authentication_failure",
			retryable: false,
		});
		expect(classifyProviderFailure("rate limited", 429)).toMatchObject({
			kind: "transient_network",
			retryable: true,
		});
		expect(classifyProviderFailure("socket ECONNRESET")).toMatchObject({ kind: "transient_network" });
		expect(classifyProviderFailure("unsupported model", 400)).toMatchObject({
			kind: "model_error",
			retryable: false,
		});
	});

	it("preserves explicit ArcVellum timeout tags", () => {
		expect(classifyProviderFailure("[arcvellum:idle_timeout] stalled")).toMatchObject({
			kind: "idle_timeout",
			retryable: true,
		});
	});
});

describe("provider activity watchdog", () => {
	it("aborts when no HTTP response or model event arrives", () => {
		vi.useFakeTimers();
		const abort = vi.fn();
		const failures: string[] = [];
		const watchdog = new ProviderActivityWatchdog(policy, (failure) => failures.push(failure.kind));
		watchdog.arm(abort);
		vi.advanceTimersByTime(101);
		expect(abort).toHaveBeenCalledOnce();
		expect(failures).toEqual(["first_event_timeout"]);
	});

	it("moves from first-byte monitoring to idle monitoring and clears on completion", () => {
		vi.useFakeTimers();
		const abort = vi.fn();
		const watchdog = new ProviderActivityWatchdog(policy);
		watchdog.arm(abort);
		vi.advanceTimersByTime(80);
		watchdog.observeResponse();
		vi.advanceTimersByTime(180);
		watchdog.observeAgentEvent({ type: "message_update" } as AgentEvent);
		vi.advanceTimersByTime(180);
		expect(abort).not.toHaveBeenCalled();
		watchdog.observeAgentEvent({ type: "message_end" } as AgentEvent);
		vi.advanceTimersByTime(1_000);
		expect(abort).not.toHaveBeenCalled();
	});

	it("aborts an established stream after its idle deadline", () => {
		vi.useFakeTimers();
		const abort = vi.fn();
		const watchdog = new ProviderActivityWatchdog(policy);
		watchdog.arm(abort);
		watchdog.observeResponse();
		vi.advanceTimersByTime(201);
		expect(watchdog.failure?.kind).toBe("idle_timeout");
		expect(abort).toHaveBeenCalledOnce();
	});
});

describe("provider circuit and request budget", () => {
	it("opens after bounded transient failures and half-opens after cooldown", () => {
		let now = 10;
		const circuit = new ProviderCircuitBreaker(2, 100, () => now);
		const transient = classifyProviderFailure("network timeout")!;
		circuit.recordFailure(transient);
		expect(circuit.state()).toBe("closed");
		circuit.recordFailure(transient);
		expect(circuit.state()).toBe("open");
		expect(() => circuit.assertRequestAllowed()).toThrow(ProviderReliabilityError);
		now = 111;
		expect(circuit.state()).toBe("half_open");
	});

	it("rejects the next provider call before exceeding its budget", () => {
		const session = new ProviderReliabilitySession(policy, () => undefined);
		session.beforeRequest(0, 1);
		expect(() => session.beforeRequest(1, 1)).toThrow(/budget exhausted before/);
		expect(session.receipt().request_count).toBe(1);
	});

	it("compiles provider SDK controls from one policy", () => {
		expect(providerStreamControls(policy)).toEqual({ timeoutMs: 500, maxRetries: 1 });
	});
});
