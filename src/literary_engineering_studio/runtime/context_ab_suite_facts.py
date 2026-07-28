"""Statistical and quality facts for a context A/B report suite."""

from __future__ import annotations

import math
from statistics import median
from typing import Any, Iterable, Mapping


_REVIEW_RANK = {
    "reject": 0,
    "revise_required": 1,
    "pass_with_notes": 2,
    "pass": 3,
}


def analyze_context_ab_suite(
    samples: tuple[Mapping[str, Any], ...],
    *,
    rollback_drill: Mapping[str, Any] | None,
) -> dict[str, object]:
    token_reductions = tuple(
        _optional_number(
            _mapping(item.get("comparison")).get(
                "non_cached_input_token_reduction"
            )
        )
        for item in samples
    )
    visible_reductions = tuple(
        _number(
            _mapping(item.get("comparison")).get(
                "first_turn_visible_character_reduction"
            )
        )
        for item in samples
    )
    repair = _repair_retry_evidence(samples)
    criteria = _suite_criteria(
        samples,
        token_reductions=token_reductions,
        visible_reductions=visible_reductions,
        repair=repair,
        rollback_drill=rollback_drill,
    )
    return {
        "model_identities": _model_identities(samples),
        "distributions": _suite_distributions(
            samples,
            token_reductions=token_reductions,
            visible_reductions=visible_reductions,
        ),
        "repair_retry": repair,
        "review_conclusions": _review_conclusions(samples),
        "criteria": criteria,
        "rollback_drill": _safe_rollback_projection(rollback_drill),
    }


def _suite_criteria(
    samples: tuple[Mapping[str, Any], ...],
    *,
    token_reductions: tuple[float | None, ...],
    visible_reductions: tuple[float, ...],
    repair: Mapping[str, object],
    rollback_drill: Mapping[str, Any] | None,
) -> dict[str, bool]:
    return {
        "multi_scene_sample": (
            len(samples) >= 3
            and len({str(item.get("task_id") or "") for item in samples})
            >= 3
        ),
        "uniform_route_and_runtime": _uniform_identity(samples),
        "all_sample_safety_gates_pass": all(
            _sample_safety_pass(item) for item in samples
        ),
        "review_quality_not_degraded": all(
            _review_not_degraded(item) for item in samples
        ),
        "median_non_cached_input_token_reduction_at_least_40_percent": (
            all(value is not None for value in token_reductions)
            and _median_present(token_reductions) >= 0.4
        ),
        "median_first_turn_visible_reduction_at_least_50_percent": (
            median(visible_reductions) >= 0.5
        ),
        "repair_retry_target_met": bool(repair["target_met"]),
        "rollback_drill_passed": bool(
            rollback_drill and rollback_drill.get("passed") is True
        ),
    }


def _suite_distributions(
    samples: tuple[Mapping[str, Any], ...],
    *,
    token_reductions: tuple[float | None, ...],
    visible_reductions: tuple[float, ...],
) -> dict[str, dict[str, float | int | None]]:
    return {
        "non_cached_input_token_reduction": _distribution(
            value for value in token_reductions if value is not None
        ),
        "first_turn_visible_character_reduction": _distribution(
            visible_reductions
        ),
        "shadow_non_cached_input_tokens": _arm_distribution(
            samples, "shadow", "usage", "non_cached_input_tokens"
        ),
        "bounded_non_cached_input_tokens": _arm_distribution(
            samples, "bounded", "usage", "non_cached_input_tokens"
        ),
        "shadow_elapsed_seconds": _arm_distribution(
            samples, "shadow", "", "elapsed_seconds"
        ),
        "bounded_elapsed_seconds": _arm_distribution(
            samples, "bounded", "", "elapsed_seconds"
        ),
        "bounded_exact_on_demand_read_characters": _arm_distribution(
            samples,
            "bounded",
            "context_access",
            "exact_on_demand_read_characters",
        ),
    }


def _sample_safety_pass(report: Mapping[str, Any]) -> bool:
    criteria = _mapping(report.get("criteria"))
    required = (
        "same_model",
        "requested_modes_applied",
        "both_complete",
        "both_first_preflight_pass",
        "both_reviews_non_fail",
        "review_schema_present_and_equal",
        "bounded_did_not_add_repair_or_retry_turns",
        "bounded_mandatory_complete",
        "bounded_tiers_disjoint",
        "original_project_unchanged",
    )
    return all(criteria.get(field) is True for field in required)


def _review_not_degraded(report: Mapping[str, Any]) -> bool:
    arms = _mapping(report.get("arms"))
    shadow = _mapping(_mapping(arms.get("shadow")).get("review"))
    bounded = _mapping(_mapping(arms.get("bounded")).get("review"))
    shadow_rank = _REVIEW_RANK.get(str(shadow.get("conclusion") or ""), -1)
    bounded_rank = _REVIEW_RANK.get(str(bounded.get("conclusion") or ""), -1)
    return (
        shadow_rank >= 0
        and bounded_rank >= shadow_rank
        and _integer(bounded.get("blocking_issue_count"))
        <= _integer(shadow.get("blocking_issue_count"))
    )


def _repair_retry_evidence(
    samples: tuple[Mapping[str, Any], ...],
) -> dict[str, object]:
    pairs = tuple(
        (_arm_turns(item, "shadow"), _arm_turns(item, "bounded"))
        for item in samples
    )
    zero_baseline = all(shadow == 0 for shadow, _ in pairs)
    if zero_baseline:
        return {
            "baseline": "zero",
            "shadow_turns": 0,
            "bounded_turns": sum(item[1] for item in pairs),
            "median_reduction": None,
            "target_met": all(bounded == 0 for _, bounded in pairs),
        }
    reductions = [
        (shadow - bounded) / shadow
        for shadow, bounded in pairs
        if shadow > 0
    ]
    zero_samples_safe = all(
        bounded == 0
        for shadow, bounded in pairs
        if shadow == 0
    )
    value = float(median(reductions)) if reductions else 0.0
    return {
        "baseline": "nonzero",
        "shadow_turns": sum(item[0] for item in pairs),
        "bounded_turns": sum(item[1] for item in pairs),
        "median_reduction": round(value, 6),
        "target_met": zero_samples_safe and value >= 0.25,
    }


def _uniform_identity(samples: tuple[Mapping[str, Any], ...]) -> bool:
    routes = {str(item.get("route") or "") for item in samples}
    runtimes = {str(item.get("runtime") or "") for item in samples}
    models = set(_model_identities(samples))
    return (
        len(routes) == 1
        and "" not in routes
        and len(runtimes) == 1
        and "" not in runtimes
        and len(models) == 1
        and "" not in models
    )


def _model_identities(
    samples: tuple[Mapping[str, Any], ...],
) -> list[str]:
    return sorted(
        {
            str(
                _mapping(
                    _mapping(item.get("arms")).get("shadow")
                ).get("model_identity")
                or ""
            )
            for item in samples
        }
    )


def _review_conclusions(
    samples: tuple[Mapping[str, Any], ...],
) -> dict[str, list[str]]:
    return {
        mode: [
            str(
                _mapping(
                    _mapping(_mapping(item.get("arms")).get(mode)).get(
                        "review"
                    )
                ).get("conclusion")
                or ""
            )
            for item in samples
        ]
        for mode in ("shadow", "bounded")
    }


def _arm_distribution(
    samples: tuple[Mapping[str, Any], ...],
    mode: str,
    section: str,
    field: str,
) -> dict[str, float | int | None]:
    values: list[float] = []
    for item in samples:
        arm = _mapping(_mapping(item.get("arms")).get(mode))
        source = _mapping(arm.get(section)) if section else arm
        values.append(_number(source.get(field)))
    return _distribution(values)


def _arm_turns(report: Mapping[str, Any], mode: str) -> int:
    arm = _mapping(_mapping(report.get("arms")).get(mode))
    return _integer(arm.get("repairs")) + _integer(arm.get("retries"))


def _distribution(
    values: Iterable[float],
) -> dict[str, float | int | None]:
    ordered = sorted(float(item) for item in values)
    if not ordered:
        return {
            "count": 0,
            "minimum": None,
            "median": None,
            "p95": None,
            "maximum": None,
        }
    p95_index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return {
        "count": len(ordered),
        "minimum": round(ordered[0], 6),
        "median": round(float(median(ordered)), 6),
        "p95": round(ordered[p95_index], 6),
        "maximum": round(ordered[-1], 6),
    }


def _safe_rollback_projection(
    value: Mapping[str, Any] | None,
) -> dict[str, object]:
    if not value:
        return {"present": False, "passed": False}
    return {
        "present": True,
        "schema": str(value.get("schema") or ""),
        "task_count": _integer(value.get("task_count")),
        "criteria": dict(_mapping(value.get("criteria"))),
        "passed": value.get("passed") is True,
    }


def _median_present(values: Iterable[float | None]) -> float:
    present = [float(item) for item in values if item is not None]
    return float(median(present)) if present else float("-inf")


def _optional_number(value: object) -> float | None:
    if value is None:
        return None
    return _number(value)


def _number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _integer(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


__all__ = ["analyze_context_ab_suite"]
