import { createHash } from "node:crypto";
import type { RuntimeEventSink } from "./contracts.ts";

const count = (value: unknown): number | null =>
  typeof value === "number" && Number.isSafeInteger(value) && value >= 0 ? value : null;
const record = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const digest = (value: string) => createHash("sha256").update(value).digest("hex");

export function cacheUsageObservation(value: unknown) {
  const usage = record(value) ? value : {};
  const details = record(usage.prompt_tokens_details) ? usage.prompt_tokens_details : {};
  const openai = count(details.cached_tokens);
  const native = count(usage.prompt_cache_hit_tokens);
  const miss = count(usage.prompt_cache_miss_tokens);
  const input = count(usage.prompt_tokens);
  const hit = openai ?? native;
  const inconsistent = (openai !== null && native !== null && openai !== native) ||
    (input !== null && hit !== null && hit > input) ||
    (input !== null && hit !== null && miss !== null && hit + miss !== input);
  return {
    schema: "arcvellum/cache-usage/v1",
    status: inconsistent ? "inconsistent" : hit === null ? "not-reported" : "reported",
    prompt_tokens: input, cache_read_tokens: inconsistent ? null : hit,
    cache_miss_tokens: miss, openai_cached_tokens: openai, native_hit_tokens: native,
    cache_write_tokens: count(details.cache_write_tokens),
    completion_tokens: count(usage.completion_tokens),
  };
}

/** Bounded, pass-through SSE observation. No choices, text, reasoning or headers are retained. */
export function observeCacheStream(response: Response, emit: RuntimeEventSink, identity: Record<string, unknown>): Response {
  if (!response.ok || !response.body || !response.headers.get("content-type")?.includes("text/event-stream")) return response;
  let tail = "";
  let skipping = false;
  const decoder = new TextDecoder();
  const observeLine = (line: string) => {
    if (!line.startsWith("data:")) return;
    try {
      const value: unknown = JSON.parse(line.slice(5).trim());
      if (record(value) && record(value.usage))
        emit("runner.cache.usage.observed", { ...identity, ...cacheUsageObservation(value.usage) });
    } catch { /* A malformed event must not change the SDK's response stream. */ }
  };
  const tap = new TransformStream<Uint8Array, Uint8Array>({
    transform(chunk, controller) {
      controller.enqueue(chunk);
      const text = decoder.decode(chunk, { stream: true });
      for (const part of text.split(/(?<=\n)/)) {
        if (!skipping) tail += part;
        if (tail.length > 65_536) { tail = ""; skipping = true; }
        if (part.endsWith("\n")) {
          if (!skipping) observeLine(tail.trimEnd());
          tail = ""; skipping = false;
        }
      }
    },
    flush() { if (!skipping) observeLine((tail + decoder.decode()).trimEnd()); },
  });
  return new Response(response.body.pipeThrough(tap), {
    status: response.status, statusText: response.statusText, headers: response.headers,
  });
}

/** Exact serialized request changes inside one process; lengths are bytes, not model tokens. */
export class RequestShapeObserver {
  private previous: string | undefined;
  private emit: RuntimeEventSink;
  private identity: () => Record<string, unknown>;
  constructor(emit: RuntimeEventSink, identity: () => Record<string, unknown>) { this.emit=emit;this.identity=identity; }
  observe(payload: unknown): void {
    if (!record(payload)) return;
    const shape = JSON.stringify({ messages: payload.messages, tools: payload.tools });
    const current = Buffer.from(shape, "utf8");
    const prior = this.previous === undefined ? undefined : Buffer.from(this.previous, "utf8");
    let common = 0;
    if (prior) while (common < Math.min(prior.length, current.length) && prior[common] === current[common]) common++;
    this.emit("runner.cache.request.shape", {
      ...this.identity(), schema: "arcvellum/request-shape/v1", shape_sha256: digest(shape),
      input_bytes: current.length, common_prefix_bytes: prior ? common : null,
      previous_shape_available: Boolean(prior),
      messages_sha256: digest(JSON.stringify(payload.messages ?? [])),
      tools_sha256: digest(JSON.stringify(payload.tools ?? [])),
      message_count: Array.isArray(payload.messages) ? payload.messages.length : 0,
      tool_count: Array.isArray(payload.tools) ? payload.tools.length : 0,
    });
    // One bounded process-local comparison, never a persisted second copy of prose.
    this.previous = current.length <= 8_000_000 ? shape : undefined;
  }
}
