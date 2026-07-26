"""Measure-only throughput projection derived from the runtime event ledger.

This module is deliberately read-only. It neither changes execution policy nor
persists a second source of truth. Only fixed metric fields are projected; event
payload text, prompts, paths, credentials, and model reasoning are discarded.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any


SCHEMA = "arcvellum/throughput-projection/v1"
MAX_VISIBLE_TASKS = 100
_STAGE_NAMES = (
    "task_selection",
    "preparation",
    "model_execution",
    "validation_writeback",
    "human_wait",
)
_RETRY_EVENTS = {
    "task.recovery_started",
    "worker.run.resume_started",
}


def build_throughput_projection(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate public throughput facts from persisted runtime events."""
    ordered = _ordered_events(events)
    task_order: list[str] = []
    tasks: dict[str, dict[str, Any]] = {}
    stage_samples: dict[str, list[float]] = {name: [] for name in _STAGE_NAMES}
    pending_selection: datetime | None = None
    active_task_id = ""
    bundles_seen: set[str] = set()
    usage_snapshots: dict[tuple[str, str], dict[str, float]] = {}
    totals = {
        "model_turns": 0,
        "repairs": 0,
        "retries": 0,
    }
    usage = _empty_usage()

    for item in ordered:
        event = str(item.get("event") or "")
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        stamp = _parse_datetime(item.get("at"))
        task_id = str(data.get("task_id") or active_task_id)

        if event == "worker.task.selecting":
            pending_selection = stamp
            continue

        if event == "worker.task.opened":
            task_id = str(data.get("task_id") or "")
            if not task_id:
                continue
            active_task_id = task_id
            task = _task(tasks, task_order, task_id)
            if task["_open_count"]:
                totals["retries"] += 1
                task["retries"] += 1
            task["_open_count"] += 1
            task["route"] = str(data.get("route") or task["route"])
            task["_opened_at"] = stamp
            _record_duration(task, stage_samples, "task_selection", pending_selection, stamp)
            pending_selection = None
            continue

        if task_id:
            task = _task(tasks, task_order, task_id)
            route = str(data.get("route") or "")
            if route:
                task["route"] = route
        else:
            task = None

        if event == "worker.runner.started":
            totals["model_turns"] += 1
            if task is not None:
                task["model_turns"] += 1
                task["_model_started_at"] = stamp
                _record_duration(
                    task,
                    stage_samples,
                    "preparation",
                    task.get("_opened_at"),
                    stamp,
                )
        elif event == "worker.runner.completed":
            if task is not None:
                _record_duration(
                    task,
                    stage_samples,
                    "model_execution",
                    task.get("_model_started_at"),
                    stamp,
                )
        elif event == "worker.repair.started":
            totals["repairs"] += 1
            totals["model_turns"] += 1
            if task is not None:
                task["repairs"] += 1
                task["model_turns"] += 1
        elif event in _RETRY_EVENTS:
            totals["retries"] += 1
            if task is not None:
                task["retries"] += 1
        elif event == "worker.usage.updated":
            delta = _usage_event_delta(data, task_id, usage_snapshots)
            _merge_usage(usage, delta)
            if task is not None:
                _merge_usage(task["usage"], delta)
        elif event == "worker.validation.started":
            if task is not None:
                task["_validation_started_at"] = stamp
        elif event in {"worker.validation.passed", "worker.validation.failed"}:
            kind = str(data.get("kind") or "")
            if task is not None and kind == "sandbox-preflight" and task["first_validation_passed"] is None:
                task["first_validation_passed"] = event == "worker.validation.passed"
            if task is not None and kind == "exact-task-gate":
                _record_duration(
                    task,
                    stage_samples,
                    "validation_writeback",
                    task.get("_validation_started_at"),
                    stamp,
                )
        elif event == "worker.validation.blocked":
            if task is not None and str(data.get("kind") or "") == "core-task-gate":
                _record_duration(
                    task,
                    stage_samples,
                    "validation_writeback",
                    task.get("_validation_started_at"),
                    stamp,
                )
        elif event == "worker.writeback.preview_ready":
            if task is not None and str(data.get("policy") or "") in {"preview-required", "approval-required"}:
                task["_human_wait_started_at"] = stamp
        elif event in {"worker.writeback.approved", "worker.writeback.rejected"}:
            if task is not None:
                _record_duration(
                    task,
                    stage_samples,
                    "human_wait",
                    task.get("_human_wait_started_at"),
                    stamp,
                )

        if event in {"bundle.started", "worker.bundle.started"}:
            bundle_id = str(data.get("bundle_id") or "")
            bundles_seen.add(bundle_id or f"event:{item.get('sequence')}")

    public_tasks = [_public_task(tasks[task_id]) for task_id in task_order]
    first_results = [
        item["first_validation_passed"]
        for item in public_tasks
        if item["first_validation_passed"] is not None
    ]
    passed_first = sum(1 for result in first_results if result)
    evaluated = len(first_results)
    projection = {
        "schema": SCHEMA,
        "mode": "measure-only",
        "event_count": len(ordered),
        "task_count": len(task_order),
        "bundle_count": len(bundles_seen),
        "model_turns": totals["model_turns"],
        "repairs": totals["repairs"],
        "retries": totals["retries"],
        "first_validation": {
            "evaluated_tasks": evaluated,
            "passed_first_attempt": passed_first,
            "failed_first_attempt": evaluated - passed_first,
            "pass_rate": round(passed_first / evaluated, 4) if evaluated else None,
        },
        "usage": _rounded_usage(usage),
        "stages": {
            name: _stage_summary(stage_samples[name])
            for name in _STAGE_NAMES
        },
        "coverage": {
            "event_ledger": True,
            "bundle_events": bool(bundles_seen),
            "cache_tokens": bool(usage["cache_read_tokens"] or usage["cache_write_tokens"]),
            "scene_attribution": False,
        },
        "tasks": public_tasks[-MAX_VISIBLE_TASKS:],
        "tasks_truncated": len(public_tasks) > MAX_VISIBLE_TASKS,
    }
    return _with_revision(projection)


def _with_revision(projection: dict[str, Any]) -> dict[str, Any]:
    projection["revision"] = _digest(projection)
    return projection


def _usage_event_delta(
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


def _ordered_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = [(index, item) for index, item in enumerate(events) if isinstance(item, dict)]

    def order_key(pair: tuple[int, dict[str, Any]]) -> tuple[int, int]:
        index, item = pair
        try:
            sequence = int(item.get("sequence"))
        except (TypeError, ValueError):
            sequence = 10**12 + index
        return sequence, index

    return [item for _, item in sorted(indexed, key=order_key)]


def _task(
    tasks: dict[str, dict[str, Any]],
    task_order: list[str],
    task_id: str,
) -> dict[str, Any]:
    if task_id not in tasks:
        tasks[task_id] = {
            "task_id": task_id,
            "route": "",
            "model_turns": 0,
            "repairs": 0,
            "retries": 0,
            "first_validation_passed": None,
            "usage": _empty_usage(),
            "_stage_seconds": {name: 0.0 for name in _STAGE_NAMES},
            "_open_count": 0,
        }
        task_order.append(task_id)
    return tasks[task_id]


def _record_duration(
    task: dict[str, Any],
    stage_samples: dict[str, list[float]],
    stage: str,
    started: object,
    finished: object,
) -> None:
    if not isinstance(started, datetime) or not isinstance(finished, datetime):
        return
    duration = (finished - started).total_seconds()
    if duration < 0:
        return
    duration = round(duration, 3)
    stage_samples[stage].append(duration)
    task["_stage_seconds"][stage] = round(task["_stage_seconds"][stage] + duration, 3)


def _public_task(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task["task_id"],
        "route": task["route"],
        "model_turns": task["model_turns"],
        "repairs": task["repairs"],
        "retries": task["retries"],
        "first_validation_passed": task["first_validation_passed"],
        "usage": _rounded_usage(task["usage"]),
        "stage_seconds": {
            name: round(float(task["_stage_seconds"][name]), 3)
            for name in _STAGE_NAMES
        },
    }


def _stage_summary(samples: list[float]) -> dict[str, int | float]:
    total = round(sum(samples), 3)
    return {
        "sample_count": len(samples),
        "total_seconds": total,
        "average_seconds": round(total / len(samples), 3) if samples else 0.0,
        "max_seconds": round(max(samples), 3) if samples else 0.0,
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
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_write_tokens": cache_write_tokens,
        "total_tokens": supplied_total or input_tokens + output_tokens + reasoning_tokens,
        "cost_usd": _number(data.get("cost_usd")),
    }


def _empty_usage() -> dict[str, float]:
    return {
        "input_tokens": 0.0,
        "output_tokens": 0.0,
        "reasoning_tokens": 0.0,
        "cache_read_tokens": 0.0,
        "cache_write_tokens": 0.0,
        "total_tokens": 0.0,
        "cost_usd": 0.0,
    }


def _merge_usage(target: dict[str, float], delta: dict[str, float]) -> None:
    for key in target:
        target[key] += delta[key]


def _usage_delta(
    previous: dict[str, float] | None,
    current: dict[str, float],
) -> dict[str, float]:
    if previous is None:
        return dict(current)
    return {
        key: (
            current[key] - previous[key]
            if current[key] >= previous[key]
            else current[key]
        )
        for key in current
    }


def _rounded_usage(usage: dict[str, float]) -> dict[str, int | float]:
    return {
        "input_tokens": int(usage["input_tokens"]),
        "output_tokens": int(usage["output_tokens"]),
        "reasoning_tokens": int(usage["reasoning_tokens"]),
        "cache_read_tokens": int(usage["cache_read_tokens"]),
        "cache_write_tokens": int(usage["cache_write_tokens"]),
        "total_tokens": int(usage["total_tokens"]),
        "cost_usd": round(usage["cost_usd"], 6),
    }


def _number(value: object) -> float:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, number) if math.isfinite(number) else 0.0


def _parse_datetime(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _digest(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]
