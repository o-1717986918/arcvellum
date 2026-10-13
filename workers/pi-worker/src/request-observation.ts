import { randomUUID, createHash } from "node:crypto";
import { observeCacheStream } from "./cache-observation.ts";
import type { RuntimeEventSink } from "./contracts.ts";

/** Observe SDK attempts and bounded usage counters without retaining response content. */
export function observeSdkFetch(
	emit: RuntimeEventSink,
	context: () => Record<string, unknown>,
	transport: typeof globalThis.fetch = globalThis.fetch,
): typeof globalThis.fetch {
	return async (input, init) => {
		const url = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
		const endpoint = createHash("sha256").update(url.origin + url.pathname).digest("hex");
		const identity = { ...context(), endpoint_sha256: endpoint, http_attempt_id: randomUUID(), http_started_at: new Date().toISOString() };
		emit("runner.http.attempt.started", identity);
		try {
			const response = await transport(input, init);
			emit("runner.http.attempt.completed", { ...identity, status: response.status });
			return observeCacheStream(response, emit, identity);
		} catch (error) {
			emit("runner.http.attempt.failed", { ...identity, outcome: "transport-error" });
			throw error;
		}
	};
}
