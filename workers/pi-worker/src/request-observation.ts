import { randomUUID } from "node:crypto";
import type { RuntimeEventSink } from "./contracts.ts";

/** Observe Pi SDK transport attempts without reading payloads, headers, or streams. */
export function observeSdkFetch(
	emit: RuntimeEventSink,
	context: () => Record<string, unknown>,
	transport: typeof globalThis.fetch = globalThis.fetch,
): typeof globalThis.fetch {
	return async (input, init) => {
		const identity = { ...context(), http_attempt_id: randomUUID(), http_started_at: new Date().toISOString() };
		emit("runner.http.attempt.started", identity);
		try {
			const response = await transport(input, init);
			emit("runner.http.attempt.completed", { ...identity, status: response.status });
			return response;
		} catch (error) {
			emit("runner.http.attempt.failed", { ...identity, outcome: "transport-error" });
			throw error;
		}
	};
}
