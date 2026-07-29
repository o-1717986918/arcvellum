"""Mutable event aggregation behind the read-only throughput projection."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .throughput_facts import (
    context_from_event,
    empty_context,
    empty_usage,
    merge_usage,
    rounded_usage,
    usage_event_delta,
)


STAGE_NAMES = (
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
_EVENT_HANDLERS = {
    "worker.runner.started": "_runner_started",
    "worker.runner.completed": "_runner_completed",
    "worker.repair.started": "_repair_started",
    "worker.repair.output_guard.finalized": "_repair_guard_finalized",
    "task.recovery_started": "_retry_started",
    "worker.run.resume_started": "_retry_started",
    "worker.usage.updated": "_usage_updated",
    "worker.sandbox.context_ready": "_context_ready",
    "worker.context.access.summary": "_context_access",
    "worker.validation.started": "_validation_started",
    "worker.validation.passed": "_validation_finished",
    "worker.validation.failed": "_validation_finished",
    "worker.validation.blocked": "_validation_blocked",
    "worker.writeback.preview_ready": "_preview_ready",
    "worker.writeback.approved": "_writeback_finished",
    "worker.writeback.rejected": "_writeback_finished",
    "bundle.started": "_bundle_started",
    "worker.bundle.started": "_bundle_started",
}


class ThroughputAccumulator:
    """Consume normalized runtime events without retaining prompts or payload text."""

    def __init__(self) -> None:
        self.task_order: list[str] = []
        self.tasks: dict[str, dict[str, Any]] = {}
        self.stage_samples: dict[str, list[float]] = {
            name: [] for name in STAGE_NAMES
        }
        self.pending_selection: datetime | None = None
        self.active_task_id = ""
        self.bundles_seen: set[str] = set()
        self.usage_snapshots: dict[tuple[str, str], dict[str, float]] = {}
        self.totals = {"model_turns": 0, "repairs": 0, "retries": 0}
        self.repair_context = _empty_repair_context()
        self.context_access = _empty_context_access()
        self.usage = empty_usage()

    def consume(self, item: dict[str, Any]) -> None:
        event = str(item.get("event") or "")
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        stamp = parse_datetime(item.get("at"))
        if event == "worker.task.selecting":
            self.pending_selection = stamp
            return
        if event == "worker.task.opened":
            self._task_opened(data, stamp)
            return
        task_id = str(data.get("task_id") or self.active_task_id)
        task = self._ensure_task(task_id, data) if task_id else None
        handler_name = _EVENT_HANDLERS.get(event)
        if handler_name:
            getattr(self, handler_name)(event, data, stamp, task, item)

    def public_tasks(self) -> list[dict[str, Any]]:
        return [_public_task(self.tasks[task_id]) for task_id in self.task_order]

    def _task_opened(
        self,
        data: dict[str, Any],
        stamp: datetime | None,
    ) -> None:
        task_id = str(data.get("task_id") or "")
        if not task_id:
            return
        self.active_task_id = task_id
        task = self._ensure_task(task_id, data)
        if task["_open_count"]:
            self.totals["retries"] += 1
            task["retries"] += 1
        task["_open_count"] += 1
        task["scene_id"] = str(data.get("scene_id") or task["scene_id"])
        task["role"] = str(data.get("agent_role") or task["role"])
        task["_opened_at"] = stamp
        record_duration(
            task,
            self.stage_samples,
            "task_selection",
            self.pending_selection,
            stamp,
        )
        self.pending_selection = None

    def _ensure_task(
        self,
        task_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        if task_id not in self.tasks:
            self.tasks[task_id] = _new_task(task_id)
            self.task_order.append(task_id)
        task = self.tasks[task_id]
        route = str(data.get("route") or "")
        if route:
            task["route"] = route
        return task

    def _runner_started(self, _event, _data, stamp, task, _item) -> None:
        self.totals["model_turns"] += 1
        if task is None:
            return
        task["model_turns"] += 1
        task["_model_started_at"] = stamp
        record_duration(
            task,
            self.stage_samples,
            "preparation",
            task.get("_opened_at"),
            stamp,
        )

    def _runner_completed(self, _event, _data, stamp, task, _item) -> None:
        if task is not None:
            record_duration(
                task,
                self.stage_samples,
                "model_execution",
                task.get("_model_started_at"),
                stamp,
            )

    def _repair_started(self, _event, data, _stamp, task, _item) -> None:
        self.totals["repairs"] += 1
        self.totals["model_turns"] += 1
        _merge_repair_context(self.repair_context, data)
        if task is not None:
            task["repairs"] += 1
            task["model_turns"] += 1
            _merge_repair_context(task["repair_context"], data)
            task["repair_context_digest"] = str(
                data.get("repair_context_digest")
                or task["repair_context_digest"]
            )

    def _repair_guard_finalized(
        self,
        _event,
        data,
        _stamp,
        task,
        _item,
    ) -> None:
        restored = _safe_int(data.get("restored_output_count"))
        self.repair_context["restored_outputs"] += restored
        if task is not None:
            task["repair_context"]["restored_outputs"] += restored

    def _retry_started(self, event, _data, _stamp, task, _item) -> None:
        if event not in _RETRY_EVENTS:
            return
        self.totals["retries"] += 1
        if task is not None:
            task["retries"] += 1

    def _usage_updated(self, _event, data, _stamp, task, _item) -> None:
        task_id = task["task_id"] if task is not None else ""
        delta = usage_event_delta(data, task_id, self.usage_snapshots)
        merge_usage(self.usage, delta)
        if task is None:
            return
        merge_usage(task["usage"], delta)
        task["provider"] = str(data.get("provider") or task["provider"])
        task["model"] = str(data.get("model") or task["model"])
        task["runtime_role"] = str(data.get("role") or task["runtime_role"])
        task["context_digest"] = str(
            data.get("context_ledger_digest") or task["context_digest"]
        )

    def _context_ready(self, _event, data, _stamp, task, _item) -> None:
        if task is None:
            return
        report = data.get("context_budget")
        if isinstance(report, dict):
            task["context"] = context_from_event(report)
        task["context_digest"] = str(
            data.get("context_ledger_digest") or task["context_digest"]
        )

    def _context_access(self, _event, data, _stamp, task, _item) -> None:
        safe = _context_access_from_event(data)
        _merge_context_access(self.context_access, safe)
        if task is not None:
            _merge_context_access(task["context_access"], safe)

    def _validation_started(self, _event, _data, stamp, task, _item) -> None:
        if task is not None:
            task["_validation_started_at"] = stamp

    def _validation_finished(self, event, data, stamp, task, _item) -> None:
        if task is None:
            return
        kind = str(data.get("kind") or "")
        if kind == "sandbox-preflight" and task["first_validation_passed"] is None:
            task["first_validation_passed"] = event == "worker.validation.passed"
        if kind == "exact-task-gate":
            record_duration(
                task,
                self.stage_samples,
                "validation_writeback",
                task.get("_validation_started_at"),
                stamp,
            )

    def _validation_blocked(self, _event, data, stamp, task, _item) -> None:
        if task is not None and str(data.get("kind") or "") == "core-task-gate":
            record_duration(
                task,
                self.stage_samples,
                "validation_writeback",
                task.get("_validation_started_at"),
                stamp,
            )

    def _preview_ready(self, _event, data, stamp, task, _item) -> None:
        if task is not None and str(data.get("policy") or "") in {
            "preview-required",
            "approval-required",
        }:
            task["_human_wait_started_at"] = stamp

    def _writeback_finished(self, _event, _data, stamp, task, _item) -> None:
        if task is not None:
            record_duration(
                task,
                self.stage_samples,
                "human_wait",
                task.get("_human_wait_started_at"),
                stamp,
            )

    def _bundle_started(self, _event, data, _stamp, _task, item) -> None:
        bundle_id = str(data.get("bundle_id") or "")
        self.bundles_seen.add(bundle_id or f"event:{item.get('sequence')}")


def ordered_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = [
        (index, item)
        for index, item in enumerate(events)
        if isinstance(item, dict)
    ]

    def order_key(pair: tuple[int, dict[str, Any]]) -> tuple[int, int]:
        index, item = pair
        try:
            sequence = int(item.get("sequence"))
        except (TypeError, ValueError):
            sequence = 10**12 + index
        return sequence, index

    return [item for _, item in sorted(indexed, key=order_key)]


def record_duration(
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
    task["_stage_seconds"][stage] = round(
        task["_stage_seconds"][stage] + duration,
        3,
    )


def parse_datetime(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _new_task(task_id: str) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "route": "",
        "scene_id": "",
        "role": "",
        "runtime_role": "",
        "provider": "",
        "model": "",
        "context_digest": "",
        "repair_context_digest": "",
        "model_turns": 0,
        "repairs": 0,
        "retries": 0,
        "first_validation_passed": None,
        "usage": empty_usage(),
        "context": empty_context(),
        "context_access": _empty_context_access(),
        "repair_context": _empty_repair_context(),
        "_stage_seconds": {name: 0.0 for name in STAGE_NAMES},
        "_open_count": 0,
    }


def _public_task(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task["task_id"],
        "route": task["route"],
        "scene_id": task["scene_id"],
        "role": task["role"],
        "runtime_role": task["runtime_role"],
        "provider": task["provider"],
        "model": task["model"],
        "model_identity": _model_identity(task["provider"], task["model"]),
        "context_digest": task["context_digest"],
        "repair_context_digest": task["repair_context_digest"],
        "model_turns": task["model_turns"],
        "repairs": task["repairs"],
        "retries": task["retries"],
        "first_validation_passed": task["first_validation_passed"],
        "usage": rounded_usage(task["usage"]),
        "context": dict(task["context"]),
        "context_access": dict(task["context_access"]),
        "repair_context": dict(task["repair_context"]),
        "stage_seconds": {
            name: round(float(task["_stage_seconds"][name]), 3)
            for name in STAGE_NAMES
        },
    }


def _model_identity(provider: object, model: object) -> str:
    provider_id = str(provider or "").strip()
    model_id = str(model or "").strip()
    if provider_id and model_id:
        return f"{provider_id}/{model_id}"
    return model_id or provider_id


def _empty_repair_context() -> dict[str, int]:
    return {
        "prompt_characters": 0,
        "excerpt_characters": 0,
        "targeted_turns": 0,
        "fallback_turns": 0,
        "protected_outputs": 0,
        "restored_outputs": 0,
    }


def _empty_context_access() -> dict[str, int]:
    return {
        "read_tool_calls": 0,
        "unique_read_targets": 0,
        "exact_on_demand_read_calls": 0,
        "exact_on_demand_unique_files": 0,
        "exact_on_demand_read_characters": 0,
        "must_inline_reread_calls": 0,
        "expected_output_read_calls": 0,
        "infrastructure_read_calls": 0,
        "other_authorized_read_calls": 0,
        "unmapped_read_calls": 0,
        "redundant_read_calls": 0,
    }


def _context_access_from_event(data: dict[str, Any]) -> dict[str, int]:
    return {
        key: _safe_int(data.get(key))
        for key in _empty_context_access()
    }


def _merge_context_access(
    target: dict[str, int],
    value: dict[str, int],
) -> None:
    for key in target:
        target[key] += value[key]


def _merge_repair_context(
    target: dict[str, int],
    data: dict[str, Any],
) -> None:
    target["prompt_characters"] += _safe_int(
        data.get("repair_prompt_characters")
    )
    target["excerpt_characters"] += _safe_int(
        data.get("repair_excerpt_characters")
    )
    target["protected_outputs"] += _safe_int(
        data.get("repair_protected_count")
    )
    mode = str(data.get("repair_write_scope_mode") or "")
    if mode == "targeted":
        target["targeted_turns"] += 1
    elif mode == "all_declared_outputs_fallback":
        target["fallback_turns"] += 1


def _safe_int(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0
