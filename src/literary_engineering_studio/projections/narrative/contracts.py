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


class RelationFamily(str, Enum):
    NARRATIVE_SPINE = "narrative-spine"
    CHAPTER_SCENE = "chapter-scene"
    SCENE_BRANCH = "scene-branch"
    SCENE_REVIEW = "scene-review"
    SCENE_READER_QUESTION = "scene-reader-question"
    SCENE_PROMISE_PAYOFF = "scene-promise-payoff"
    CHARACTER_SCENE = "character-scene"
    EVIDENCE_CLAIM = "evidence-claim"
    CANON_STATE_IMPACT = "canon-state-impact"
    WORKFLOW_CONTROL = "workflow-control"
    CONTEXT_ASSOCIATION = "context-association"


class RelationLodMode(str, Enum):
    AGGREGATE = "aggregate"
    INDIVIDUAL = "individual"
    EMPHASIZED = "emphasized"


class RelationFocusState(str, Enum):
    GLOBAL = "global"
    INTERNAL = "internal"
    ATTACHED = "attached"
    CONTEXT = "context"


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


@dataclass(frozen=True)
class RelationVisibilityProfile:
    family: RelationFamily
    label: str
    edge_count: int
    focused_edge_count: int
    far_mode: RelationLodMode
    mid_mode: RelationLodMode
    near_mode: RelationLodMode
    aggregate_anchor: str
    base_weight: float
    focus_weight: float

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("family", "far_mode", "mid_mode", "near_mode"):
            payload[key] = payload[key].value
        return payload

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RelationVisibilityProfile":
        return cls(
            family=_enum(RelationFamily, value.get("family"), RelationFamily.CONTEXT_ASSOCIATION),
            label=str(value.get("label") or "").strip(),
            edge_count=max(0, int(value.get("edge_count") or 0)),
            focused_edge_count=max(0, int(value.get("focused_edge_count") or 0)),
            far_mode=_enum(RelationLodMode, value.get("far_mode"), RelationLodMode.AGGREGATE),
            mid_mode=_enum(RelationLodMode, value.get("mid_mode"), RelationLodMode.INDIVIDUAL),
            near_mode=_enum(RelationLodMode, value.get("near_mode"), RelationLodMode.EMPHASIZED),
            aggregate_anchor=str(value.get("aggregate_anchor") or "chapter-centroid").strip(),
            base_weight=max(0.0, float(value.get("base_weight") or 0.0)),
            focus_weight=max(0.0, float(value.get("focus_weight") or 0.0)),
        )


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _enum(enum_type: type[Enum], value: object, default: Any) -> Any:
    try:
        return enum_type(str(value or "").strip())
    except ValueError:
        return default
