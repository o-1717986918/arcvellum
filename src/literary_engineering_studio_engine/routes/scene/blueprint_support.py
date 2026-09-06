"""Filesystem-derived support values for scene task blueprints."""

from __future__ import annotations

import hashlib
from pathlib import Path

from ...literary.scene.promotion.context_archive import context_archive_output_paths
from ...literary.scene.promotion.historical_context import (
    historical_revision_candidate_source_paths,
)
from ...literary.scene.promotion.legacy_context_bootstrap import (
    legacy_context_migration_output_paths,
)
from literary_engineering_studio_engine.routes.scene.support import _unique
from ...tasking.paths import read_json
from literary_engineering_studio_engine.tasking.paths import relative_path, resolve_project_path


def state_patch_character_files(root: Path, state_patch: str) -> list[str]:
    """Return existing in-project character files mutated by state apply."""

    patch_path = root / f"{state_patch}.json"
    if not patch_path.is_file():
        return []
    payload = read_json(patch_path)
    character_files: list[str] = []
    for item in payload.get("characters") or []:
        if not isinstance(item, dict):
            continue
        raw_path = str(item.get("file") or "").replace("\\", "/").strip()
        if not raw_path:
            character_id = str(item.get("character_id") or "").strip()
            raw_path = f"characters/{character_id}.yaml" if character_id else ""
        if not raw_path:
            continue
        candidate = resolve_project_path(root, raw_path)
        try:
            relative = candidate.resolve().relative_to(root.resolve()).as_posix()
        except (OSError, ValueError):
            continue
        if relative.startswith("characters/") and candidate.is_file():
            character_files.append(relative)
    return _unique(character_files)


def matching_revision_choice_sources(
    root: Path,
    scene_id: str,
    revision_source: str,
) -> list[str]:
    """Return consumed revision choices bound to the exact source body."""

    source = resolve_project_path(root, revision_source)
    if not source.is_file():
        return []
    source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    choices = root / "workflow" / "human_choices"
    matches: list[tuple[int, str]] = []
    paths = choices.glob("choice.revision_direction.*.json") if choices.is_dir() else ()
    for path in paths:
        payload = read_json(path)
        target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
        if payload.get("consumed") is not True:
            continue
        if str(payload.get("decision_type") or "") != "revision_direction":
            continue
        if str(target.get("target_id") or "") != scene_id:
            continue
        if str(target.get("candidate_path") or "").replace("\\", "/") != revision_source:
            continue
        if str(target.get("candidate_sha256") or "").lower() != source_sha256:
            continue
        matches.append((path.stat().st_mtime_ns, relative_path(path, root)))
    return [max(matches)[1]] if matches else []


def reader_obligation_outputs(chapter_id: str) -> list[str]:
    base = f"plot/chapter_obligations/{chapter_id}"
    return [
        f"{base}.json",
        f"{base}.md",
        f"{base}.agent_tasks.md",
        f"{base}.agent_completion.json",
    ]


def promotion_archive_outputs(
    root: Path,
    scene_id: str,
    candidate: Path | None,
) -> list[str]:
    return list(context_archive_output_paths(root, scene_id, candidate)) if candidate else []


def candidate_markdown(root: Path, scene_id: str, candidate: Path | None) -> str:
    return relative_path(candidate, root) if candidate else (
        f"drafts/candidates/{scene_id}-platform-agent.md"
    )


def promotion_historical_sources(
    root: Path,
    scene_id: str,
    candidate: Path | None,
) -> tuple[str, ...]:
    return (
        historical_revision_candidate_source_paths(root, scene_id, candidate)
        if candidate
        else ()
    )


def legacy_revision_migration_outputs(
    root: Path,
    scene_id: str,
    revision_source: str,
) -> tuple[str, ...]:
    if revision_source != f"drafts/scenes/{scene_id}.md":
        return ()
    return legacy_context_migration_output_paths(root, scene_id)


def select_blueprint(
    current_state: str,
    writeback: dict[str, object] | None,
    table: dict[str, dict[str, object]],
    default: dict[str, object],
) -> dict[str, object]:
    return writeback if writeback is not None else table.get(current_state, default)


__all__ = [
    "candidate_markdown",
    "legacy_revision_migration_outputs",
    "matching_revision_choice_sources",
    "promotion_archive_outputs",
    "promotion_historical_sources",
    "reader_obligation_outputs",
    "select_blueprint",
    "state_patch_character_files",
]
