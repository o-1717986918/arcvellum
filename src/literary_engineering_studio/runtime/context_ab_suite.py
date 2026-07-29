"""Aggregate safe single-task context A/B reports into an exit verdict."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .context_ab_reporting import CONTEXT_AB_SCHEMA
from .context_ab_suite_facts import analyze_context_ab_suite


CONTEXT_AB_SUITE_SCHEMA = "arcvellum/context-ab-suite-report/v1"


def build_context_ab_suite_report(
    reports: Iterable[Mapping[str, Any]],
    *,
    rollback_drill: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    samples = tuple(_validated_report(item) for item in reports)
    if not samples:
        raise ValueError("context A/B suite requires at least one report")
    analysis = analyze_context_ab_suite(
        samples,
        rollback_drill=rollback_drill,
    )
    return {
        "schema": CONTEXT_AB_SUITE_SCHEMA,
        "sample_count": len(samples),
        "task_ids": [str(item.get("task_id") or "") for item in samples],
        "route": str(samples[0].get("route") or ""),
        "runtime": str(samples[0].get("runtime") or ""),
        "model_identities": analysis["model_identities"],
        "distributions": analysis["distributions"],
        "repair_retry": analysis["repair_retry"],
        "review_conclusions": analysis["review_conclusions"],
        "criteria": analysis["criteria"],
        "exit_candidate": all(analysis["criteria"].values()),
        "rollback_drill": analysis["rollback_drill"],
    }


def _validated_report(value: Mapping[str, Any]) -> Mapping[str, Any]:
    if value.get("schema") != CONTEXT_AB_SCHEMA:
        raise ValueError("context A/B suite received an unsupported report")
    arms = value.get("arms")
    if not isinstance(arms, Mapping) or not all(
        isinstance(arms.get(name), Mapping)
        for name in ("shadow", "bounded")
    ):
        raise ValueError("context A/B suite report lacks shadow/bounded arms")
    if not str(value.get("task_id") or ""):
        raise ValueError("context A/B suite report lacks task identity")
    return value


__all__ = [
    "CONTEXT_AB_SUITE_SCHEMA",
    "build_context_ab_suite_report",
]
