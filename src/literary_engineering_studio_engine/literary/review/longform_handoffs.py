"""Cross-scene handoff checks used by the long-form audit."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from ..scene.context.handoff import ordered_scene_ids, scene_handoff_source_status
from ..scene.facts import load_scene_facts


def audit_scene_handoffs(root: Path, completed_scene_ids: Iterable[str]) -> dict[str, Any]:
    completed = set(completed_scene_ids)
    ordered = ordered_scene_ids(root)
    required = [scene_id for scene_id in ordered[:-1] if scene_id in completed]
    issues: list[dict[str, str]] = []
    passed = 0
    for scene_id in required:
        valid, message, payload = scene_handoff_source_status(root, scene_id)
        if not valid:
            issues.append(_handoff_issue(scene_id, message, "重新完成该场景写回并生成摘要绑定的 scene-handoff。"))
            continue
        successor = str(payload.get("successor_scene_id") or "")
        bridge_error = _bridge_error(root, payload, successor)
        if bridge_error:
            issues.append(_handoff_issue(scene_id, bridge_error, "为前场补出场钩子，并为后场补可解释的入场压力。"))
            continue
        passed += 1
    return {
        "required_count": len(required),
        "pass_count": passed,
        "issue_count": len(issues),
        "issues": issues,
    }


def _bridge_error(root: Path, payload: dict[str, Any], successor: str) -> str:
    outgoing = [str(item).strip() for item in payload.get("outgoing_hooks") or [] if str(item).strip()]
    if not outgoing and not str(payload.get("causal_pressure_for_next_scene") or "").strip():
        return "scene handoff lacks outgoing causal pressure"
    successor_path = root / "scenes" / f"{successor}.yaml"
    if not successor or not successor_path.is_file():
        return "scene handoff successor scene is missing"
    try:
        incoming = load_scene_facts(successor_path).incoming_pressure
    except ValueError as exc:
        return str(exc)
    return "" if incoming else "successor scene lacks scene_bridge.incoming_pressure"


def _handoff_issue(scene_id: str, message: str, recommendation: str) -> dict[str, str]:
    return {
        "severity": "medium",
        "category": "scene_handoff",
        "subject": scene_id,
        "message": message,
        "recommendation": recommendation,
    }


__all__ = ["audit_scene_handoffs"]
