"""Knowledge store abstraction built on the lightweight memory index."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .memory_index import build_memory_index, load_index, tokenize


KNOWLEDGE_BACKENDS = {"json"}
KNOWLEDGE_SCHEMA = "literary-engineering-workbench/knowledge-store/v0.1"


@dataclass(frozen=True)
class KnowledgeBuildResult:
    project_root: Path
    store_path: Path
    backend: str
    item_count: int
    source_count: int


@dataclass(frozen=True)
class KnowledgeHit:
    chunk_id: str
    source: str
    kind: str
    canon_status: str
    score: float
    text: str
    metadata: dict[str, str]


class KnowledgeStoreBackend(Protocol):
    name: str

    def build(self, project_root: Path, output: Path | None = None) -> KnowledgeBuildResult:
        """Build the backend store."""

    def search(
        self,
        project_root: Path,
        query: str,
        top_k: int = 8,
        kind: str = "",
        canon_status: str = "",
    ) -> list[KnowledgeHit]:
        """Search the backend store."""


class JsonKnowledgeStore:
    name = "json"

    def build(self, project_root: Path, output: Path | None = None) -> KnowledgeBuildResult:
        root = project_root.resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"project root not found: {root}")

        index_result = build_memory_index(root)
        index = load_index(root)
        items = []
        for chunk in index.get("chunks", []):
            metadata = _metadata_for_source(str(chunk.get("source", "")))
            items.append(
                {
                    "id": chunk.get("id", ""),
                    "source": chunk.get("source", ""),
                    "kind": chunk.get("kind", ""),
                    "chunk_index": chunk.get("chunk_index", 0),
                    "char_count": chunk.get("char_count", 0),
                    "terms": chunk.get("terms", []),
                    "text": chunk.get("text", ""),
                    "metadata": metadata,
                }
            )

        store_path = output or root / "memory" / "knowledge_store.json"
        store_path = store_path if store_path.is_absolute() else root / store_path
        store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": KNOWLEDGE_SCHEMA,
            "backend": self.name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "project_root": str(root),
            "source_count": index_result.source_count,
            "item_count": len(items),
            "items": items,
        }
        store_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return KnowledgeBuildResult(
            project_root=root,
            store_path=store_path,
            backend=self.name,
            item_count=len(items),
            source_count=index_result.source_count,
        )

    def search(
        self,
        project_root: Path,
        query: str,
        top_k: int = 8,
        kind: str = "",
        canon_status: str = "",
    ) -> list[KnowledgeHit]:
        root = project_root.resolve()
        store = _load_store(root)
        query_terms = tokenize(query)
        if not query_terms:
            return []

        hits: list[KnowledgeHit] = []
        for item in store.get("items", []):
            item_kind = str(item.get("kind", ""))
            metadata = {str(k): str(v) for k, v in dict(item.get("metadata", {})).items()}
            item_status = metadata.get("canon_status", "")
            if kind and item_kind != kind:
                continue
            if canon_status and item_status != canon_status:
                continue

            terms = set(item.get("terms", []))
            overlap = query_terms & terms
            if not overlap:
                continue
            score = float(len(overlap))
            text = str(item.get("text", ""))
            for phrase in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_]{3,}", query):
                if phrase and phrase.lower() in text.lower():
                    score += 2.5
            if item_status == "confirmed":
                score += 0.25
            hits.append(
                KnowledgeHit(
                    chunk_id=str(item.get("id", "")),
                    source=str(item.get("source", "")),
                    kind=item_kind,
                    canon_status=item_status,
                    score=score,
                    text=text,
                    metadata=metadata,
                )
            )

        hits.sort(key=lambda item: (-item.score, item.source, item.chunk_id))
        return hits[:top_k]


def build_knowledge_store(project_root: Path, backend: str = "json", output: Path | None = None) -> KnowledgeBuildResult:
    return _backend_for(backend).build(project_root, output=output)


def search_knowledge_store(
    project_root: Path,
    query: str,
    top_k: int = 8,
    backend: str = "json",
    kind: str = "",
    canon_status: str = "",
) -> list[KnowledgeHit]:
    return _backend_for(backend).search(
        project_root,
        query,
        top_k=top_k,
        kind=kind,
        canon_status=canon_status,
    )


def _backend_for(backend: str) -> KnowledgeStoreBackend:
    if backend == "json":
        return JsonKnowledgeStore()
    raise ValueError(f"unknown knowledge backend: {backend}. valid: {', '.join(sorted(KNOWLEDGE_BACKENDS))}")


def _load_store(root: Path) -> dict[str, object]:
    store_path = root / "memory" / "knowledge_store.json"
    if not store_path.exists():
        raise FileNotFoundError(f"knowledge store not found: {store_path}. run knowledge-build first")
    return json.loads(store_path.read_text(encoding="utf-8"))


def _metadata_for_source(source: str) -> dict[str, str]:
    path = Path(source)
    parts = path.parts
    kind = parts[0] if parts else "project"
    metadata = {
        "source": source,
        "kind": kind,
        "canon_status": _canon_status_for(kind),
        "scene_id": _extract_id(source, r"(scene[_-]?\d+)", fallback=""),
        "chapter_id": _extract_id(source, r"(chapter[_-]?\d+)", fallback=""),
        "character_id": path.stem if kind == "characters" and path.stem != "_template" else "",
    }
    if kind == "canon":
        metadata["authority"] = "hard"
    elif kind in {"characters", "plot", "style", "sources", "scenes"}:
        metadata["authority"] = "structured"
    else:
        metadata["authority"] = "working"
    return metadata


def _canon_status_for(kind: str) -> str:
    if kind in {"canon", "characters"}:
        return "confirmed"
    if kind in {"plot", "style", "scenes", "project"}:
        return "planned"
    if kind in {"drafts", "branches", "reviews", "prompts", "exports", "tests", "sources"}:
        return "candidate"
    return "working"


def _extract_id(value: str, pattern: str, fallback: str = "") -> str:
    match = re.search(pattern, value, re.I)
    return match.group(1) if match else fallback
