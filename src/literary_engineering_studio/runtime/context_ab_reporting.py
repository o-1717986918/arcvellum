"""Safe metric projection and verdicts for one context A/B run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .worker_results import WorkerRunResult


CONTEXT_AB_SCHEMA = "arcvellum/context-ab-report/v1"


def build_arm_report(
    mode: str,
    result: WorkerRunResult,
    elapsed: float,
    projection: dict[str, Any],
    task,
    run_manifest: Mapping[str, Any],
) -> dict[str, object]:
    context = _mapping(run_manifest.get("context_budget"))
    execution = _mapping(run_manifest.get("execution_context"))
    task_metrics = (
        projection["tasks"][-1] if projection.get("tasks") else {}
    )
    return {
        "mode": mode,
        "status": result.status,
        "runtime": result.runtime,
        "elapsed_seconds": round(elapsed, 3),
        "model_identity": str(task_metrics.get("model_identity") or ""),
        "model_turns": int(projection.get("model_turns") or 0),
        "repairs": int(projection.get("repairs") or 0),
        "retries": int(projection.get("retries") or 0),
        "first_validation": projection.get("first_validation") or {},
        "usage": projection.get("usage") or {},
        "context": _context_report(
            context,
            execution,
            task,
            result.workspace,
        ),
        "review": _review_summary(task),
    }


def build_experiment_report(
    task_id: str,
    route: str,
    runtime_id: str,
    original_digest: str,
    final_digest: str,
    arms: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    shadow = arms["shadow"]
    bounded = arms["bounded"]
    reduction = _context_reduction(shadow, bounded)
    criteria = _criteria(
        arms,
        shadow,
        bounded,
        reduction,
        original_digest == final_digest,
    )
    return {
        "schema": CONTEXT_AB_SCHEMA,
        "task_id": task_id,
        "route": route,
        "runtime": runtime_id,
        "arms": dict(arms),
        "comparison": _comparison(shadow, bounded, reduction),
        "criteria": criteria,
        "canary_candidate": all(criteria.values()),
        "original_project_digest_before": original_digest,
        "original_project_digest_after": final_digest,
    }


def _context_report(
    context: Mapping[str, Any],
    execution: Mapping[str, Any],
    task,
    workspace: Path | None,
) -> dict[str, object]:
    tiers = _mapping(execution.get("tier_counts"))
    mandatory = {
        str(item)
        for item in task.payload.get("context_must_inline_paths") or []
    }
    actual = set(_task_context_paths(workspace, "must_inline"))
    return {
        "requested_mode": str(context.get("requested_mode") or ""),
        "effective_mode": str(context.get("mode") or ""),
        "contract_status": str(context.get("contract_status") or ""),
        "rollout_reason": str(context.get("rollout_reason") or ""),
        "rollout_policy_digest": str(
            context.get("rollout_policy_digest") or ""
        ),
        "first_turn_visible_characters": _integer(
            context,
            "first_turn_visible_characters",
        ),
        "exact_on_demand_characters": _integer(
            context,
            "exact_on_demand_characters",
        ),
        "mandatory_characters": _integer(
            context,
            "mandatory_characters",
        ),
        "must_inline_count": _integer(tiers, "must_inline"),
        "exact_on_demand_count": _integer(
            tiers,
            "exact_on_demand",
        ),
        "mandatory_missing_count": len(mandatory - actual),
        "tier_overlap_count": _tier_overlap(workspace),
        "execution_context_digest": str(execution.get("digest") or ""),
    }


def _review_summary(task) -> dict[str, object]:
    candidates = [
        path
        for path in task.expected_outputs
        if path.endswith("_scene_review.json")
    ]
    if len(candidates) != 1:
        return _empty_review()
    path = task.project_root / Path(candidates[0])
    if not path.is_file():
        return _empty_review()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "present": True,
        "schema": str(payload.get("schema") or ""),
        "conclusion": str(payload.get("conclusion") or ""),
        "blocking_issue_count": len(
            payload.get("blocking_issues") or []
        ),
        "warning_count": len(payload.get("warnings") or []),
    }


def _criteria(
    arms: Mapping[str, Mapping[str, object]],
    shadow: Mapping[str, object],
    bounded: Mapping[str, object],
    reduction: float,
    original_unchanged: bool,
) -> dict[str, bool]:
    same_model = bool(
        shadow.get("model_identity")
        and shadow.get("model_identity") == bounded.get("model_identity")
    )
    modes_applied = (
        _context_string(shadow, "effective_mode") == "shadow"
        and _context_string(bounded, "effective_mode") == "bounded"
    )
    review_schemas = {
        _review_string(arm, "schema") for arm in arms.values()
    }
    repair_retry_not_increased = (
        _repair_retry_turns(bounded) <= _repair_retry_turns(shadow)
    )
    return {
        "same_model": same_model,
        "requested_modes_applied": modes_applied,
        "both_complete": all(
            arm.get("status") == "complete"
            for arm in arms.values()
        ),
        "both_first_preflight_pass": all(
            _first_preflight_pass(arm) for arm in arms.values()
        ),
        "both_reviews_non_fail": all(
            _review_non_fail(arm) for arm in arms.values()
        ),
        "review_schema_present_and_equal": (
            len(review_schemas) == 1 and "" not in review_schemas
        ),
        "bounded_did_not_add_repair_or_retry_turns": (
            repair_retry_not_increased
        ),
        "bounded_context_reduction_at_least_50_percent": (
            reduction >= 0.5
        ),
        "bounded_mandatory_complete": (
            _context_value(bounded, "mandatory_missing_count") == 0
        ),
        "bounded_tiers_disjoint": (
            _context_value(bounded, "tier_overlap_count") == 0
        ),
        "original_project_unchanged": original_unchanged,
    }


def _comparison(
    shadow: Mapping[str, object],
    bounded: Mapping[str, object],
    reduction: float,
) -> dict[str, object]:
    return {
        "first_turn_visible_character_reduction": round(
            reduction,
            6,
        ),
        "non_cached_input_token_reduction": _usage_reduction(
            shadow,
            bounded,
            "non_cached_input_tokens",
        ),
        "repair_retry_turn_delta": (
            int(bounded.get("repairs") or 0)
            + int(bounded.get("retries") or 0)
            - int(shadow.get("repairs") or 0)
            - int(shadow.get("retries") or 0)
        ),
        "elapsed_seconds_delta": round(
            float(bounded.get("elapsed_seconds") or 0)
            - float(shadow.get("elapsed_seconds") or 0),
            3,
        ),
    }


def _task_context_paths(
    workspace: Path | None,
    field: str,
) -> tuple[str, ...]:
    if workspace is None:
        return ()
    path = workspace / "TASK_CONTEXT.json"
    if not path.is_file():
        return ()
    payload = json.loads(path.read_text(encoding="utf-8"))
    values = _mapping(payload.get("execution_context")).get(field)
    if not isinstance(values, list):
        return ()
    return tuple(str(item) for item in values)


def _tier_overlap(workspace: Path | None) -> int:
    memberships: dict[str, int] = {}
    for field in ("must_inline", "exact_on_demand", "excluded"):
        for path in set(_task_context_paths(workspace, field)):
            memberships[path] = memberships.get(path, 0) + 1
    return sum(1 for count in memberships.values() if count > 1)


def _context_reduction(
    shadow: Mapping[str, object],
    bounded: Mapping[str, object],
) -> float:
    shadow_chars = _context_value(
        shadow,
        "first_turn_visible_characters",
    )
    bounded_chars = _context_value(
        bounded,
        "first_turn_visible_characters",
    )
    if not shadow_chars:
        return 0.0
    return (shadow_chars - bounded_chars) / shadow_chars


def _context_value(
    arm: Mapping[str, object],
    field: str,
) -> int:
    return _integer(_mapping(arm.get("context")), field)


def _context_string(
    arm: Mapping[str, object],
    field: str,
) -> str:
    return str(_mapping(arm.get("context")).get(field) or "")


def _review_string(
    arm: Mapping[str, object],
    field: str,
) -> str:
    return str(_mapping(arm.get("review")).get(field) or "")


def _repair_retry_turns(arm: Mapping[str, object]) -> int:
    return int(arm.get("repairs") or 0) + int(
        arm.get("retries") or 0
    )


def _usage_reduction(
    shadow: Mapping[str, object],
    bounded: Mapping[str, object],
    field: str,
) -> float | None:
    shadow_value = float(_mapping(shadow.get("usage")).get(field) or 0)
    bounded_value = float(_mapping(bounded.get("usage")).get(field) or 0)
    if shadow_value <= 0:
        return None
    return round((shadow_value - bounded_value) / shadow_value, 6)


def _first_preflight_pass(arm: Mapping[str, object]) -> bool:
    first = _mapping(arm.get("first_validation"))
    return int(first.get("passed_first_attempt") or 0) >= 1


def _review_non_fail(arm: Mapping[str, object]) -> bool:
    review = _mapping(arm.get("review"))
    return (
        review.get("present") is True
        and str(review.get("conclusion") or "") in {
            "pass",
            "pass_with_notes",
        }
    )


def _empty_review() -> dict[str, object]:
    return {
        "present": False,
        "schema": "",
        "conclusion": "",
        "blocking_issue_count": 0,
        "warning_count": 0,
    }


def _integer(value: Mapping[str, Any], field: str) -> int:
    return int(value.get(field) or 0)


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


__all__ = [
    "CONTEXT_AB_SCHEMA",
    "build_arm_report",
    "build_experiment_report",
]
