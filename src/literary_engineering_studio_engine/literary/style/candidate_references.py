"""Bounded, reviewable reference candidates from user-supplied style sources."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from .reference_projection import REFERENCE_INDEX_SCHEMA


_SCENE_CUES = (
    (("“", "”", "问", "答"), ("对话", "关系", "问答", "dialogue", "relationship"), "dialogue-rebound"),
    (("跑", "追", "打", "冲", "逃"), ("动作", "追逐", "冲突", "action", "conflict"), "action-motion"),
    (("想", "记得", "梦", "回忆"), ("内省", "余波", "回忆", "reflection", "aftermath"), "interior-distance"),
    (("城", "街", "雨", "屋", "门"), ("氛围", "过场", "空间", "atmosphere", "transition"), "space-reveal"),
)


def append_candidate_references(profile: str, sources: list[tuple[Path, str]]) -> tuple[str, dict[str, Any]]:
    """Append complete bounded excerpts; metadata remains editable before version freeze."""

    excerpts = [_complete_excerpt(text) for _, text in sources[:12]]
    excerpts = [excerpt for excerpt in excerpts if excerpt]
    if not excerpts:
        return profile, {}
    output = profile.rstrip() + "\n\n## 候选参考选段\n\n以下单元来自已导入语料；文风版本冻结前可审查技法标签。\n"
    units: list[dict[str, Any]] = []
    for number, excerpt in enumerate(excerpts, 1):
        unit_id = f"R{number:02d}"
        output += f"\n### {unit_id}\n\n"
        start = len(output)
        output += excerpt
        end = len(output)
        output += "\n"
        match_terms, axes = _classify(excerpt)
        units.append({
            "unit_id": unit_id,
            "source_digest": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
            "span": {"start": start, "end": end},
            "match_terms": match_terms,
            "technique_axes": axes,
        })
    return output, {
        "schema": REFERENCE_INDEX_SCHEMA,
        "profile_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
        "review_status": "candidate",
        "units": units,
    }


def _complete_excerpt(source: str) -> str:
    paragraphs = [
        part.strip() for part in re.split(r"\n\s*\n", source.strip())
        if part.strip() and not re.match(r"^(?:作者|版权|来源|许可|copyright|isbn|https?://)\s*[:：]?", part.strip(), re.I)
    ]
    if not paragraphs:
        return ""
    selected: list[str] = []
    for paragraph in paragraphs:
        if len("\n\n".join((*selected, paragraph))) > 1200:
            break
        selected.append(paragraph)
    if selected:
        return "\n\n".join(selected)
    sentences = re.findall(r"[^。！？!?]*[。！？!?]", paragraphs[0])
    selected_sentences: list[str] = []
    for sentence in sentences:
        if len("".join((*selected_sentences, sentence))) > 1200:
            break
        selected_sentences.append(sentence)
    return "".join(selected_sentences).strip()


def _classify(excerpt: str) -> tuple[list[str], list[str]]:
    terms: list[str] = []
    axes: list[str] = []
    for clues, scene_terms, axis in _SCENE_CUES:
        if any(clue in excerpt for clue in clues):
            terms.extend(scene_terms)
            axes.append(axis)
    return list(dict.fromkeys(terms)), axes or ["scene-conditioned-style"]


__all__ = ["append_candidate_references"]
