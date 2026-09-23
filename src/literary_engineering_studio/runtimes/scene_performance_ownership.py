"""Narrow quotation provenance check for first-level scene performers."""

from __future__ import annotations

import json
import re
from typing import Any, Callable


_QUOTED = re.compile(r"[“「]([^”」]+)[”」]")
_LETTERS = re.compile(r"[^\u4e00-\u9fffA-Za-z0-9]+")
_DIALOGUE_TAG = re.compile(r"(?:说|问|答|道|喊|叫|开口|应声|继续)[，,:：]?$|[：:]$")


def unlicensed_scene_dialogue(prose: str, materials: str) -> list[str]:
    """Find quoted text absent from every first-level actor's spoken material.

    This intentionally does not judge prose quality or infer visible-action semantics.
    """

    if not materials:
        return []
    try:
        packet = json.loads(materials.split("\n", 1)[1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise ValueError("first-level performance material block is malformed") from exc
    entries = _actor_entries(packet)
    if not entries:
        raise ValueError("first-level performance material block has no actor entries")
    spoken = [_normalize(entry.get("spoken", "")) for entry in entries]
    missing = []
    for match in _QUOTED.finditer(prose):
        paragraph_start = prose.rfind("\n", 0, match.start()) + 1
        prefix = prose[paragraph_start:match.start()].strip()
        if prefix and not _DIALOGUE_TAG.search(prefix):
            continue
        quote = match.group(1).strip()
        normalized = _normalize(quote)
        if normalized and not any(normalized in source for source in spoken):
            missing.append(quote)
    return list(dict.fromkeys(missing))


def repair_actor_dialogue(
    candidate: Any, materials: str, revise: Callable[[Any, list[str]], Any],
) -> Any:
    for _ in range(2):
        missing = unlicensed_scene_dialogue(candidate.prose, materials)
        if not missing:
            return candidate
        candidate = revise(candidate, missing)
    if unlicensed_scene_dialogue(candidate.prose, materials):
        raise RuntimeError("scene writer added dialogue absent from first-level actor material after two repairs")
    return candidate


def _actor_entries(packet: Any) -> list[dict[str, Any]]:
    if not isinstance(packet, dict):
        return []
    if isinstance(packet.get("actor_entries"), list):
        return [item for item in packet["actor_entries"] if isinstance(item, dict)]
    groups = packet.get("actor_candidates")
    if not isinstance(groups, list):
        return []
    return [entry for group in groups if isinstance(group, dict)
            for entry in group.get("entries", []) if isinstance(entry, dict)]


def _normalize(text: Any) -> str:
    return _LETTERS.sub("", text) if isinstance(text, str) else ""


__all__ = ["repair_actor_dialogue", "unlicensed_scene_dialogue"]
