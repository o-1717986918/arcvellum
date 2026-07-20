from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from pathlib import Path


INDEX_VERSION = "0.1"
TEXT_EXTENSIONS = {".md", ".txt", ".yaml", ".yml", ".json", ".csv"}
ROOT_FILES = {"project.yaml", "AGENTS.md", "agentread.yaml"}
INCLUDE_DIRS = {
    "canon",
    "characters",
    "plot",
    "style",
    "sources",
    "scenes",
    "drafts",
    "reviews",
    "branches",
    "prompts",
    "exports",
    "tests",
}
SKIP_DIRS = {"memory", ".git", "__pycache__"}


@dataclass(frozen=True)
class IndexResult:
    project_root: Path
    index_path: Path
    chunk_count: int
    source_count: int


@dataclass(frozen=True)
class SearchHit:
    chunk_id: str
    source: str
    kind: str
    score: float
    text: str


def tokenize(text: str) -> set[str]:
    tokens: set[str] = set()
    for token in re.findall(r"[A-Za-z0-9_]+", text.lower()):
        if len(token) >= 2:
            tokens.add(token)

    cjk = re.findall(r"[\u4e00-\u9fff]", text)
    tokens.update(cjk)
    for i in range(len(cjk) - 1):
        tokens.add(cjk[i] + cjk[i + 1])
    return tokens


def _kind_for(path: Path, root: Path) -> str:
    rel = path.relative_to(root).as_posix()
    if "/" not in rel:
        return "project"
    return rel.split("/", 1)[0]


def _iter_source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(root).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        if path.name not in ROOT_FILES and (not rel_parts or rel_parts[0] not in INCLUDE_DIRS):
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        files.append(path)
    return sorted(files)


def _chunk_text(text: str, max_chars: int = 900) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if not current:
            current = para
        elif len(current) + len(para) + 2 <= max_chars:
            current += "\n\n" + para
        else:
            chunks.append(current)
            current = para

        while len(current) > max_chars:
            chunks.append(current[:max_chars])
            current = current[max_chars:]

    if current:
        chunks.append(current)
    return chunks


def build_memory_index(project_root: Path) -> IndexResult:
    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")

    chunks = []
    source_files = _iter_source_files(root)
    for source in source_files:
        text = source.read_text(encoding="utf-8", errors="ignore")
        rel = source.relative_to(root).as_posix()
        for idx, chunk_text in enumerate(_chunk_text(text)):
            terms = sorted(tokenize(chunk_text))
            chunks.append(
                {
                    "id": f"{rel}#{idx}",
                    "source": rel,
                    "kind": _kind_for(source, root),
                    "chunk_index": idx,
                    "char_count": len(chunk_text),
                    "terms": terms,
                    "text": chunk_text,
                }
            )

    payload = {
        "schema": f"lew-memory-index/{INDEX_VERSION}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(root),
        "source_count": len(source_files),
        "chunk_count": len(chunks),
        "chunks": chunks,
    }

    index_path = root / "memory" / "index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return IndexResult(
        project_root=root,
        index_path=index_path,
        chunk_count=len(chunks),
        source_count=len(source_files),
    )


def load_index(project_root: Path) -> dict:
    index_path = project_root.resolve() / "memory" / "index.json"
    if not index_path.exists():
        raise FileNotFoundError(f"memory index not found: {index_path}")
    return json.loads(index_path.read_text(encoding="utf-8"))


def search_memory(project_root: Path, query: str, top_k: int = 8) -> list[SearchHit]:
    index = load_index(project_root)
    query_terms = tokenize(query)
    if not query_terms:
        return []

    hits: list[SearchHit] = []
    for chunk in index.get("chunks", []):
        terms = set(chunk.get("terms", []))
        overlap = query_terms & terms
        if not overlap:
            continue
        score = float(len(overlap))
        text = chunk.get("text", "")
        for phrase in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_]{3,}", query):
            if phrase and phrase.lower() in text.lower():
                score += 2.5
        hits.append(
            SearchHit(
                chunk_id=chunk["id"],
                source=chunk["source"],
                kind=chunk["kind"],
                score=score,
                text=text,
            )
        )

    hits.sort(key=lambda item: (-item.score, item.source, item.chunk_id))
    return hits[:top_k]
