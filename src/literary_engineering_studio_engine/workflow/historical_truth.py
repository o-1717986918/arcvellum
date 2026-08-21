"""Workflow projections for immutable promoted-scene history."""

from __future__ import annotations

from pathlib import Path

from ..literary.scene.promotion.historical import HistoricalPromotionValidation
from ..literary.scene.promotion.historical import validate_historical_promotion
from ..literary.scene.promotion.gate_support import is_revision_candidate_path
from ..literary.scene.promotion.generation_gate import candidate_generation_gate


def candidate_supersedes_promotion(
    promoted: Path | None,
    latest: Path | None,
) -> bool:
    if latest is None or promoted is None:
        return latest is not None
    return (
        latest.resolve() != promoted.resolve()
        and latest.stat().st_mtime_ns > promoted.stat().st_mtime_ns
    )


def preserve_valid_revision_preparation_steps(
    root: Path,
    scene_id: str,
    candidate: Path | None,
    steps: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Do not rerun creative preparation for an exact valid revision candidate."""

    if candidate is None or not is_revision_candidate_path(root, candidate):
        return steps
    gate = candidate_generation_gate(root, scene_id, candidate)
    if gate.get("status") != "pass":
        return steps
    sealed_keys = {
        "roleplay-simulation",
        "roleplay-agent-task",
        "branch-manifest",
        "branch-agent-task",
        "branch-selection",
        "composition-json",
        "composition-agent-task",
    }
    result: list[dict[str, object]] = []
    for step in steps:
        if step.get("key") not in sealed_keys or step.get("status") == "pass":
            result.append(step)
            continue
        sealed = dict(step)
        sealed.update(
            {
                "status": "pass",
                "message": (
                    "sealed by exact historical revision provenance; current-context "
                    "AgentReview, promotion, and writeback remain mandatory"
                ),
                "next_action": "",
                "historical_revision_preparation": True,
            }
        )
        result.append(sealed)
    return result


def preserve_current_historical_style_steps(
    root: Path,
    scene_id: str,
    steps: list[dict[str, object]],
    candidate: Path | None = None,
) -> list[dict[str, object]]:
    steps = preserve_valid_revision_preparation_steps(root, scene_id, candidate, steps)
    historical = validate_historical_promotion(root, scene_id)
    if not historical.passed or not historical.current:
        return steps
    steps = preserve_promoted_preparation_steps(steps, historical)
    return preserve_historical_style_steps(root, steps, historical)


def preserve_promoted_preparation_steps(
    steps: list[dict[str, object]],
    historical: HistoricalPromotionValidation,
) -> list[dict[str, object]]:
    """Seal pre-promotion preparation after the promotion itself is current."""

    sealed_keys = {
        "roleplay-simulation",
        "roleplay-agent-task",
        "branch-manifest",
        "branch-agent-task",
        "branch-selection",
        "composition-json",
        "composition-agent-task",
    }
    result: list[dict[str, object]] = []
    for step in steps:
        if step.get("key") not in sealed_keys or step.get("status") == "pass":
            result.append(step)
            continue
        sealed = dict(step)
        sealed.update(
            {
                "status": "pass",
                "message": (
                    "sealed by the current tamper-evident promotion; "
                    "post-promotion review and writeback remain mandatory"
                ),
                "next_action": "",
                "historical_promotion_preparation": True,
                "historical_candidate": str(historical.candidate_path or ""),
            }
        )
        result.append(sealed)
    return result


def preserve_current_historical_style_gates(
    root: Path,
    scene_id: str,
    gates: list[dict[str, str]],
) -> None:
    historical = validate_historical_promotion(root, scene_id)
    if historical.passed and historical.current:
        preserve_historical_style_gates(gates, scene_id, historical)


def preserve_historical_style_steps(
    root: Path,
    steps: list[dict[str, object]],
    historical: HistoricalPromotionValidation,
) -> list[dict[str, object]]:
    """Keep sealed style-dependent steps valid after a later style switch."""

    sealed_keys = {
        "context-trace",
        "composition-json",
        "candidate-generation-provenance",
        "generation-agent-task",
        "candidate-review",
        "candidate-revision",
        "candidate-human-decision",
        "agent-review-task",
    }
    result: list[dict[str, object]] = []
    for step in steps:
        if step.get("key") not in sealed_keys or step.get("status") == "pass":
            result.append(step)
            continue
        sealed = dict(step)
        sealed.update(
            {
                "status": "pass",
                "message": (
                    "sealed by historical promotion evidence; the active style "
                    "applies to future prose, not this promoted scene"
                ),
                "next_action": "",
                "historical_truth": True,
                "historical_candidate": _relative_candidate(root, historical),
            }
        )
        result.append(sealed)
    return result


def preserve_historical_style_gates(
    gates: list[dict[str, str]],
    scene_id: str,
    historical: HistoricalPromotionValidation,
) -> None:
    """Project sealed pre-promotion proof without weakening unrelated gates."""

    sealed_labels = {
        "context-trace",
        "candidate-generation-provenance",
        "candidate-review-pass",
        "promotion-candidate-review",
        "style-adherence-review",
    }
    candidate = (
        historical.candidate_path.name
        if historical.candidate_path is not None
        else "promoted candidate"
    )
    for gate in gates:
        label = str(gate.get("key") or "").removeprefix(f"{scene_id}:")
        if label not in sealed_labels or gate.get("status") == "pass":
            continue
        gate["status"] = "pass"
        gate["message"] = (
            f"{scene_id} {candidate} is sealed Historical Truth; a later style "
            "mount applies only to future prose."
        )


def _relative_candidate(
    root: Path,
    historical: HistoricalPromotionValidation,
) -> str:
    if historical.candidate_path is None:
        return ""
    try:
        return historical.candidate_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(historical.candidate_path)
