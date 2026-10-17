"""Bounded excerpts from preserved source imports for lightweight planning."""

from __future__ import annotations

import json
from hashlib import sha256
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


def current_story_context(project_root: Path, *, max_chars: int = 120_000) -> str:
    """Deliver complete registered sources; source files retain their own fact status."""
    root = project_root.expanduser().resolve()
    paths = [path for folder in ('canon', 'characters') for path in (root / folder).glob('*')
             if not path.name.startswith('_') and path.suffix.lower() in {'.yaml', '.yml', '.json'}]
    continuity = root / 'workflow/continuity/current.json'
    if continuity.exists():
        paths.append(continuity)
    entries, size = [], 0
    for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix()):
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            raise ValueError('planning source escapes the project archive: ' + path.relative_to(root).as_posix())
        if not resolved.is_file():
            continue
        raw = resolved.read_bytes()
        content = raw.decode('utf-8-sig')
        size += len(content)
        if size > max_chars:
            raise ValueError('planning story sources exceed context capacity; scope the archives explicitly before planning')
        entries.append({'path': path.relative_to(root).as_posix(), 'file_sha256': sha256(raw).hexdigest(),
                        'complete': True, 'content': content})
    return ('## 已有人物、Canon与连续性来源\n'
        '以下为当前档案全文，优先于规划中的人物简介；不重新发明已有人物的亲属关系、经历和时间。'
        '各文件中的正式事实、候选、待确认项与人物认知保持原状态；候选不因出现在资料中而生效。'
        '档案相互矛盾时明确列出冲突与来源，保留待裁定状态，不用称呼游戏、叙述视角或新身世掩盖。'
        '视角与叙述声音沿用已有约定，只有得到创作方向授权时才改变；第一人称与第三人称均可。\n'
        + json.dumps({'sources': entries}, ensure_ascii=False, separators=(',', ':')))


__all__ = ["imported_source_context", "current_story_context"]
