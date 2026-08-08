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


def load_scene_facts(scene_path: Path) -> SceneFacts:
    """Load the shared literary facts from canonical or legacy scene YAML."""

    path = scene_path.resolve()
    try:
        payload = _YAML.load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"invalid scene YAML: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"scene YAML must be a mapping: {path}")

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
        ),
    )


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


__all__ = ["SceneFacts", "load_scene_facts"]
