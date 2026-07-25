"""Stable character references for the read-only living narrative field."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import re
from typing import Any


class CharacterReferenceResolution(str, Enum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class CharacterReference:
    reference_id: str
    node_id: str
    character_id: str
    display_name: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    resolution: CharacterReferenceResolution = CharacterReferenceResolution.UNRESOLVED
    matched_names: tuple[str, ...] = field(default_factory=tuple)
    candidate_character_ids: tuple[str, ...] = field(default_factory=tuple)
    scene_ids: tuple[str, ...] = field(default_factory=tuple)
    chapter_ids: tuple[str, ...] = field(default_factory=tuple)
    importance: str = "secondary"
    source_id: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "reference_id": self.reference_id,
            "node_id": self.node_id,
            "character_id": self.character_id,
            "display_name": self.display_name,
            "aliases": list(self.aliases),
            "resolution": self.resolution.value,
            "matched_names": list(self.matched_names),
            "candidate_character_ids": list(self.candidate_character_ids),
            "scene_ids": list(self.scene_ids),
            "chapter_ids": list(self.chapter_ids),
            "importance": self.importance,
            "source_id": self.source_id,
        }

    @classmethod
    def from_dict(cls, value: object) -> "CharacterReference":
        source = value if isinstance(value, dict) else {}
        resolution_value = str(source.get("resolution") or CharacterReferenceResolution.UNRESOLVED.value)
        try:
            resolution = CharacterReferenceResolution(resolution_value)
        except ValueError:
            resolution = CharacterReferenceResolution.UNRESOLVED
        return cls(
            reference_id=_text(source.get("reference_id")),
            node_id=_text(source.get("node_id")),
            character_id=_text(source.get("character_id")),
            display_name=_text(source.get("display_name")),
            aliases=_strings(source.get("aliases")),
            resolution=resolution,
            matched_names=_strings(source.get("matched_names")),
            candidate_character_ids=_strings(source.get("candidate_character_ids")),
            scene_ids=_strings(source.get("scene_ids")),
            chapter_ids=_strings(source.get("chapter_ids")),
            importance=_text(source.get("importance")) or "secondary",
            source_id=_text(source.get("source_id")),
        )


@dataclass
class _ReferenceAccumulator:
    reference_id: str
    node_id: str
    character_id: str
    display_name: str
    aliases: set[str]
    resolution: CharacterReferenceResolution
    candidate_character_ids: set[str]
    importance: str
    source_id: str
    matched_names: set[str] = field(default_factory=set)
    scene_ids: set[str] = field(default_factory=set)
    chapter_ids: set[str] = field(default_factory=set)

    def freeze(self) -> CharacterReference:
        return CharacterReference(
            reference_id=self.reference_id,
            node_id=self.node_id,
            character_id=self.character_id,
            display_name=self.display_name,
            aliases=tuple(sorted(self.aliases)),
            resolution=self.resolution,
            matched_names=tuple(sorted(self.matched_names)),
            candidate_character_ids=tuple(sorted(self.candidate_character_ids)),
            scene_ids=tuple(sorted(self.scene_ids, key=_natural_key)),
            chapter_ids=tuple(sorted(self.chapter_ids, key=_natural_key)),
            importance=self.importance,
            source_id=self.source_id,
        )


def build_character_references(library_payload: object) -> list[CharacterReference]:
    """Resolve canonical IDs, aliases and unresolved scene mentions deterministically."""

    characters, scenes = _library_items(library_payload)
    records = {_text(item.get("id")): item for item in characters if _text(item.get("id"))}
    alias_index = _alias_index(records)
    accumulators = {
        character_id: _resolved_accumulator(character_id, item)
        for character_id, item in records.items()
    }
    for scene in scenes:
        _accumulate_scene_mentions(scene, records, alias_index, accumulators)
    return [
        accumulator.freeze()
        for accumulator in sorted(
            accumulators.values(),
            key=lambda item: (
                item.resolution is not CharacterReferenceResolution.RESOLVED,
                _natural_key(item.display_name),
                item.reference_id,
            ),
        )
    ]


def _library_items(library_payload: object) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sections = library_payload.get("sections") if isinstance(library_payload, dict) else {}
    sections = sections if isinstance(sections, dict) else {}
    characters = [item for item in sections.get("characters", []) if isinstance(item, dict)]
    scenes = [item for item in sections.get("scenes", []) if isinstance(item, dict)]
    return characters, scenes


def _accumulate_scene_mentions(
    scene: dict[str, Any],
    records: dict[str, dict[str, Any]],
    alias_index: dict[str, set[str]],
    accumulators: dict[str, _ReferenceAccumulator],
) -> None:
    scene_id = _text(scene.get("id"))
    chapter_id = _scene_chapter(scene)
    explicit_refs = _list_values(scene.get("participant_refs"))
    mentions = _list_values(scene.get("participants")) or _split_participants(_fact(scene, "参与者"))
    for mention in [*explicit_refs, *mentions]:
        candidates = _candidate_ids(mention, records, alias_index)
        accumulator = _select_accumulator(mention, candidates, accumulators)
        accumulator.matched_names.add(mention)
        if scene_id:
            accumulator.scene_ids.add(scene_id)
        if chapter_id:
            accumulator.chapter_ids.add(chapter_id)


def augment_character_graph(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    references: list[CharacterReference],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Add stable character nodes and visible participation edges without mutation."""

    result_nodes = list(nodes)
    result_edges = list(edges)
    node_ids = {str(node.get("node_id") or "") for node in result_nodes}
    visible_scenes = {node_id for node_id in node_ids if node_id.startswith("scene:")}
    visible_chapters = {node_id for node_id in node_ids if node_id.startswith("chapter:")}
    for order, reference in enumerate(references, start=len(result_nodes)):
        if reference.node_id not in node_ids:
            result_nodes.append(_reference_node(reference, order))
            node_ids.add(reference.node_id)
        targets = _reference_targets(reference, visible_scenes, visible_chapters)
        for target in targets:
            result_edges.append(
                {
                    "edge_id": f"participates:{reference.node_id}>{target}",
                    "source": reference.node_id,
                    "target": target,
                    "type": "participates",
                    "label": _participation_label(reference),
                }
            )
    return _dedupe_nodes(result_nodes), _dedupe_edges(result_edges)


def _resolved_accumulator(character_id: str, item: dict[str, Any]) -> _ReferenceAccumulator:
    display_name = _text(item.get("title")) or character_id
    aliases = set(_list_values(item.get("aliases")))
    aliases.add(display_name)
    return _ReferenceAccumulator(
        reference_id=character_id,
        node_id=f"character:{character_id}",
        character_id=character_id,
        display_name=display_name,
        aliases=aliases,
        resolution=CharacterReferenceResolution.RESOLVED,
        candidate_character_ids={character_id},
        importance=_text(item.get("importance") or item.get("status")) or "secondary",
        source_id=_text(item.get("path") or character_id),
    )


def _alias_index(records: dict[str, dict[str, Any]]) -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for character_id, item in records.items():
        names = {character_id, _text(item.get("title")), *_list_values(item.get("aliases"))}
        for name in names:
            normalized = _normalize_name(name)
            if normalized:
                index.setdefault(normalized, set()).add(character_id)
    return index


def _candidate_ids(
    mention: str,
    records: dict[str, dict[str, Any]],
    alias_index: dict[str, set[str]],
) -> tuple[str, ...]:
    if mention in records:
        return (mention,)
    return tuple(sorted(alias_index.get(_normalize_name(mention), set())))


def _select_accumulator(
    mention: str,
    candidates: tuple[str, ...],
    accumulators: dict[str, _ReferenceAccumulator],
) -> _ReferenceAccumulator:
    if len(candidates) == 1:
        return accumulators[candidates[0]]
    resolution = (
        CharacterReferenceResolution.AMBIGUOUS
        if candidates
        else CharacterReferenceResolution.UNRESOLVED
    )
    key = f"{resolution.value}:{_stable_id(mention, candidates)}"
    if key not in accumulators:
        accumulators[key] = _ReferenceAccumulator(
            reference_id=key,
            node_id=f"character:{key}",
            character_id="",
            display_name=mention,
            aliases=set(),
            resolution=resolution,
            candidate_character_ids=set(candidates),
            importance="unresolved",
            source_id="",
        )
    return accumulators[key]


def _reference_node(reference: CharacterReference, order: int) -> dict[str, Any]:
    subtitle = {
        CharacterReferenceResolution.RESOLVED: "正式人物",
        CharacterReferenceResolution.AMBIGUOUS: "人物名称存在歧义",
        CharacterReferenceResolution.UNRESOLVED: "尚未解析为正式人物",
    }[reference.resolution]
    return {
        "node_id": reference.node_id,
        "type": "character",
        "label": reference.display_name,
        "subtitle": subtitle,
        "status": "memory" if reference.resolution is CharacterReferenceResolution.RESOLVED else "blocked",
        "source_type": "character-reference",
        "source_id": reference.source_id or reference.reference_id,
        "navigate": "library",
        "metrics": {
            "character_id": reference.character_id,
            "resolution": reference.resolution.value,
            "aliases": list(reference.aliases),
            "candidate_character_ids": list(reference.candidate_character_ids),
            "scene_ids": list(reference.scene_ids),
            "chapter_ids": list(reference.chapter_ids),
        },
        "order": order,
    }


def _reference_targets(
    reference: CharacterReference,
    visible_scenes: set[str],
    visible_chapters: set[str],
) -> list[str]:
    scene_targets = [
        f"scene:{scene_id}"
        for scene_id in reference.scene_ids
        if f"scene:{scene_id}" in visible_scenes
    ]
    if scene_targets:
        return scene_targets
    return [
        f"chapter:{chapter_id}"
        for chapter_id in reference.chapter_ids
        if f"chapter:{chapter_id}" in visible_chapters
    ]


def _participation_label(reference: CharacterReference) -> str:
    if reference.resolution is CharacterReferenceResolution.RESOLVED:
        return "人物进入场景"
    if reference.resolution is CharacterReferenceResolution.AMBIGUOUS:
        return "待消歧人物提及"
    return "待解析人物提及"


def _scene_chapter(scene: dict[str, Any]) -> str:
    return _fact(scene, "章节") or _text(scene.get("subtitle"))


def _fact(item: dict[str, Any], label: str) -> str:
    facts = item.get("facts") if isinstance(item.get("facts"), list) else []
    for fact in facts:
        if isinstance(fact, dict) and _text(fact.get("label")) == label:
            return _text(fact.get("value"))
    return ""


def _split_participants(value: str) -> list[str]:
    normalized = value.replace("，", ",").replace("、", ",")
    return [item.strip() for item in normalized.split(",") if item.strip() and item.strip() != "未填写"]


def _list_values(value: object) -> list[str]:
    return [_text(item) for item in value] if isinstance(value, list) else []


def _strings(value: object) -> tuple[str, ...]:
    return tuple(item for item in _list_values(value) if item)


def _text(value: object) -> str:
    return str(value or "").strip()


def _normalize_name(value: str) -> str:
    return "".join(value.split()).casefold()


def _stable_id(mention: str, candidates: tuple[str, ...]) -> str:
    value = "|".join([_normalize_name(mention), *candidates])
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _natural_key(value: str) -> tuple[object, ...]:
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in re.split(r"(\d+)", value)
        if part
    )


def _dedupe_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for node in nodes:
        result.setdefault(str(node.get("node_id") or ""), node)
    return [node for node_id, node in result.items() if node_id]


def _dedupe_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for edge in edges:
        result.setdefault(str(edge.get("edge_id") or ""), edge)
    return [edge for edge_id, edge in result.items() if edge_id]
