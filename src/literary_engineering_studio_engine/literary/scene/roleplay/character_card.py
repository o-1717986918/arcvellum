"""Creator-authored actor system cards, with explicit template substitution."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping


ACTOR_CARD_SCHEMA = "arcvellum/actor-character-card/v1"
ACTOR_CARD_SECTIONS = (
    "PERSONA_LOAD", "CORE_IDENTITY", "PERSONALITY_LAYERS", "PRIVATE_BEHAVIOR_MODES",
    "INTERACTION_LIBRARY", "SUMMARY_PRIVATE", "SELF_IDENTITY", "SELF_CLAIM_RULES",
    "PERSONALITY_CORE", "PERSONALITY_PUBLIC", "PERSONALITY_PRIVATE",
    "PERSONALITY_CONTRADICTION", "PERSONALITY_SUMMARY", "SELF_CLAIM_EXAMPLES",
    "FOOD_PREFERENCE", "REAL_SELF_BEHAVIOR",
)
_TOKEN = re.compile(r"\{\{([A-Z_]+)\}\}")


@dataclass(frozen=True)
class ActorCharacterCardV1:
    target: str
    sections: tuple[tuple[str, str], ...]
    source_refs: tuple[str, ...]
    design_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"schema": ACTOR_CARD_SCHEMA, "target": self.target,
                "sections": dict(self.sections), "source_refs": list(self.source_refs),
                "design_notes": self.design_notes}


def parse_actor_character_card(payload: Any, target: str) -> ActorCharacterCardV1:
    if not isinstance(target, str) or not target.strip() or len(target) > 120:
        raise ValueError("character_card requires a bounded nonempty target")
    if not isinstance(payload, Mapping) or payload.get("schema") != ACTOR_CARD_SCHEMA:
        raise ValueError("character_card requires the actor-character-card/v1 schema")
    if payload.get("target") != target:
        raise ValueError("character_card target must match its actor request")
    sections = _parse_sections(payload.get("sections"))
    refs = _parse_source_refs(payload.get("source_refs"))
    notes = payload.get("design_notes", "")
    if not isinstance(notes, str) or len(notes) > 2000:
        raise ValueError("character_card design_notes exceeds its limit")
    return ActorCharacterCardV1(target, sections, refs, notes.strip())


def _parse_source_refs(refs: Any) -> tuple[str, ...]:
    if not isinstance(refs, list) or not 1 <= len(refs) <= 32:
        raise ValueError("character_card needs one to thirty-two source_refs")
    if any(not isinstance(ref, str) or not ref.strip() or len(ref) > 500 for ref in refs):
        raise ValueError("character_card source_refs must be bounded strings")
    return tuple(ref.strip() for ref in refs)


def _parse_sections(raw: Any) -> tuple[tuple[str, str], ...]:
    if not isinstance(raw, Mapping) or set(raw) != set(ACTOR_CARD_SECTIONS):
        raise ValueError("character_card needs exactly the sixteen named sections")
    sections = []
    for key in ACTOR_CARD_SECTIONS:
        value = raw[key]
        if not isinstance(value, str) or not value.strip() or len(value) > 3500:
            raise ValueError(f"character_card section {key} needs bounded nonempty text")
        if _TOKEN.search(value):
            raise ValueError(f"character_card section {key} still has unfilled placeholders")
        sections.append((key, value.strip()))
    if sum(len(value) for _, value in sections) > 12_000:
        raise ValueError("character_card exceeds its total context budget; shorten the card")
    return tuple(sections)


def render_actor_character_card(template: str, card: ActorCharacterCardV1) -> str:
    values = dict(card.sections)
    tokens = _TOKEN.findall(template)
    if len(tokens) != len(ACTOR_CARD_SECTIONS) or set(tokens) != set(ACTOR_CARD_SECTIONS):
        raise ValueError("actor system template must contain each card section token exactly once")
    return _TOKEN.sub(lambda match: values[match.group(1)], template)


__all__ = [
    "ACTOR_CARD_SCHEMA", "ACTOR_CARD_SECTIONS", "ActorCharacterCardV1",
    "parse_actor_character_card", "render_actor_character_card",
]
