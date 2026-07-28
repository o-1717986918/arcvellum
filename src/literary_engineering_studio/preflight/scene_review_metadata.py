"""Task-owned metadata normalization for formal scene review outputs."""

from __future__ import annotations

import json
from pathlib import Path

from ..contracts import TaskPackage
from ..sandbox import SandboxManifest
from .style_snapshot import candidate_style_snapshot
from literary_engineering_studio_engine.creative_quality import (
    creative_quality_profile_exists,
    creative_quality_profile_path,
    load_creative_quality_profile,
)


def canonicalize_scene_review_metadata(
    task: TaskPackage,
    sandbox: SandboxManifest,
) -> list[dict[str, str]]:
    """Bind machine facts while preserving the Agent's verdict and evidence."""

    if task.current_state not in {"candidate-review", "agent-review-task"}:
        return []
    review_rel = _review_output(task)
    candidate_rel = _candidate_path(task)
    review_path = sandbox.workspace / Path(review_rel)
    candidate_path = sandbox.workspace / Path(candidate_rel)
    if not review_path.is_file() or not candidate_path.is_file():
        return []
    payload = _read_review(review_path)
    if not payload:
        return []

    expected: dict[str, object] = {
        "schema": "literary-engineering-workbench/scene-review-agent/v1",
        "scene_id": str(task.payload.get("scene_id") or task.scene_id or "").strip(),
        "candidate": candidate_rel,
        "source_paths": [
            str(item).replace("\\", "/") for item in task.source_paths
        ],
        "reviewer_session_id": _session_identity(task, "reviewer"),
        "style_mount_snapshot": candidate_style_snapshot(candidate_path),
    }
    quality_identity = _creative_quality_identity(sandbox.workspace)
    if quality_identity:
        expected["creative_quality_profile"] = quality_identity

    changed = [
        field for field, value in expected.items() if payload.get(field) != value
    ]
    if not changed:
        return []
    payload.update(expected)
    review_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return [
        {
            "path": review_rel,
            "field": field,
            "reason": "normalized deterministic scene-review metadata",
        }
        for field in changed
    ]


def _review_output(task: TaskPackage) -> str:
    return next(
        (
            relative
            for relative in task.expected_outputs
            if relative.endswith(".json")
            and "scene_review" in relative
            and not relative.endswith(".agent_completion.json")
        ),
        "",
    )


def _candidate_path(task: TaskPackage) -> str:
    declared = str(task.payload.get("candidate") or "").replace("\\", "/").strip()
    if declared:
        return declared
    return next(
        (
            relative
            for relative in task.source_paths
            if relative.replace("\\", "/").startswith("drafts/candidates/")
            and relative.endswith(".md")
        ),
        "",
    )


def _read_review(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    if not str(payload.get("conclusion") or "").strip():
        return {}
    if not str(payload.get("summary") or "").strip():
        return {}
    return payload


def _creative_quality_identity(workspace: Path) -> dict[str, object]:
    if not creative_quality_profile_exists(workspace):
        return {}
    profile = load_creative_quality_profile(workspace)
    return {
        "path": creative_quality_profile_path(workspace)
        .relative_to(workspace)
        .as_posix(),
        "revision": profile.get("revision"),
        "digest": profile.get("digest"),
        "name": profile.get("name"),
    }


def _session_identity(task: TaskPackage, role: str) -> str:
    return f"studio:{role}:{task.task_id}"


__all__ = ["canonicalize_scene_review_metadata"]
