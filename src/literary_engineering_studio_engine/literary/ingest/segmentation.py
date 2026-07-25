"""Deterministic structural segmentation and semantic chunk assembly."""

from __future__ import annotations

import re

from .contracts import SourceChunk, SourceDocument, SourceSegment


def segment_documents(documents: list[SourceDocument]) -> list[SourceSegment]:
    segments: list[SourceSegment] = []
    for document in documents:
        headings: dict[int, str] = {}
        for ordinal, bound in enumerate(document.bounds, start=1):
            text = document.text[bound.char_start : bound.char_end]
            kind = _segment_kind(bound.kind, text)
            if bound.heading_level:
                headings[bound.heading_level] = text.strip()
                headings = {
                    level: value
                    for level, value in headings.items()
                    if level <= bound.heading_level
                }
            heading_path = tuple(headings[level] for level in sorted(headings))
            segments.append(
                SourceSegment(
                    segment_id=f"{document.source_id}:segment-{ordinal:05d}",
                    source_id=document.source_id,
                    range_id=bound.range_id,
                    kind=kind,
                    text=text,
                    char_start=bound.char_start,
                    char_end=bound.char_end,
                    paragraph_start=bound.paragraph_start,
                    paragraph_end=bound.paragraph_end,
                    content_hash=bound.content_hash,
                    heading_level=bound.heading_level,
                    heading_path=heading_path,
                    page_start=bound.page_start,
                    page_end=bound.page_end,
                    source_part=bound.source_part,
                )
            )
    return segments


def build_source_chunks(
    segments: list[SourceSegment],
    *,
    chunk_size: int,
) -> list[SourceChunk]:
    limit = max(int(chunk_size or 6000), 200)
    return [
        _source_chunk(index, group)
        for index, group in enumerate(_chunk_groups(segments, limit), start=1)
    ]


def _chunk_groups(
    segments: list[SourceSegment],
    limit: int,
) -> list[list[SourceSegment]]:
    groups: list[list[SourceSegment]] = []
    current: list[SourceSegment] = []
    current_chars = 0
    for segment in segments:
        if _starts_new_chunk(current, segment, current_chars, limit):
            groups.append(current)
            current = []
            current_chars = 0
        current.append(segment)
        current_chars += len(segment.text) + (2 if len(current) > 1 else 0)
    if current:
        groups.append(current)
    return groups


def _starts_new_chunk(
    current: list[SourceSegment],
    segment: SourceSegment,
    current_chars: int,
    limit: int,
) -> bool:
    if not current:
        return False
    return (
        current[0].source_id != segment.source_id
        or segment.kind in {"volume", "chapter"}
        or current_chars + len(segment.text) + 2 > limit
    )


def _source_chunk(index: int, group: list[SourceSegment]) -> SourceChunk:
    text = "\n\n".join(item.text.strip() for item in group).rstrip() + "\n"
    headings = tuple(dict.fromkeys(item.heading_path for item in group if item.heading_path))
    return SourceChunk(
        chunk_id=f"chunk_{index:04d}",
        source_id=group[0].source_id,
        segment_ids=tuple(item.segment_id for item in group),
        evidence_ids=tuple(f"evidence:{item.segment_id}" for item in group),
        heading_paths=headings,
        text=text,
        char_start=min(item.char_start for item in group),
        char_end=max(item.char_end for item in group),
        paragraph_start=min(item.paragraph_start for item in group),
        paragraph_end=max(item.paragraph_end for item in group),
    )


def _segment_kind(bound_kind: str, text: str) -> str:
    if bound_kind == "footnote":
        return "footnote"
    if re.match(r"^(?:第[一二三四五六七八九十百千万零〇\d]+卷|卷[一二三四五六七八九十百千万零〇\d]+)\b", text.strip()):
        return "volume"
    if re.match(
        r"^(?:第[一二三四五六七八九十百千万零〇\d]+章|chapter\s+\w+|序章|楔子|尾声|后记|prologue|epilogue)\b",
        text.strip(),
        re.IGNORECASE,
    ):
        return "chapter"
    if bound_kind == "heading":
        return "section"
    if text.strip() in {"***", "---", "* * *"}:
        return "scene-break"
    return "paragraph"
