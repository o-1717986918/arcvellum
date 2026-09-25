"""Project-level actor initialization tags for already established characters."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping

from .lab import _load_characters


SCHEMA = "arcvellum/actor-personas/v1"
SECTIONS = ("PERSONA_LOAD", "PERSONALITY_CORE", "PERSONALITY_PUBLIC", "LANGUAGE_STYLE", "LITERATURE_STYLE")
DEFAULT_LANGUAGE_STYLE = ("ANTI_PLAIN", "POLISHED", "ANTI_SHORT_SENTENCES")
_TAG = re.compile(r"[A-Z_]+\Z")


def list_actor_personas(root: Path) -> dict[str, Any]:
    """List editable sections without granting arbitrary project-file access."""

    saved = _read(root)
    return {
        "schema": SCHEMA,
        "default_language_style": list(DEFAULT_LANGUAGE_STYLE),
        "characters": [
            {
                "character_id": card.character_id,
                "name": card.name,
                "configured": card.character_id in saved,
                "sections": saved.get(card.character_id),
            }
            for card in _load_characters(root)
        ],
    }


def save_actor_persona(root: Path, character_id: str, sections: Mapping[str, Any]) -> dict[str, Any]:
    """Replace the editable initialization sections for one existing character."""

    cards = {card.character_id: card for card in _load_characters(root)}
    if character_id not in cards:
        raise ValueError("actor persona requires an existing character_id")
    normalized = _normalize(sections)
    saved = _read(root)
    saved[character_id] = normalized
    path = _path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"schema": SCHEMA, "profiles": saved}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return {"schema": SCHEMA, "character_id": character_id, "name": cards[character_id].name, "sections": normalized}


def actor_personas_for_participants(root: Path, participants: list[str]) -> dict[str, str]:
    """Use saved initialization tags only for a unique matching scene participant."""

    saved = _read(root)
    if not saved:
        return {}
    cards = _load_characters(root)
    result: dict[str, str] = {}
    for participant in participants:
        tail = participant.rsplit("/", 1)[-1]
        matches = [card for card in cards if participant in {card.character_id, card.name, card.file.stem}
                   or tail in {card.character_id, card.file.stem}]
        if len(matches) == 1 and matches[0].character_id in saved:
            result[participant] = render_actor_persona(saved[matches[0].character_id])
    return result


def render_actor_persona(sections: Mapping[str, Any]) -> str:
    normalized = _normalize(sections)
    return "\n\n".join(
        f"{header}\n" + "\n".join(normalized[key])
        for key, header in (
            ("PERSONA_LOAD", "【PERSONA_LOAD】"),
            ("PERSONALITY_CORE", "【PERSONALITY_CORE】"),
            ("PERSONALITY_PUBLIC", "【PERSONALITY_PUBLIC】"),
            ("LANGUAGE_STYLE", "[LANGUAGE_STYLE]"),
            ("LITERATURE_STYLE", "[LITERATURE_STYLE]"),
        )
    )


def _normalize(sections: Mapping[str, Any]) -> dict[str, list[str]]:
    if not isinstance(sections, Mapping) or not set(SECTIONS[:-1]).issubset(sections) or set(sections) - set(SECTIONS):
        raise ValueError("actor persona requires the four core sections")
    result: dict[str, list[str]] = {}
    for key in SECTIONS:
        values = sections.get(key, [])
        if not isinstance(values, list) or len(values) > 16:
            raise ValueError(f"actor persona {key} must be a list of at most 16 tags")
        tags = [str(item).strip() for item in values]
        if any(not _TAG.fullmatch(tag) or len(tag) > 80 for tag in tags):
            raise ValueError(f"actor persona {key} tags must use uppercase English letters and underscores")
        if len(set(tags)) != len(tags):
            raise ValueError(f"actor persona {key} contains duplicate tags")
        result[key] = tags
    if not result["PERSONA_LOAD"]:
        raise ValueError("actor persona PERSONA_LOAD cannot be empty")
    return result


def _path(root: Path) -> Path:
    return root / "characters" / "_actor_personas.json"


def _read(root: Path) -> dict[str, dict[str, list[str]]]:
    path = _path(root)
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA or not isinstance(payload.get("profiles"), dict):
        raise ValueError("actor persona store has an invalid schema")
    return {str(key): _normalize(value) for key, value in payload["profiles"].items()}


__all__ = ["DEFAULT_LANGUAGE_STYLE", "actor_personas_for_participants", "list_actor_personas", "render_actor_persona", "save_actor_persona"]
