"""Measure-only throughput projection derived from the runtime event ledger.

This module is deliberately read-only. It neither changes execution policy nor
persists a second source of truth. Only fixed metric fields are projected; event
payload text, prompts, paths, credentials, and model reasoning are discarded.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .throughput_aggregation import (
    STAGE_NAMES,
    ThroughputAccumulator,
    ordered_events,
)
from .throughput_facts import (
    attribution,
    context_summary,
    rounded_usage,
    stage_summary,
)


SCHEMA = "arcvellum/throughput-projection/v1"
MAX_VISIBLE_TASKS = 100


def build_throughput_projection(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate public throughput facts from persisted runtime events."""
    ordered = ordered_events(events)
    accumulator = ThroughputAccumulator()
    for item in ordered:
        accumulator.consume(item)

    public_tasks = accumulator.public_tasks()
    first_results = [
        item["first_validation_passed"]
        for item in public_tasks
        if item["first_validation_passed"] is not None
    ]
    passed_first = sum(1 for result in first_results if result)
    evaluated = len(first_results)
    context = context_summary(public_tasks)
    projection = {
        "schema": SCHEMA,
        "mode": "measure-only",
        "event_count": len(ordered),
        "task_count": len(accumulator.task_order),
        "bundle_count": len(accumulator.bundles_seen),
        "model_turns": accumulator.totals["model_turns"],
        "repairs": accumulator.totals["repairs"],
        "retries": accumulator.totals["retries"],
        "first_validation": {
            "evaluated_tasks": evaluated,
            "passed_first_attempt": passed_first,
            "failed_first_attempt": evaluated - passed_first,
            "pass_rate": round(passed_first / evaluated, 4) if evaluated else None,
        },
        "usage": rounded_usage(accumulator.usage),
        "context": context,
        "attribution": {
            "by_scene": attribution(public_tasks, "scene_id"),
            "by_role": attribution(public_tasks, "role"),
            "by_runtime_role": attribution(public_tasks, "runtime_role"),
            "by_model": attribution(public_tasks, "model_identity"),
            "by_context_digest": attribution(public_tasks, "context_digest"),
        },
        "stages": {
            name: stage_summary(accumulator.stage_samples[name])
            for name in STAGE_NAMES
        },
        "coverage": {
            "event_ledger": True,
            "bundle_events": bool(accumulator.bundles_seen),
            "cache_tokens": bool(
                accumulator.usage["cache_read_tokens"]
                or accumulator.usage["cache_write_tokens"]
            ),
            "scene_attribution": any(item["scene_id"] for item in public_tasks),
            "context_budget": context["reported_tasks"] > 0,
            "provider_model_attribution": any(
                item["model"] for item in public_tasks
            ),
        },
        "tasks": public_tasks[-MAX_VISIBLE_TASKS:],
        "tasks_truncated": len(public_tasks) > MAX_VISIBLE_TASKS,
    }
    projection["revision"] = _digest(projection)
    return projection


def _digest(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]
