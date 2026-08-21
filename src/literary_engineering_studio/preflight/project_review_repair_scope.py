"""Compile narrow deterministic Canon repair effects from Agent candidates."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from io import StringIO
import json
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from ..contracts import TaskPackage
from ..sandbox import SandboxManifest
from literary_engineering_studio_engine.public.literary import (
    SCENE_LIFECYCLE_VALUES,
    SceneLifecycleStatus,
)


_SCENE_STATUS_ISSUE = "scene-status-invalid"
_CHAPTER_SCENE_ISSUES = frozenset(
    {"chapter-scene-fields-missing", "chapter-scene-not-ready"}
)


def canonicalize_project_review_repair_scope(
    task: TaskPackage,
    sandbox: SandboxManifest,
) -> list[dict[str, str]]:
    """Apply only lint-authorized structured fields to their baseline documents."""

    if task.current_state != "canon-review-pass" or sandbox.control_workspace is None:
        return []
    issues = _lint_issues(sandbox.control_workspace / "reviews" / "canon_lint.json")
    if not issues:
        return []
    targets = {
        str(item).replace("\\", "/").strip()
        for item in task.payload.get("repair_targets") or []
        if str(item).strip()
    }
    changes: list[dict[str, str]] = []
    for relative, check_ids in _issues_by_target(issues).items():
        if relative not in targets:
            continue
        if _SCENE_STATUS_ISSUE in check_ids:
            change = _compile_scene_status(relative, sandbox)
            if change:
                changes.append(change)
        if check_ids & _CHAPTER_SCENE_ISSUES:
            change = _compile_chapter_scene_statuses(relative, sandbox)
            if change:
                changes.append(change)
    return changes


def _compile_scene_status(
    relative: str,
    sandbox: SandboxManifest,
) -> dict[str, str] | None:
    control_workspace = sandbox.control_workspace
    if control_workspace is None:
        return None
    baseline_path = control_workspace / Path(relative)
    candidate_path = sandbox.workspace / Path(relative)
    baseline = _read_yaml_mapping(baseline_path)
    candidate = _read_yaml_mapping(candidate_path)
    status = str(candidate.get("status") or "").strip()
    if not baseline or status not in SCENE_LIFECYCLE_VALUES:
        return None
    baseline["status"] = status
    _write_yaml_mapping(candidate_path, baseline)
    return {"path": relative, "scope": "status", "value": status}


def _compile_chapter_scene_statuses(
    relative: str,
    sandbox: SandboxManifest,
) -> dict[str, str] | None:
    control_workspace = sandbox.control_workspace
    if control_workspace is None:
        return None
    baseline_path = control_workspace / Path(relative)
    candidate_path = sandbox.workspace / Path(relative)
    baseline = _read_json_mapping(baseline_path)
    candidate = _read_json_mapping(candidate_path)
    baseline_scenes = baseline.get("scenes")
    candidate_scenes = candidate.get("scenes")
    if not isinstance(baseline_scenes, list) or not isinstance(candidate_scenes, list):
        return None
    candidate_statuses = {
        str(item.get("scene_id") or "").strip(): str(item.get("status") or "").strip()
        for item in candidate_scenes
        if isinstance(item, Mapping)
    }
    updated = 0
    for item in baseline_scenes:
        if not isinstance(item, MutableMapping):
            continue
        scene_id = str(item.get("scene_id") or "").strip()
        status = candidate_statuses.get(scene_id, "")
        if status != SceneLifecycleStatus.READY:
            continue
        item["status"] = status
        updated += 1
    if not updated:
        return None
    candidate_path.write_text(
        json.dumps(baseline, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"path": relative, "scope": "scenes[].status", "value": str(updated)}


def _lint_issues(path: Path) -> list[Mapping[str, Any]]:
    payload = _read_json_mapping(path)
    issues = payload.get("issues")
    if not isinstance(issues, list):
        return []
    return [item for item in issues if isinstance(item, Mapping)]


def _issues_by_target(
    issues: list[Mapping[str, Any]],
) -> dict[str, set[str]]:
    grouped: dict[str, set[str]] = {}
    for issue in issues:
        relative = str(issue.get("location") or "").replace("\\", "/").strip()
        check_id = str(issue.get("check_id") or "").strip()
        if relative and check_id:
            grouped.setdefault(relative, set()).add(check_id)
    return grouped


def _read_json_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_yaml_mapping(path: Path) -> MutableMapping[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = _yaml().load(path.read_text(encoding="utf-8"))
    except (OSError, YAMLError):
        return {}
    return payload if isinstance(payload, MutableMapping) else {}


def _write_yaml_mapping(path: Path, payload: MutableMapping[str, Any]) -> None:
    stream = StringIO()
    _yaml().dump(payload, stream)
    path.write_text(stream.getvalue(), encoding="utf-8")


def _yaml() -> YAML:
    parser = YAML(typ="rt")
    parser.allow_duplicate_keys = False
    parser.preserve_quotes = True
    parser.width = 4096
    return parser


__all__ = ["canonicalize_project_review_repair_scope"]
