"""Canonical scene facts shared by branching, composition, and review."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML


_YAML = YAML(typ="safe")
_MISSING = object()


@dataclass(frozen=True)
class SceneFacts:
    scene_id: str
    chapter_id: str
    location: str
    participants: list[str]
    canon_refs: list[str]
    active_foreshadowing: list[str]
    scene_goal: str
    external_conflict: str
    internal_conflict: str
    style_constraints: list[str]
    next_hooks: list[str]
    viewpoint: str = ""
    incoming_pressure: str = ""
    status: str = ""
    volume_id: str = ""
    chapter_obligation_id: str = ""
    title: str = ""
    word_count_target: int = 0
    word_count_min: int = 0
    word_count_max: int = 0
    story_time: str = ""
    timeline_order: int | None = None
    spatial_time_gap_before: float = 0.0


def load_scene_facts(scene_path: Path) -> SceneFacts:
    """Load shared facts, preserving the legacy empty projection for absent files."""

    path = scene_path.resolve()
    payload = load_scene_mapping(path) if path.is_file() else {}

    return SceneFacts(
        scene_id=_text(payload.get("scene_id")) or path.stem or "scene",
        chapter_id=_text(payload.get("chapter_id")),
        location=_text(payload.get("location")),
        participants=_text_list(payload.get("participants")),
        canon_refs=_text_list(
            _canonical_or_legacy(payload, ("input_state", "canon_refs"), "canon_refs")
        ),
        active_foreshadowing=_text_list(
            _canonical_or_legacy(
                payload,
                ("input_state", "active_foreshadowing"),
                "active_foreshadowing",
            )
        ),
        scene_goal=_text(payload.get("scene_goal")),
        external_conflict=_text(
            _canonical_or_legacy(payload, ("conflict", "external"), "external")
        ),
        internal_conflict=_text(
            _canonical_or_legacy(payload, ("conflict", "internal"), "internal")
        ),
        style_constraints=_text_list(payload.get("style_constraints")),
        next_hooks=_text_list(
            _canonical_or_legacy(payload, ("output_state", "next_hooks"), "next_hooks")
        ) or _text_list(_path_value(payload, ("scene_bridge", "outgoing_hook"))),
        viewpoint=_text(payload.get("viewpoint") or payload.get("pov")),
        incoming_pressure=_text(
            _canonical_or_legacy(
                payload,
                ("scene_bridge", "incoming_pressure"),
                "incoming_pressure",
            )
        ),
        status=_text(payload.get("status")),
        volume_id=_text(payload.get("volume_id") or payload.get("volume")),
        chapter_obligation_id=_text(payload.get("chapter_obligation_id")),
        title=_text(payload.get("title")),
        word_count_target=_non_negative_int(payload.get("word_count_target")),
        word_count_min=_non_negative_int(payload.get("word_count_min")),
        word_count_max=_non_negative_int(payload.get("word_count_max")),
        story_time=_text(
            _canonical_or_legacy(payload, ("time", "story_time"), "story_time")
        ),
        timeline_order=_optional_int(
            _canonical_or_legacy(
                payload,
                ("time", "timeline_order"),
                "timeline_order",
            )
        ),
        spatial_time_gap_before=_non_negative_float(
            payload.get("spatial_time_gap_before")
        ),
    )


def load_scene_mapping(scene_path: Path) -> dict[str, Any]:
    """Decode one scene document through the canonical YAML implementation."""

    path = scene_path.resolve()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"unable to read scene YAML: {path}") from exc
    return parse_scene_mapping(text, source=path)


def parse_scene_mapping(text: str, *, source: Path | str = "<scene>") -> dict[str, Any]:
    """Decode in-memory scene YAML for callers that already own the source text."""

    try:
        payload = _YAML.load(text)
    except Exception as exc:
        raise ValueError(f"invalid scene YAML: {source}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"scene YAML must be a mapping: {source}")
    return dict(payload)


def _canonical_or_legacy(
    payload: dict[str, Any],
    canonical_path: tuple[str, ...],
    legacy_key: str,
) -> Any:
    canonical = _path_value(payload, canonical_path)
    if canonical is not _MISSING:
        return canonical
    return payload.get(legacy_key)


def _path_value(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return _MISSING
        current = current[key]
    return current


def _text(value: Any) -> str:
    if value is None or isinstance(value, (dict, list, tuple, set)):
        return ""
    return str(value).strip()


def _text_list(value: Any) -> list[str]:
    values = value if isinstance(value, (list, tuple)) else [value]
    return [text for item in values if (text := _text(item))]


def _optional_int(value: Any) -> int | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        return int(str(value).replace(",", "").replace("_", "").strip())
    except (TypeError, ValueError):
        return None


def _non_negative_int(value: Any) -> int:
    parsed = _optional_int(value)
    return max(0, parsed) if parsed is not None else 0


def _non_negative_float(value: Any) -> float:
    if value in (None, "") or isinstance(value, bool):
        return 0.0
    try:
        return max(0.0, float(str(value).replace(",", "").replace("_", "").strip()))
    except (TypeError, ValueError):
        return 0.0


__all__ = [
    "SceneFacts",
    "load_scene_facts",
    "load_scene_mapping",
    "parse_scene_mapping",
]
