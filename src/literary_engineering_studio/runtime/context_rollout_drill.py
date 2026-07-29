"""Deterministic bounded-canary to shadow rollback rehearsal."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping

from ..contracts import TaskPackage
from .context_rollout import resolve_context_rollout


CONTEXT_ROLLBACK_DRILL_SCHEMA = "arcvellum/context-rollout-rollback-drill/v1"


def run_context_rollout_rollback_drill(
    tasks: Iterable[TaskPackage],
    *,
    canary_config: Mapping[str, Any],
    rollback_config: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    packages = tuple(tasks)
    if not packages:
        raise ValueError("context rollout rollback drill requires tasks")
    before = {task.task_id: _task_digest(task) for task in packages}
    canary = tuple(
        _decision(task, canary_config) for task in packages
    )
    rollback_policy = rollback_config or {
        "mode": "shadow",
        "bounded_rollout": {"enabled": False},
    }
    rolled_back = tuple(
        _decision(task, rollback_policy) for task in packages
    )
    after = {task.task_id: _task_digest(task) for task in packages}
    criteria = {
        "canary_exercised": any(
            item["effective_mode"] == "bounded"
            for item in canary
        ),
        "canary_only_activates_ready_contracts": all(
            (
                item["contract_status"] == "bounded-ready"
                and item["rollout_matched"] is True
            )
            if item["effective_mode"] == "bounded"
            else item["effective_mode"] == "shadow"
            for item in canary
        ),
        "rollback_restores_shadow_for_all_tasks": all(
            item["effective_mode"] == "shadow"
            for item in rolled_back
        ),
        "policy_identity_changed": any(
            left["policy_digest"] != right["policy_digest"]
            for left, right in zip(canary, rolled_back)
        ),
        "task_contracts_unchanged": before == after,
    }
    return {
        "schema": CONTEXT_ROLLBACK_DRILL_SCHEMA,
        "task_count": len(packages),
        "task_ids": [task.task_id for task in packages],
        "canary": list(canary),
        "rollback": list(rolled_back),
        "criteria": criteria,
        "passed": all(criteria.values()),
    }


def _decision(
    task: TaskPackage,
    config: Mapping[str, Any],
) -> dict[str, object]:
    value = resolve_context_rollout(task, config)
    return {
        "task_id": task.task_id,
        "route": value.route,
        "current_state": value.current_state,
        "contract_status": value.contract_status,
        "effective_mode": value.effective_mode,
        "rollout_matched": value.rollout_matched,
        "reason": value.reason,
        "policy_digest": value.policy_digest,
    }


def _task_digest(task: TaskPackage) -> str:
    encoded = json.dumps(
        task.payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "CONTEXT_ROLLBACK_DRILL_SCHEMA",
    "run_context_rollout_rollback_drill",
]
