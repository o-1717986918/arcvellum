"""Route-local work-item selection for the formal task registry.

Selection is deliberately separate from task blueprints and gates: it only
chooses the current derived work item and never changes route order or writes
project artifacts.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path


def select_scene_state(
    root: Path,
    payload: dict[str, object],
    scene: Path | str | None,
    *,
    resolve_project_path: Callable[[Path, Path | str], Path],
    relative_path: Callable[[Path, Path], str],
    scene_id_for_path: Callable[[Path], str],
) -> dict[str, object] | None:
    scenes = [item for item in payload.get("scenes", []) if isinstance(item, dict)]
    if scene:
        scene_path = resolve_project_path(root, scene)
        scene_id = scene_id_for_path(scene_path)
        scene_rel = relative_path(scene_path, root)
        return next((item for item in scenes if item.get("scene_id") == scene_id or item.get("scene") == scene_rel), None)
    return next((item for item in scenes if item.get("status") != "ready"), None)


def select_longform_state(_root: Path, payload: dict[str, object], _scene: Path | str | None) -> dict[str, object] | None:
    state = payload.get("longform") if isinstance(payload.get("longform"), dict) else {}
    if not state or state.get("status") == "ready":
        return None
    return state


def select_source_ingest_state(_root: Path, payload: dict[str, object], scene: Path | str | None) -> dict[str, object] | None:
    items = [item for item in payload.get("source_ingests", []) if isinstance(item, dict)]
    return _select_target(items, scene, exact_fields=("work_id", "target_id"), suffix_fields=("import_dir",))


def select_style_engineering_state(_root: Path, payload: dict[str, object], scene: Path | str | None) -> dict[str, object] | None:
    items = [item for item in payload.get("styles", []) if isinstance(item, dict)]
    return _select_target(items, scene, exact_fields=("profile_id", "target_id"), suffix_fields=("profile_dir",))


def select_asset_state(_root: Path, payload: dict[str, object], scene: Path | str | None) -> dict[str, object] | None:
    items = [item for item in payload.get("assets", []) if isinstance(item, dict)]
    return _select_target(items, scene, exact_fields=("candidate_id", "target_id"), suffix_fields=("candidate",))


def select_review_audit_state(_root: Path, payload: dict[str, object], _scene: Path | str | None) -> dict[str, object] | None:
    items = [item for item in payload.get("audits", []) if isinstance(item, dict)]
    return next((item for item in items if item.get("status") != "ready"), None)


def select_export_release_state(_root: Path, payload: dict[str, object], scene: Path | str | None) -> dict[str, object] | None:
    items = [item for item in payload.get("exports", []) if isinstance(item, dict)]
    return _select_target(items, scene, exact_fields=("chapter_id", "target_id", "scene_id"))


def _select_target(
    items: list[dict[str, object]],
    scene: Path | str | None,
    *,
    exact_fields: tuple[str, ...],
    suffix_fields: tuple[str, ...] = (),
) -> dict[str, object] | None:
    if scene:
        target = str(scene).replace("\\", "/").strip("/")
        return next(
            (
                item
                for item in items
                if any(str(item.get(field) or "") == target for field in exact_fields)
                or any(str(item.get(field) or "").rstrip("/").endswith(target) for field in suffix_fields)
            ),
            None,
        )
    return next((item for item in items if item.get("status") != "ready"), None)
