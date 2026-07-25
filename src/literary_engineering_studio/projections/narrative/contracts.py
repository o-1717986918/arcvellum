"""Stable contracts owned by the narrative projection domain."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class NarrativeFocusLevel(str, Enum):
    BOOK = "book"
    CHAPTER = "chapter"
    SCENE = "scene"
    CHARACTER = "character"

    @classmethod
    def parse(cls, value: object) -> "NarrativeFocusLevel":
        try:
            return cls(str(value or "").strip().lower())
        except ValueError:
            return cls.BOOK


@dataclass(frozen=True)
class NarrativeFocusScope:
    level: NarrativeFocusLevel
    focus_id: str
    chapter_ids: tuple[str, ...] = ()
    scene_ids: tuple[str, ...] = ()
    character_ids: tuple[str, ...] = ()
    anchor_node_ids: tuple[str, ...] = ()
    context_node_ids: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["level"] = self.level.value
        for key in (
            "chapter_ids",
            "scene_ids",
            "character_ids",
            "anchor_node_ids",
            "context_node_ids",
        ):
            payload[key] = list(payload[key])
        return payload

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "NarrativeFocusScope":
        return cls(
            level=NarrativeFocusLevel.parse(value.get("level")),
            focus_id=str(value.get("focus_id") or value.get("focus") or "").strip(),
            chapter_ids=_strings(value.get("chapter_ids")),
            scene_ids=_strings(value.get("scene_ids")),
            character_ids=_strings(value.get("character_ids")),
            anchor_node_ids=_strings(value.get("anchor_node_ids")),
            context_node_ids=_strings(value.get("context_node_ids")),
        )


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())
