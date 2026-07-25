"""Safe stale-impact projection for an exact prospective style mount."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable

from literary_engineering_studio_engine.literary.style.snapshot import (
    artifact_style_mount_snapshot,
)
from literary_engineering_studio_engine.literary.scene.promotion.historical import (
    validate_historical_promotion,
)


_ARTIFACT_GROUPS = (
    ("context", "memory/context_packets/*.trace.json"),
    ("composition", "drafts/compositions/*_composition.json"),
    ("generation", "drafts/candidates/*.prompt.json"),
    ("candidate", "drafts/candidates/*.json"),
    ("review", "reviews/agent/*_scene_review.json"),
    ("revision", "drafts/revisions/*_revision.prompt.json"),
    ("revision", "drafts/revisions/*_revision.json"),
)
_SCENE_ID_RE = re.compile(r"(scene_[0-9]+)", re.IGNORECASE)


def project_style_mount_impact(
    project_root: Path,
    *,
    current_snapshot: dict[str, object],
    target_snapshot: dict[str, object],
) -> dict[str, object]:
    """Describe non-historical scene artifacts that a mount switch will stale."""

    root = project_root.expanduser().resolve()
    target_digest = str(target_snapshot.get("digest") or "")
    affected, historical_artifact_count, inspected_artifact_count = (
        _collect_affected_artifacts(root, target_digest)
    )
    entries = [_public_entry(affected[key]) for key in sorted(affected)]
    changed = _identity(current_snapshot) != _identity(target_snapshot)
    payload: dict[str, object] = {
        "schema": "arcvellum/style-mount-impact-preview/v1",
        "status": "would-propagate" if changed and entries else "not-required",
        "mount_changes": changed,
        "affected_scene_count": len(entries),
        "affected_artifact_count": sum(
            int(entry["artifact_count"]) for entry in entries
        ),
        "historical_artifact_count": historical_artifact_count,
        "inspected_artifact_count": inspected_artifact_count,
        "entries": entries,
        "invalidated_stages": sorted(
            {
                stage
                for entry in entries
                for stage in entry["stages"]
                if isinstance(stage, str)
            }
        ),
        "historical_prose": "preserved",
    }
    payload["revision"] = _payload_hash(
        {
            "current": _identity(current_snapshot),
            "target": _identity(target_snapshot),
            **payload,
        }
    )
    return payload


def _collect_affected_artifacts(
    root: Path,
    target_digest: str,
) -> tuple[dict[str, dict[str, object]], int, int]:
    affected: dict[str, dict[str, object]] = {}
    historical_count = 0
    inspected_count = 0
    for stage, path in _artifact_paths(root):
        payload = _read_json(path)
        scene_id = _scene_id(payload, path)
        if not scene_id:
            continue
        recorded = artifact_style_mount_snapshot(payload)
        if not recorded and not _looks_like_formal_scene_artifact(payload):
            continue
        inspected_count += 1
        if _is_historical_artifact(root, scene_id, path):
            historical_count += 1
        elif str(recorded.get("digest") or "") != target_digest:
            _record_affected(affected, scene_id, stage, recorded)
    return affected, historical_count, inspected_count


def _record_affected(
    affected: dict[str, dict[str, object]],
    scene_id: str,
    stage: str,
    recorded: dict[str, Any],
) -> None:
    entry = affected.setdefault(
        scene_id,
        {
            "scene_id": scene_id,
            "stages": [],
            "artifact_count": 0,
            "recorded_versions": set(),
            "reason": "文风版本变化后，这条未晋升场景链必须重新取得当前文风快照。",
        },
    )
    stages = entry["stages"]
    if isinstance(stages, list) and stage not in stages:
        stages.append(stage)
    entry["artifact_count"] = int(entry["artifact_count"]) + 1
    recorded_versions = entry["recorded_versions"]
    if isinstance(recorded_versions, set):
        recorded_versions.add(
            str(recorded.get("version_id") or "未绑定不可变版本")
        )


def _artifact_paths(root: Path) -> Iterable[tuple[str, Path]]:
    seen: set[Path] = set()
    for stage, pattern in _ARTIFACT_GROUPS:
        for path in sorted(root.glob(pattern)):
            resolved = path.resolve()
            if resolved in seen or not resolved.is_relative_to(root):
                continue
            seen.add(resolved)
            if path.name.endswith((".agent_completion.json", ".agent.json")):
                continue
            yield stage, path


def _is_historical_artifact(root: Path, scene_id: str, path: Path) -> bool:
    promotion = root / "drafts" / "promotions" / f"{scene_id}_promotion.json"
    if not promotion.is_file():
        return False
    validation = validate_historical_promotion(root, scene_id)
    if not validation.passed:
        return False
    try:
        return path.stat().st_mtime_ns <= promotion.stat().st_mtime_ns
    except OSError:
        return False


def _looks_like_formal_scene_artifact(payload: dict[str, Any]) -> bool:
    schema = str(payload.get("schema") or "")
    return bool(payload.get("scene_id")) and (
        "scene" in schema
        or "context" in schema
        or "composition" in schema
        or "revision" in schema
    )


def _scene_id(payload: dict[str, Any], path: Path) -> str:
    direct = str(payload.get("scene_id") or "").strip()
    if direct:
        return direct
    match = _SCENE_ID_RE.search(path.name)
    return match.group(1).lower() if match else ""


def _public_entry(entry: dict[str, object]) -> dict[str, object]:
    versions = entry.get("recorded_versions")
    return {
        **entry,
        "stages": sorted(
            str(item) for item in entry.get("stages", []) if str(item)
        ),
        "recorded_versions": sorted(versions) if isinstance(versions, set) else [],
    }


def _identity(payload: dict[str, object]) -> dict[str, str]:
    return {
        field: str(payload.get(field) or "")
        for field in (
            "style_id",
            "version_id",
            "content_hash",
            "prompt_sha256",
            "digest",
        )
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _payload_hash(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
