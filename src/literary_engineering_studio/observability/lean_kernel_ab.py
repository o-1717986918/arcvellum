"""Read-only evidence contract for strict-v1 versus lean-v2."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean
from typing import Any, Mapping


LITERARY_DIMENSIONS = (
    "character_credibility",
    "scene_function",
    "style_identity",
    "subtext",
    "rhythm",
    "handoff",
    "reader_question_management",
)


@dataclass(frozen=True)
class RouteEvidence:
    route: str
    model_calls: int
    recoverable_states: int
    project_agent_task_files: int
    committed_hanzi: int = 0
    canon_regressions: int = 0

    def __post_init__(self) -> None:
        for name in (
            "model_calls",
            "recoverable_states",
            "project_agent_task_files",
            "committed_hanzi",
            "canon_regressions",
        ):
            if int(getattr(self, name)) < 0:
                raise ValueError(f"{name} must be non-negative")


def compare_routes(
    strict: RouteEvidence,
    lean: RouteEvidence,
    *,
    literary_scores: Mapping[str, Mapping[str, float]] | None = None,
    noninferiority_margin: float = 0.25,
) -> dict[str, Any]:
    """Build an evidence report without conflating efficiency and quality."""

    reductions = {
        "model_calls": _reduction(strict.model_calls, lean.model_calls),
        "recoverable_states": _reduction(
            strict.recoverable_states,
            lean.recoverable_states,
        ),
        "project_agent_task_files": _reduction(
            strict.project_agent_task_files,
            lean.project_agent_task_files,
        ),
    }
    structural = {
        "standard_model_calls_at_most_two": lean.model_calls <= 2,
        "project_agent_task_files_reduced_at_least_70_percent": (
            reductions["project_agent_task_files"] >= 0.70
        ),
        "no_more_canon_regressions": (
            lean.canon_regressions <= strict.canon_regressions
        ),
    }
    quality = _quality_evidence(
        literary_scores,
        margin=max(0.0, float(noninferiority_margin)),
    )
    structural_pass = all(structural.values())
    ready = structural_pass and quality["available"] and quality["noninferior"]
    decision = (
        "ready-for-default"
        if ready
        else "pending-literary-evidence"
        if structural_pass and not quality["available"]
        else "hold"
    )
    return {
        "schema": "arcvellum/lean-kernel-ab/v1",
        "routes": {"strict-v1": asdict(strict), "lean-v2": asdict(lean)},
        "reductions": reductions,
        "structural_criteria": structural,
        "literary_quality": quality,
        "decision": decision,
        "ready_for_default": ready,
    }


def _quality_evidence(
    scores: Mapping[str, Mapping[str, float]] | None,
    *,
    margin: float,
) -> dict[str, Any]:
    if not scores:
        return {
            "available": False,
            "noninferior": False,
            "margin": margin,
            "reason": "blind literary scores were not supplied",
        }
    strict = scores.get("strict-v1") or {}
    lean = scores.get("lean-v2") or {}
    missing = [
        dimension
        for dimension in LITERARY_DIMENSIONS
        if dimension not in strict or dimension not in lean
    ]
    if missing:
        return {
            "available": False,
            "noninferior": False,
            "margin": margin,
            "missing_dimensions": missing,
            "reason": "literary rubric is incomplete",
        }
    strict_mean = mean(float(strict[item]) for item in LITERARY_DIMENSIONS)
    lean_mean = mean(float(lean[item]) for item in LITERARY_DIMENSIONS)
    return {
        "available": True,
        "noninferior": lean_mean + margin >= strict_mean,
        "margin": margin,
        "strict_mean": round(strict_mean, 4),
        "lean_mean": round(lean_mean, 4),
        "delta": round(lean_mean - strict_mean, 4),
    }


def _reduction(before: int, after: int) -> float:
    if before <= 0:
        return 0.0 if after else 1.0
    return round((before - after) / before, 4)


__all__ = ["LITERARY_DIMENSIONS", "RouteEvidence", "compare_routes"]
