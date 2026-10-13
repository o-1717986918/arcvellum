"""Creator-authored actor system cards, with explicit template substitution."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping


LEGACY_ACTOR_CARD_SCHEMA = "arcvellum/actor-character-card/v1"
LEGACY_ACTOR_CARD_SECTIONS = (
    "PERSONA_LOAD", "CORE_IDENTITY", "PERSONALITY_LAYERS", "PRIVATE_BEHAVIOR_MODES",
    "INTERACTION_LIBRARY", "SUMMARY_PRIVATE", "SELF_IDENTITY", "SELF_CLAIM_RULES",
    "PERSONALITY_CORE", "PERSONALITY_PUBLIC", "PERSONALITY_PRIVATE",
    "PERSONALITY_CONTRADICTION", "PERSONALITY_SUMMARY", "SELF_CLAIM_EXAMPLES",
    "FOOD_PREFERENCE", "REAL_SELF_BEHAVIOR",
)
ACTOR_CARD_SCHEMA = "arcvellum/actor-character-card/v2"
ACTOR_CARD_SECTIONS = tuple(key for key in LEGACY_ACTOR_CARD_SECTIONS if key not in {
    "PERSONALITY_CORE", "PERSONALITY_PUBLIC", "PERSONALITY_PRIVATE",
    "PERSONALITY_CONTRADICTION", "PERSONALITY_SUMMARY",
})
_TOKEN = re.compile(r"\{\{([A-Z_]+)\}\}")


@dataclass(frozen=True)
class ActorCharacterCardV1:
    target: str
    sections: tuple[tuple[str, str], ...]
    source_refs: tuple[str, ...]
    design_notes: str = ""
    schema: str = LEGACY_ACTOR_CARD_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {"schema": self.schema, "target": self.target,
                "sections": dict(self.sections), "source_refs": list(self.source_refs),
                "design_notes": self.design_notes}


@dataclass(frozen=True)
class ActorCharacterCardV2(ActorCharacterCardV1):
    schema: str = ACTOR_CARD_SCHEMA


def actor_card_section_names(schema: str) -> tuple[str, ...]:
    if schema == ACTOR_CARD_SCHEMA:
        return ACTOR_CARD_SECTIONS
    if schema == LEGACY_ACTOR_CARD_SCHEMA:
        return LEGACY_ACTOR_CARD_SECTIONS
    raise ValueError("character_card requires a supported actor-character-card schema")


def actor_card_schema_for_template(template: str) -> str:
    tokens = _TOKEN.findall(template)
    for schema in (ACTOR_CARD_SCHEMA, LEGACY_ACTOR_CARD_SCHEMA):
        names = actor_card_section_names(schema)
        if len(tokens) == len(names) and set(tokens) == set(names):
            return schema
    raise ValueError("actor system template must contain each card section token exactly once")


def parse_actor_character_card(payload: Any, target: str) -> ActorCharacterCardV1:
    if not isinstance(target, str) or not target.strip() or len(target) > 120:
        raise ValueError("character_card requires a bounded nonempty target")
    if not isinstance(payload, Mapping):
        raise ValueError("character_card requires a supported actor-character-card schema")
    schema = payload.get("schema")
    names = actor_card_section_names(schema)
    if payload.get("target") != target:
        raise ValueError("character_card target must match its actor request")
    sections = _parse_sections(payload.get("sections"), names)
    refs = _parse_source_refs(payload.get("source_refs"))
    notes = payload.get("design_notes", "")
    if not isinstance(notes, str) or len(notes) > 2000:
        raise ValueError("character_card design_notes exceeds its limit")
    card_type = ActorCharacterCardV2 if schema == ACTOR_CARD_SCHEMA else ActorCharacterCardV1
    return card_type(target, sections, refs, notes.strip())


def _parse_source_refs(refs: Any) -> tuple[str, ...]:
    if not isinstance(refs, list) or not 1 <= len(refs) <= 32:
        raise ValueError("character_card needs one to thirty-two source_refs")
    if any(not isinstance(ref, str) or not ref.strip() or len(ref) > 500 for ref in refs):
        raise ValueError("character_card source_refs must be bounded strings")
    return tuple(ref.strip() for ref in refs)


def _parse_sections(raw: Any, names: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    if not isinstance(raw, Mapping) or set(raw) != set(names):
        raise ValueError(f"character_card needs exactly its {len(names)} named sections")
    sections = []
    for key in names:
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
    schema = actor_card_schema_for_template(template)
    if schema == ACTOR_CARD_SCHEMA and card.schema == LEGACY_ACTOR_CARD_SCHEMA:
        # Explicit legacy-card selection preserves all five historic sections.
        extra = "\n\n".join("【" + key + "】\n{{" + key + "}}"
            for key in LEGACY_ACTOR_CARD_SECTIONS if key not in ACTOR_CARD_SECTIONS)
        template = template.replace("【SELF_CLAIM_EXAMPLES】", extra + "\n\n【SELF_CLAIM_EXAMPLES】")
    if set(_TOKEN.findall(template)) != set(values):
        raise ValueError("actor card version does not match the frozen system template")
    return _TOKEN.sub(lambda match: values[match.group(1)], template)


__all__ = [
    "ACTOR_CARD_SCHEMA", "ACTOR_CARD_SECTIONS", "ActorCharacterCardV1", "ActorCharacterCardV2",
    "LEGACY_ACTOR_CARD_SCHEMA", "LEGACY_ACTOR_CARD_SECTIONS",
    "actor_card_section_names", "actor_card_schema_for_template",
    "parse_actor_character_card", "render_actor_character_card",
]
