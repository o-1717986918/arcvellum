"""Compact editorial brief derived from existing read-only projections."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def build_story_brief(
    library: Mapping[str, Any], reader: Mapping[str, Any]
) -> dict[str, Any]:
    scenes, characters, rhythm, continuity = _project_sections(library)
    sections = _mapping(library.get("sections"))
    drafts = _section_rows(sections, library, "drafts")
    units = _rows(reader.get("units"))
    formal_scene_ids = _formal_scene_ids(units)
    completed = _completed_beats(scenes, rhythm, formal_scene_ids, units, drafts)
    open_threads = _open_threads(continuity)
    return {
        "formal_units": _formal_units(reader, units),
        "completed_beats": completed[:8],
        "main_characters": _main_characters(characters),
        "recent_changes": _recent_changes(continuity),
        "open_threads": open_threads,
        "next_planned_scene": _next_scene(scenes, formal_scene_ids),
        "continuity_status": _continuity_status(continuity, open_threads, reader),
    }


def _project_sections(
    library: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    sections = _mapping(library.get("sections"))
    scenes = _section_rows(sections, library, "scenes")
    characters = _section_rows(sections, library, "characters")
    rhythm = {
        str(item.get("id") or ""): item
        for item in _section_rows(sections, library, "rhythm")
    }
    return scenes, characters, rhythm, _section_rows(sections, library, "continuity")


def _section_rows(
    sections: Mapping[str, Any], library: Mapping[str, Any], key: str
) -> list[dict[str, Any]]:
    return _rows(sections.get(key) or library.get(key))


def _completed_beats(
    scenes: list[dict[str, Any]],
    rhythm: Mapping[str, dict[str, Any]],
    formal_scene_ids: list[str],
    units: list[dict[str, Any]],
    drafts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    scene_by_id = {str(item.get("id") or ""): item for item in scenes}
    latest_scene_id = formal_scene_ids[-1] if formal_scene_ids else ""
    prose_tail = _latest_formal_prose_tail(drafts, latest_scene_id)
    completed = [
        _completed_beat(
            scene_by_id[scene_id],
            rhythm.get(scene_id, {}),
            actual_prose_tail=prose_tail if scene_id == latest_scene_id else "",
        )
        for scene_id in formal_scene_ids
        if scene_id in scene_by_id
    ]
    return completed or [
        {
            "scene_id": str(item.get("scene_id") or ""),
            "title": str(item.get("title") or "未命名正文"),
            "chapter_id": str(item.get("chapter_id") or ""),
        }
        for item in units[:8]
    ]


def _formal_units(
    reader: Mapping[str, Any], units: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "count": int(reader.get("unit_count") or len(units)),
        "chinese_content_chars": int(reader.get("total_chinese_content_chars") or 0),
        "titles": [str(item.get("title") or "未命名正文") for item in units[:12]],
    }


def _open_threads(continuity: list[dict[str, Any]]) -> list[dict[str, str]]:
    closed = {"closed", "resolved", "paid", "complete", "completed", "recorded", "committed", "applied"}
    return [
        {
            "title": str(item.get("title") or "未命名线索"),
            "kind": str(item.get("subtitle") or "连续性事项"),
            "status": str(item.get("status") or "open"),
        }
        for item in continuity
        if str(item.get("status") or "open").casefold() not in closed
    ][:8]


def _recent_changes(continuity: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "summary": str(item.get("title") or "未命名变化"),
            "kind": str(item.get("subtitle") or "连续性变化"),
            "status": str(item.get("status") or "recorded"),
        }
        for item in continuity
        if str(item.get("status") or "").casefold() in {"recorded", "committed", "applied", "needs_identity_resolution"}
    ][-8:]


def _next_scene(
    scenes: list[dict[str, Any]], formal_scene_ids: list[str]
) -> dict[str, Any] | None:
    return next(
        (
            _planned_scene(item)
            for item in scenes
            if str(item.get("id") or "") not in formal_scene_ids
        ),
        None,
    )


def _continuity_status(
    continuity: list[dict[str, Any]],
    open_threads: list[dict[str, str]],
    reader: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "state": "tracked" if continuity else "not_recorded",
        "record_count": len(continuity),
        "open_count": len(open_threads),
        "reader_warning_count": len(_rows(reader.get("warnings"))),
    }


def _formal_scene_ids(units: list[dict[str, Any]]) -> list[str]:
    result: list[str] = []
    for unit in units:
        values = unit.get("coverage") if isinstance(unit.get("coverage"), list) else []
        scene_id = str(unit.get("scene_id") or "").strip()
        for value in [*values, scene_id]:
            normalized = str(value or "").strip()
            if normalized and normalized not in result:
                result.append(normalized)
    return result


def _completed_beat(
    scene: Mapping[str, Any],
    rhythm: Mapping[str, Any],
    *,
    actual_prose_tail: str = "",
) -> dict[str, Any]:
    scene_id = str(scene.get("id") or "")
    planned_story_move = str(rhythm.get("excerpt") or scene.get("excerpt") or "")
    result = {
        "scene_id": scene_id,
        "title": str(scene.get("title") or scene_id),
        "chapter_id": str(scene.get("subtitle") or ""),
        "participants": [str(item) for item in _values(scene.get("participants"))[:8]],
    }
    if actual_prose_tail:
        result["planned_story_move"] = planned_story_move
        result["actual_prose_tail"] = actual_prose_tail
    else:
        result["story_move"] = planned_story_move
    return result


def _latest_formal_prose_tail(drafts: list[dict[str, Any]], scene_id: str) -> str:
    if not scene_id:
        return ""
    for item in drafts:
        if str(item.get("status") or "") != "promoted":
            continue
        path = str(item.get("path") or "").replace("\\", "/")
        item_id = str(item.get("id") or "")
        if not (
            path.endswith(f"/drafts/scenes/{scene_id}.md")
            or path == f"drafts/scenes/{scene_id}.md"
            or item_id == f"promoted__{scene_id}"
        ):
            continue
        body = str(item.get("body") or "").strip()
        if body:
            return body[-800:]
    return ""


def _planned_scene(scene: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "scene_id": str(scene.get("id") or ""),
        "title": str(scene.get("title") or "未命名场景"),
        "chapter_id": str(scene.get("subtitle") or ""),
        "objective": str(scene.get("excerpt") or ""),
        "participants": [str(item) for item in _values(scene.get("participants"))[:8]],
    }


def _main_characters(characters: list[dict[str, Any]]) -> list[dict[str, str]]:
    ordered = sorted(
        characters,
        key=lambda item: (str(item.get("importance") or "secondary") != "major"),
    )
    return [
        {
            "name": str(item.get("title") or "未命名人物"),
            "role": str(item.get("subtitle") or item.get("importance") or ""),
            "situation": str(item.get("excerpt") or "尚未记录人物处境"),
        }
        for item in ordered[:8]
    ]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _values(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


__all__ = ["build_story_brief"]
