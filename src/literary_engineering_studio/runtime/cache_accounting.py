"""Reported provider cache counters are independent from local reuse and SDK zeros."""
from collections import defaultdict


def summarize_server_cache(events):
    raw = _raw_observations(events)
    groups = {}
    for data in _usage_rows(events):
        observation = raw.get(data.get("model_request_id"), {})
        key = (data.get("provider", ""), observation.get("endpoint_sha256", ""),
               data.get("model", ""), data.get("call_purpose", data.get("role", "")),
               data.get("scene_transaction_id", ""), observation.get("request_series_id", ""))
        _add_response(groups.setdefault(key, _row(key)), data, observation)
    result = list(groups.values())
    for row in result:
        _ratios(row)
        row["uncached_reported_input_tokens"] = row["reported_input_tokens"] - row["cache_read_tokens"]
    totals = {name: sum(row[name] for row in result) for name in
              ("responses", "reported_responses", "unreported_responses", "inconsistent_responses",
               "total_input_tokens", "reported_input_tokens", "cache_read_tokens", "output_tokens")}
    _ratios(totals)
    return {"schema": "arcvellum/server-cache-accounting/v1", "totals": totals, "groups": result,
            "local_reuse_included": False, "cost_source": "runtime-model-catalog-estimate; provider billing unverified"}


def _raw_observations(events):
    result = {}
    for event in events:
        if event.get("event") == "runner.cache.usage.observed":
            data = event.get("data") or {}
            if data.get("model_request_id"):
                result[data["model_request_id"]] = data
    return result


def _usage_rows(events):
    seen = set()
    for event in events:
        if str(event.get("event", "")).startswith("runner.cache."):
            continue
        if event.get("event") != "usage.updated" and event.get("channel") != "usage":
            continue
        data = event.get("data") or event
        identity = data.get("usage_id") or data.get("model_request_id")
        if identity and identity not in seen:
            seen.add(identity)
            yield data


def _counters(data, observation):
    counters = data.get("usage") or {}
    status = observation.get("status") or ("legacy-positive" if counters.get("cache_read", 0) > 0 else "not-reported")
    hit = observation.get("cache_read_tokens", counters.get("cache_read", 0))
    prompt = observation.get("prompt_tokens")
    if prompt is None:
        prompt = sum(int(counters.get(name) or 0) for name in ("input", "cache_read", "cache_write"))
    if status == "reported" and hit != counters.get("cache_read", 0):
        status = "inconsistent"
    return counters, status, int(hit or 0), int(prompt or 0)


def _add_response(row, data, observation):
    counters, status, hit, prompt = _counters(data, observation)
    row["responses"] += 1
    row["output_tokens"] += int(counters.get("output") or 0)
    row["total_input_tokens"] += prompt
    row["catalog_estimate_usd"] += float(data.get("cost_usd") or 0)
    if status in {"reported", "legacy-positive"}:
        row["reported_responses"] += 1
        row["reported_input_tokens"] += prompt
        row["cache_read_tokens"] += hit
    else:
        row["inconsistent_responses" if status == "inconsistent" else "unreported_responses"] += 1


def _ratios(row):
    row["hit_ratio"] = row["cache_read_tokens"] / row["reported_input_tokens"] if row["reported_input_tokens"] else None
    row["reporting_coverage"] = row["reported_responses"] / row["responses"] if row["responses"] else 0


def _row(key):
    names = ("provider", "endpoint_sha256", "model", "call_purpose", "scene_transaction_id", "request_series_id")
    return {**dict(zip(names, key)), "responses": 0, "reported_responses": 0,
            "unreported_responses": 0, "inconsistent_responses": 0, "total_input_tokens": 0,
            "reported_input_tokens": 0, "cache_read_tokens": 0, "output_tokens": 0,
            "catalog_estimate_usd": 0.0}
