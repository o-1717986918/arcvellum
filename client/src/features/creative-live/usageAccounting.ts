import type { CreativeLiveEvent, CreativeLiveSnapshot, UsageAccounting } from "./types";

export function usageIdentity(event: CreativeLiveEvent): string {
  const id = String(event.data.usage_id || "");
  return id.startsWith("arcvellum-conversation-") ? id : id
    ? [event.data.invocation_id || event.data.session_id || "", id].join(":") : event.event_id;
}

export function reduceAccounting(snapshot: CreativeLiveSnapshot, event: CreativeLiveEvent): UsageAccounting {
  const previous = snapshot.usage_accounting || emptyAccounting(snapshot);
  const data = event.data;
  const result = { ...previous };
  for (const [name, field, id] of [
    ["role.invocation.started", "invocation_ids", "invocation_id"],
    ["runner.provider.request.started", "model_request_ids", "model_request_id"],
    ["runner.http.attempt.started", "http_attempt_ids", "http_attempt_id"],
  ] as const) {
    if (event.event === name && data[id]) result[field] = [...new Set([...(result[field] || []), String(data[id])])];
  }
  result.outer_invocations = Math.max(previous.outer_invocations, result.invocation_ids?.length || 0);
  result.recorded_model_turns = Math.max(previous.recorded_model_turns, result.model_request_ids?.length || 0);
  result.observed_http_attempts = result.http_attempt_ids?.length || previous.observed_http_attempts;
  result.unknown_usage_invocations = (result.invocation_ids || []).filter((id) =>
    !(result.usage_invocation_ids || []).includes(id)).length;
  result.public_estimate_complete = (previous.unknown_public_price_updates || 0) === 0
    && previous.updates > 0 && result.unknown_usage_invocations === 0;
  if (event.channel !== "usage") return result;
  const identity = usageIdentity(event);
  if (previous.usage_ids.includes(identity)) return result;
  result.usage_ids = [...previous.usage_ids, identity];
  result.updates += 1;
  if (data.invocation_id) result.usage_invocation_ids = [...new Set([...(previous.usage_invocation_ids || []),String(data.invocation_id)])];
  result.unknown_usage_invocations = (result.invocation_ids || []).filter((id) =>
    !(result.usage_invocation_ids || []).includes(id)).length;
  const usage = data.usage && typeof data.usage === "object" ? data.usage as Record<string, unknown> : {};
  const available = data.usage_available !== false && number(usage.total_tokens) > 0;
  result.unknown_usage_updates += Number(!available);
  result.total_tokens += number(usage.total_tokens);
  result.token_details = { ...previous.token_details };
  for (const key of ["input", "output", "reasoning", "cache_read", "cache_write", "total_tokens"]) {
    result.token_details[key] = (result.token_details[key] || 0) + number(usage[key]);
  }
  if (!available || data.cost_usd == null || number(data.cost_usd) === 0) result.unknown_catalog_cost_updates += 1;
  else result.catalog_estimate_usd += number(data.cost_usd);
  result.cost_usd = result.catalog_estimate_usd;
  const price = data.price_estimate && typeof data.price_estimate === "object"
    ? data.price_estimate as Record<string, unknown> : null;
  if (available && price?.currency === "CNY" && price.amount != null) {
    result.public_estimate_cny = (result.public_estimate_cny || 0) + number(price.amount);
    const source = { source: String(price.source || ""), observed_at: String(price.observed_at || ""), currency: "CNY" };
    result.price_sources = [...previous.price_sources.filter((item) =>
      item.source !== source.source || item.observed_at !== source.observed_at), source];
  } else result.unknown_public_price_updates = (previous.unknown_public_price_updates || 0) + 1;
  result.public_estimate_complete = !result.unknown_public_price_updates && !result.unknown_usage_invocations;
  if (!result.model_request_ids?.length) result.recorded_model_turns = result.updates;
  return result;
}

function emptyAccounting(snapshot: CreativeLiveSnapshot): UsageAccounting {
  return { ...snapshot.usage, token_details: {}, outer_invocations: 0, recorded_model_turns: snapshot.usage.updates,
    observed_http_attempts: null, unknown_usage_updates: 0, unknown_catalog_cost_updates: 0,
    catalog_estimate_usd: snapshot.usage.cost_usd, public_estimate_cny: null, public_estimate_complete: false,
    price_sources: [], actual_charge: null, cost_source: "runtime-model-catalog-estimate",
    usage_ids: snapshot.events.filter((event) => event.channel === "usage").map(usageIdentity) };
}

function number(value: unknown): number {
  const parsed = Number(value || 0);
  return Number.isFinite(parsed) ? Math.max(0, parsed) : 0;
}
