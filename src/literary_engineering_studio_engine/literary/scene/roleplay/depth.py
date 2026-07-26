"""Roleplay-depth policy that changes scope without weakening evidence."""

from __future__ import annotations

from .models import CharacterCard
from ..context.packet import scene_character_refs


ROLEPLAY_DEPTHS = frozenset({"light", "targeted", "full"})


def normalize_roleplay_depth(value: str) -> str:
    depth = str(value or "targeted").strip().lower()
    if depth not in ROLEPLAY_DEPTHS:
        raise ValueError(f"unsupported roleplay depth: {value}")
    return depth


def select_cards_for_depth(
    cards: list[CharacterCard],
    scene_text: str,
    roleplay_depth: str,
) -> list[CharacterCard]:
    depth = normalize_roleplay_depth(roleplay_depth)
    references = {item.casefold() for item in scene_character_refs(scene_text)}
    if not references:
        return cards
    direct = [card for card in cards if _card_matches(card, references)]
    if depth == "light":
        return direct or cards
    if depth == "targeted":
        selected = {card.file: card for card in (*direct, *_major_cards(cards))}
        return list(selected.values()) or cards
    return cards


def roleplay_depth_contract(roleplay_depth: str) -> str:
    depth = normalize_roleplay_depth(roleplay_depth)
    if depth == "light":
        return (
            "light：只分析本场直接参与者与即时因果，但 character_actions、"
            "world_consequences、branch_pressures、canon_risks 和 writeback_candidates "
            "仍必须形成非占位证据；不得把 light 理解为跳过 RP。"
        )
    if depth == "full":
        return (
            "full：覆盖所有正式人物中与本场事实相关的压力，加入反事实选择、关系代价、"
            "世界后果与 Canon 冲突复核；不得只扩写同一结论。"
        )
    return (
        "targeted：完整分析直接参与者与主要角色，明确被拒绝的便利行动、下一场代价、"
        "世界后果、分支压力和 Canon 风险。"
    )


def _card_matches(card: CharacterCard, references: set[str]) -> bool:
    identities = {
        card.character_id.casefold(),
        card.name.casefold(),
        card.file.stem.casefold(),
    }
    return bool(references.intersection(identities))


def _major_cards(cards: list[CharacterCard]) -> list[CharacterCard]:
    tokens = ("主角", "主要", "核心", "protagonist", "major", "main", "core")
    return [
        card
        for card in cards
        if any(token in card.role.casefold() for token in tokens)
    ]
