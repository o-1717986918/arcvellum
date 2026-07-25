"""Exact style-version checks shared by scene promotion gates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...style.snapshot import (
    active_style_mount_snapshot_payload,
    artifact_style_mount_snapshot,
    read_artifact_style_mount_snapshot,
    style_mount_snapshot_errors,
)


def candidate_style_snapshot(candidate_path: Path) -> dict[str, Any]:
    return read_artifact_style_mount_snapshot(candidate_path.with_suffix(".json"))


def generation_style_snapshot_errors(
    root: Path,
    scene_id: str,
    *,
    candidate: dict[str, Any],
    prompt: dict[str, Any],
) -> list[str]:
    return style_mount_snapshot_errors(
        root,
        {
            "context trace": _read_json(
                root / "memory" / "context_packets" / f"{scene_id}.trace.json"
            ).get("style_mount_snapshot"),
            "composition": _read_json(
                root / "drafts" / "compositions" / f"{scene_id}_composition.json"
            ).get("style_mount_snapshot"),
            "prompt manifest": artifact_style_mount_snapshot(prompt),
            "candidate manifest": artifact_style_mount_snapshot(candidate),
        },
    )


def review_style_snapshot_gate(
    root: Path,
    candidate_path: Path,
    review: dict[str, Any],
) -> dict[str, object]:
    errors = style_mount_snapshot_errors(
        root,
        {
            "candidate manifest": read_artifact_style_mount_snapshot(
                candidate_path.with_suffix(".json")
            ),
            "prompt manifest": read_artifact_style_mount_snapshot(
                candidate_path.with_suffix(".prompt.json")
            ),
            "scene review": artifact_style_mount_snapshot(review),
        },
    )
    return {
        "current": active_style_mount_snapshot_payload(root),
        "errors": errors,
        "passed": not errors,
    }


def review_style_failure(
    style_status: str,
    snapshot_gate: dict[str, object],
) -> tuple[str, str] | None:
    if not snapshot_gate["passed"]:
        errors = snapshot_gate["errors"]
        return "style_mount_snapshot_stale", "; ".join(str(item) for item in errors)
    if style_status not in {"pass", "pass_with_notes"}:
        return (
            "style_failed",
            "mounted style review did not pass for this candidate: "
            f"style_adherence.status={style_status or 'missing'}",
        )
    return None


def review_style_state(
    root: Path,
    candidate_path: Path,
    review: dict[str, Any],
    *,
    style_required: bool,
    style_status: str,
) -> tuple[dict[str, object], list[str], tuple[str, str] | None, bool]:
    gate = review_style_snapshot_gate(root, candidate_path, review)
    errors = gate["errors"]
    failure = review_style_failure(style_status, gate) if style_required else None
    return gate, errors, failure, failure is None


def review_style_snapshot_projection(gate: dict[str, object]) -> dict[str, object]:
    return {
        "style_mount_snapshot": gate["current"],
        "style_mount_snapshot_errors": gate["errors"],
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


__all__ = [
    "candidate_style_snapshot",
    "generation_style_snapshot_errors",
    "review_style_failure",
    "review_style_snapshot_projection",
    "review_style_state",
    "review_style_snapshot_gate",
]
