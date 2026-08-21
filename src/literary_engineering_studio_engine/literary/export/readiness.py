"""Single export-readiness contract for chapter scenes."""

from __future__ import annotations

from pathlib import Path

from ..planning.chapter_inventory import is_final_chapter
from ..planning.delivery_length import delivery_length_status
from ..scene.promotion.historical_readiness import historical_scene_readiness


def export_scene_readiness_errors(
    root: Path,
    scene: dict[str, object],
) -> list[str]:
    """Validate one chapter-workspace scene against current or sealed evidence."""

    scene_id = str(scene.get("scene_id") or "") or "unknown"
    historical = historical_scene_readiness(root, scene_id)
    if historical is not None:
        historical_status, historical_issues = historical
        errors: list[str] = []
        if historical_status != "ready":
            errors.append(
                f"historically promoted chapter scene is not ready: {scene_id}: "
                + "; ".join(historical_issues)
            )
        if scene.get("status") != historical_status:
            errors.append(
                f"chapter workspace status does not match sealed promotion: {scene_id}"
            )
        return errors

    errors = []
    if scene.get("status") != "ready":
        errors.append(f"chapter scene must be ready: {scene_id}")
    if (
        scene.get("agent_review_conclusion") != "pass"
        or scene.get("agent_review_schema_status") != "pass"
    ):
        errors.append(f"chapter scene lacks clean platform AgentReview: {scene_id}")
    if scene.get("agent_review_source_match") is not True:
        errors.append(
            f"chapter scene AgentReview does not cite exact draft/candidate: {scene_id}"
        )
    if scene.get("agent_review_unresolved_notes"):
        errors.append(f"chapter scene has unresolved AgentReview notes: {scene_id}")
    if scene.get("flow_gate_issues") or scene.get("readiness_issues"):
        errors.append(
            f"chapter scene has unresolved flow/readiness gate issues: {scene_id}"
        )
    return errors


def final_delivery_length_errors(root: Path, chapter_id: str) -> list[str]:
    """Block only the final formal chapter when the whole-work target is short."""

    if not is_final_chapter(root, chapter_id):
        return []
    status = delivery_length_status(root)
    if status.target_chinese_chars <= 0 or status.met:
        return []
    if not status.inventory_complete:
        return [
            "final release requires a complete scene inventory before whole-work length can be accepted"
        ]
    return [
        "whole-work target length is not met: "
        f"actual={status.actual_chinese_chars}, "
        f"target={status.target_chinese_chars}, "
        f"shortfall={status.shortfall_chinese_chars} Chinese-content characters"
    ]


def require_final_delivery_length(root: Path, chapter_id: str) -> None:
    errors = final_delivery_length_errors(root, chapter_id)
    if errors:
        raise RuntimeError("; ".join(errors))


__all__ = [
    "export_scene_readiness_errors",
    "final_delivery_length_errors",
    "require_final_delivery_length",
]
