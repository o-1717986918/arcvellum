"""Token, context, and attribution facts used by throughput projections."""

from __future__ import annotations

import math
from statistics import median
from typing import Any


def context_summary(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    reported = [task["context"] for task in tasks if task["context"]["digest"]]
    visible = [item["first_turn_visible_characters"] for item in reported]
    on_demand = [item["exact_on_demand_characters"] for item in reported]
    return {
        "reported_tasks": len(reported),
        "first_turn_visible_characters": sum(visible),
        "median_first_turn_visible_characters": int(median(visible)) if visible else 0,
        "exact_on_demand_characters": sum(on_demand),
        "median_exact_on_demand_characters": int(median(on_demand)) if on_demand else 0,
        "excluded_characters": sum(item["excluded_characters"] for item in reported),
        "authorized_characters": sum(item["authorized_characters"] for item in reported),
        "budget_overage_count": sum(item["budget_overage_count"] for item in reported),
        "budget_overage_characters": sum(
            item["budget_overage_characters"] for item in reported
        ),
    }


def attribution(tasks: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for task in tasks:
        value = str(task.get(key) or "").strip()
        if not value:
            continue
        group = groups.setdefault(value, _new_attribution(value))
        group["task_count"] += 1
        group["model_turns"] += int(task["model_turns"])
        group["repairs"] += int(task["repairs"])
        group["retries"] += int(task["retries"])
        merge_usage(group["usage"], task["usage"])
    return [
        {**group, "usage": rounded_usage(group["usage"])}
        for _, group in sorted(groups.items())
    ]


def stage_summary(samples: list[float]) -> dict[str, int | float]:
    total = round(sum(samples), 3)
    return {
        "sample_count": len(samples),
        "total_seconds": total,
        "average_seconds": round(total / len(samples), 3) if samples else 0.0,
        "max_seconds": round(max(samples), 3) if samples else 0.0,
    }


def usage_event_delta(
    data: dict[str, Any],
    task_id: str,
    snapshots: dict[tuple[str, str], dict[str, float]],
) -> dict[str, float]:
    current = _usage_from_event(data)
    usage_id = str(data.get("usage_id") or "")
    if not usage_id:
        return current
    snapshot_key = (task_id, usage_id)
    delta = _usage_delta(snapshots.get(snapshot_key), current)
    snapshots[snapshot_key] = current
    return delta


def empty_usage() -> dict[str, float]:
    return {
        "input_tokens": 0.0,
        "non_cached_input_tokens": 0.0,
        "output_tokens": 0.0,
        "reasoning_tokens": 0.0,
        "cache_read_tokens": 0.0,
        "cache_write_tokens": 0.0,
        "total_tokens": 0.0,
        "cost_usd": 0.0,
    }


def merge_usage(target: dict[str, float], delta: dict[str, float]) -> None:
    for key in target:
        target[key] += delta[key]


def rounded_usage(usage: dict[str, float]) -> dict[str, int | float]:
    return {
        "input_tokens": int(usage["input_tokens"]),
        "non_cached_input_tokens": int(usage["non_cached_input_tokens"]),
        "output_tokens": int(usage["output_tokens"]),
        "reasoning_tokens": int(usage["reasoning_tokens"]),
        "cache_read_tokens": int(usage["cache_read_tokens"]),
        "cache_write_tokens": int(usage["cache_write_tokens"]),
        "total_tokens": int(usage["total_tokens"]),
        "cost_usd": round(usage["cost_usd"], 6),
    }


def context_from_event(report: dict[str, Any]) -> dict[str, Any]:
    context = empty_context()
    string_fields = {
        "mode",
        "requested_mode",
        "task_kind",
        "risk_level",
        "contract_status",
        "rollout_reason",
        "rollout_policy_digest",
        "digest",
    }
    for key in string_fields:
        context[key] = str(report.get(key) or "")
    for key in context:
        if key not in string_fields:
            context[key] = int(_number(report.get(key)))
    return context


def empty_context() -> dict[str, Any]:
    return {
        "mode": "",
        "requested_mode": "",
        "task_kind": "",
        "risk_level": "",
        "contract_status": "",
        "rollout_reason": "",
        "rollout_policy_digest": "",
        "target_inline_characters": 0,
        "enforced_inline_characters": 0,
        "first_turn_visible_characters": 0,
        "exact_on_demand_characters": 0,
        "excluded_characters": 0,
        "authorized_characters": 0,
        "mandatory_characters": 0,
        "included_file_count": 0,
        "on_demand_file_count": 0,
        "excluded_file_count": 0,
        "budget_overage_count": 0,
        "budget_overage_characters": 0,
        "digest": "",
    }


def _usage_from_event(data: dict[str, Any]) -> dict[str, float]:
    raw = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    cache = raw.get("cache") if isinstance(raw.get("cache"), dict) else {}
    input_tokens = _number(raw.get("input") or raw.get("input_tokens"))
    output_tokens = _number(raw.get("output") or raw.get("output_tokens"))
    reasoning_tokens = _number(raw.get("reasoning") or raw.get("reasoning_tokens"))
    cache_read_tokens = _number(
        cache.get("read")
        or cache.get("read_tokens")
        or raw.get("cache_read")
        or raw.get("cache_read_tokens")
    )
    cache_write_tokens = _number(
        cache.get("write")
        or cache.get("write_tokens")
        or raw.get("cache_write")
        or raw.get("cache_write_tokens")
    )
    supplied_total = _number(raw.get("total") or raw.get("total_tokens"))
    return {
        "input_tokens": input_tokens,
        "non_cached_input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_write_tokens": cache_write_tokens,
        "total_tokens": supplied_total
        or input_tokens + output_tokens + reasoning_tokens,
        "cost_usd": _number(data.get("cost_usd")),
    }


def _usage_delta(
    previous: dict[str, float] | None,
    current: dict[str, float],
) -> dict[str, float]:
    if previous is None:
        return dict(current)
    return {
        key: current[key] - previous[key]
        if current[key] >= previous[key]
        else current[key]
        for key in current
    }


def _number(value: object) -> float:
    try:
        parsed = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, parsed) if math.isfinite(parsed) else 0.0


def _new_attribution(value: str) -> dict[str, Any]:
    return {
        "key": value,
        "task_count": 0,
        "model_turns": 0,
        "repairs": 0,
        "retries": 0,
        "usage": empty_usage(),
    }
