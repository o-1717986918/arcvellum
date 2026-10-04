"""Read declared corpus sources and detect split leakage."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import unicodedata
from typing import Any

from .io import ContractError, read_object


SPLITS = {"train", "holdout"}
HAN = re.compile(r"[\u3400-\u9fff]")
ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")


@dataclass(frozen=True)
class Source:
    source_id: str
    work_id: str
    genre: str
    topic: str
    style_id: str | None
    split: str
    path: Path
    declared_path: str
    raw_sha256: str
    body_sha256: str
    text: str
    han_count: int

    def public(self) -> dict[str, Any]:
        result = {
            "source_id": self.source_id, "work_id": self.work_id,
            "genre": self.genre, "topic": self.topic, "split": self.split,
            "path": self.declared_path,
            "raw_sha256": self.raw_sha256, "body_sha256": self.body_sha256,
            "han_count": self.han_count,
        }
        if self.style_id is not None:
            result["style_id"] = self.style_id
        return result


@dataclass(frozen=True)
class Corpus:
    label: str
    sources: tuple[Source, ...]
    warnings: tuple[str, ...]

    def public(self) -> dict[str, Any]:
        return {
            "schema": "corpus-inspection/v1", "label": self.label,
            "sources": [item.public() for item in self.sources],
            "warnings": list(self.warnings),
            "train_source_count": sum(item.split == "train" for item in self.sources),
            "holdout_source_count": sum(item.split == "holdout" for item in self.sources),
        }


def normalize_source(text: str, *, markdown: bool) -> str:
    text = unicodedata.normalize("NFC", text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n"))
    if not markdown:
        return text.strip()
    lines: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or re.match(r"^\s*#{1,6}\s", line):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def load_corpus(path: Path) -> Corpus:
    manifest = read_object(path, "corpus-manifest/v1")
    rows = manifest.get("sources")
    if not isinstance(rows, list) or len(rows) < 2:
        raise ContractError("corpus needs at least two source rows, including train and holdout")
    sources: list[Source] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ContractError(f"source {index} must be an object")
        source = _load_source(path.parent, row, index)
        if source.source_id in seen_ids:
            raise ContractError(f"duplicate source_id: {source.source_id}")
        seen_ids.add(source.source_id)
        sources.append(source)
    if {item.split for item in sources} != SPLITS:
        raise ContractError("corpus requires both train and holdout sources")
    warnings = _split_warnings(sources)
    return Corpus(str(manifest.get("label") or path.stem), tuple(sources), tuple(warnings))


def _load_source(base: Path, row: dict[str, Any], index: int) -> Source:
    source_id = str(row.get("source_id") or "")
    work_id = str(row.get("work_id") or "")
    split = str(row.get("split") or "")
    if not ID.fullmatch(source_id) or not ID.fullmatch(work_id):
        raise ContractError(f"source {index} needs stable source_id and work_id")
    if split not in SPLITS:
        raise ContractError(f"source {source_id} split must be train or holdout")
    style_id = row.get("style_id")
    if style_id is not None and not ID.fullmatch(str(style_id)):
        raise ContractError(f"source {source_id} style_id must be a stable ASCII identifier")
    declared_path = str(row.get("path") or "").strip()
    if not declared_path:
        raise ContractError(f"source {source_id} needs path")
    target = (base / declared_path).expanduser().resolve()
    if target.suffix.lower() not in {".txt", ".md", ".markdown"} or not target.is_file():
        raise ContractError(f"source {source_id} must point to an existing TXT or Markdown file")
    try:
        raw = target.read_bytes()
        text = raw.decode("utf-8-sig", errors="strict")
    except (OSError, UnicodeError) as exc:
        raise ContractError(f"source {source_id} must be readable UTF-8: {exc}") from exc
    body = normalize_source(text, markdown=target.suffix.lower() != ".txt")
    han_count = len(HAN.findall(body))
    if han_count < 100:
        raise ContractError(f"source {source_id} has fewer than 100 Han characters")
    return Source(source_id, work_id, str(row.get("genre") or "unknown"), str(row.get("topic") or "unknown"),
                  str(style_id) if style_id is not None else None, split,
                  target, declared_path,
                  hashlib.sha256(raw).hexdigest(), hashlib.sha256(body.encode("utf-8")).hexdigest(), body, han_count)


def _shingles(text: str) -> set[str]:
    chars = "".join(HAN.findall(text))
    if len(chars) < 12:
        return set()
    step = max(1, (len(chars) - 11) // 50_000)
    return {chars[i:i + 12] for i in range(0, len(chars) - 11, step)}


def _split_warnings(sources: list[Source]) -> list[str]:
    warnings: list[str] = []
    train_works = {item.work_id for item in sources if item.split == "train"}
    holdout_works = {item.work_id for item in sources if item.split == "holdout"}
    for work_id in sorted(train_works & holdout_works):
        warnings.append(f"same work in train and holdout: {work_id}; exploratory evidence only")
    shingles = {item.source_id: _shingles(item.text) for item in sources}
    han_bodies = {item.source_id: "".join(HAN.findall(item.text)) for item in sources}
    for i, left in enumerate(sources):
        for right in sources[i + 1:]:
            if left.body_sha256 == right.body_sha256:
                if left.split != right.split:
                    raise ContractError(f"exact train/holdout duplicate: {left.source_id}, {right.source_id}")
                warnings.append(f"duplicate content: {left.source_id}, {right.source_id}")
                continue
            if left.split == right.split:
                continue
            shorter, longer = sorted((han_bodies[left.source_id], han_bodies[right.source_id]), key=len)
            if shorter in longer:
                raise ContractError(f"contained train/holdout source: {left.source_id}, {right.source_id}")
            left_set, right_set = shingles[left.source_id], shingles[right.source_id]
            overlap = len(left_set & right_set) / max(1, min(len(left_set), len(right_set)))
            if overlap >= 0.8:
                raise ContractError(f"near-duplicate train/holdout sources: {left.source_id}, {right.source_id}")
    return warnings
