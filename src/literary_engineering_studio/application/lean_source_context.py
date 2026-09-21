"""Bounded excerpts from preserved source imports for lightweight planning."""

from __future__ import annotations

import json
from pathlib import Path


def imported_source_context(project_root: Path, *, max_chars: int = 9000) -> tuple[int, str]:
    root = project_root.expanduser().resolve()
    imports = root / "sources" / "imports"
    manifests = sorted(imports.glob("*/source_manifest.json")) if imports.is_dir() else []
    if not manifests:
        return 0, ""
    fragments = [_source_fragment(root, imports, path) for path in manifests[-3:]]
    return len(manifests), "\n\n".join(fragments)[:max_chars]


def _source_fragment(root: Path, imports: Path, manifest_path: Path) -> str:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    chunks = manifest.get("chunks") or []
    if not isinstance(chunks, list) or not chunks:
        return ""
    selected = sorted({0, len(chunks) // 2, len(chunks) - 1})
    samples = [_sample_chunk(root, imports, chunks[index]) for index in selected]
    samples = [sample for sample in samples if sample]
    if not samples:
        return ""
    return (
        f"来源《{str(manifest.get('title') or manifest_path.parent.name)}》"
        f"（{str(manifest.get('mode') or 'analysis')}，代表性片段，非全文）\n"
        + "\n[片段]\n".join(samples)
    )


def _sample_chunk(root: Path, imports: Path, row: object) -> str:
    relative = str(row.get("path") or "") if isinstance(row, dict) else ""
    path = (root / relative).resolve()
    if relative and path.is_relative_to(imports) and path.is_file():
        return path.read_text(encoding="utf-8")[:3000]
    return ""


__all__ = ["imported_source_context"]
