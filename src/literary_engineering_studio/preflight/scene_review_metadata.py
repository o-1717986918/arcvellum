"""Task-owned metadata normalization for formal scene review outputs."""

from __future__ import annotations

import json
from pathlib import Path

from ..contracts import TaskPackage
from ..sandbox import SandboxManifest
from .style_snapshot import candidate_style_snapshot
from literary_engineering_studio_engine.literary.review.creative_quality import (
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
    expected.update(_derived_review_fields(payload, sandbox.workspace))

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


def _canon_writeback_status(value: object) -> str:
    """Derive lifecycle status from the Agent-owned Canon judgment.

    ``canon_change`` is semantic judgment.  ``status`` only routes that
    judgment through the deterministic state machine and must not become a
    second model-authored vocabulary that can disagree with it.
    """

    if not isinstance(value, dict):
        return ""
    change = value.get("canon_change")
    if change is True:
        return "pending_canon_evolve"
    if change is False:
        return "not_required"
    if isinstance(change, str):
        normalized = change.strip().lower()
        if normalized == "true":
            return "pending_canon_evolve"
        if normalized == "false":
            return "not_required"
        if normalized == "unknown":
            return "unknown"
    return ""


def _derived_review_fields(
    payload: dict[str, object], workspace: Path
) -> dict[str, object]:
    fields: dict[str, object] = {}
    canon = payload.get("canon_writeback")
    status = _canon_writeback_status(canon)
    if status and isinstance(canon, dict):
        normalized_canon = dict(canon)
        normalized_canon["status"] = status
        fields["canon_writeback"] = normalized_canon
    register = _normalize_character_register(
        payload.get("new_character_register"), workspace
    )
    if register:
        fields["new_character_register"] = register
    return fields


def _normalize_character_register(value: object, workspace: Path) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    register = dict(value)
    formal = _formal_character_paths(workspace)
    introduced = register.get("introduced")
    if isinstance(introduced, list):
        register["introduced"] = [
            _normalize_character_row(item, formal) if isinstance(item, dict) else item
            for item in introduced
        ]
    waivers = register.get("ephemeral_waivers")
    if isinstance(waivers, list):
        register["ephemeral_waivers"] = [
            _normalize_character_row(item, formal) if isinstance(item, dict) else item
            for item in waivers
        ]
    return register


def _normalize_character_row(
    value: dict[str, object], formal: dict[str, str]
) -> dict[str, object]:
    row = dict(value)
    name = str(
        row.get("name") or row.get("character") or row.get("display_name") or ""
    ).strip()
    if name:
        row["name"] = name
    if not row.get("waiver_reason"):
        reason = str(row.get("waiver") or row.get("reason") or "").strip()
        if reason:
            row["waiver_reason"] = reason
    kind = str(row.get("type") or "").strip().lower()
    if not row.get("persistence"):
        if "existing" in kind:
            row["persistence"] = "main"
        elif kind in {"referenced_only", "reference_only", "cameo", "ephemeral"}:
            row["persistence"] = "ephemeral"
    formal_path = formal.get(name) or formal.get(_character_token(name))
    if formal_path:
        row["already_in_characters"] = True
        row["formal_character_path"] = formal_path
    return row


def _formal_character_paths(workspace: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    characters = workspace / "characters"
    for path in sorted([*characters.glob("*.yaml"), *characters.glob("*.yml")]):
        if path.name.startswith("_"):
            continue
        relative = path.relative_to(workspace).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        aliases = [path.stem]
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(("name:", "character_id:")):
                aliases.append(stripped.split(":", 1)[1].strip().strip("'\""))
        for alias in aliases:
            if alias:
                result[alias] = relative
                result[_character_token(alias)] = relative
    return result


def _character_token(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


__all__ = ["canonicalize_scene_review_metadata"]
