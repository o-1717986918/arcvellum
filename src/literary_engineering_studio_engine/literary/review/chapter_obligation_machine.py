"""Machine-owned chapter-obligation identity projected into Agent tasks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .reader_experience import (
    _chapter_obligation_scaffold,
    _rel,
    chapter_obligation_path,
)


def chapter_obligation_machine_contract(root: Path, chapter_id: str) -> dict[str, Any]:
    root = root.resolve()
    json_path = chapter_obligation_path(root, chapter_id)
    scaffold = _chapter_obligation_scaffold(root, chapter_id, json_path)
    locked_fields = {
        key: scaffold[key]
        for key in (
            "schema",
            "chapter_id",
            "count_unit",
            "machine_count_unit",
            "target_chinese_chars",
            "scene_count_target",
            "source_paths",
            "output_path",
        )
    }
    scene_rows = [
        {
            key: row[key]
            for key in (
                "scene_id",
                "word_count_target",
                "word_count_min",
                "word_count_max",
            )
        }
        for row in scaffold["reader_experience_by_scene"]
    ]
    return {
        "path": _rel(json_path, root),
        "markdown_path": _rel(json_path.with_suffix(".md"), root),
        "fields": locked_fields,
        "scene_rows": scene_rows,
    }


__all__ = ["chapter_obligation_machine_contract"]
