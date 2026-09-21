"""Controlled source import that delegates to the Engine transaction."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable

from literary_engineering_studio_engine.public.projects import (
    ingest_existing_work,
)

from .contracts import ArchaeologyImportSpec


class ArchaeologyImportService:
    def __init__(self, kernel_for: Callable[[Path], str] | None = None):
        self.kernel_for = kernel_for or (lambda _root: "strict-v1")

    def import_source(
        self,
        project_root: Path,
        spec: ArchaeologyImportSpec,
    ) -> dict[str, object]:
        root = project_root.expanduser().resolve()
        lean = self.kernel_for(root) == "lean-v2"
        with TemporaryDirectory(prefix="arcvellum-archaeology-") as temporary:
            source = Path(temporary) / spec.filename
            source.write_bytes(spec.content)
            result = ingest_existing_work(
                root,
                source=source,
                title=spec.title,
                work_id=spec.work_id,
                mode=spec.mode,
                chunk_size=spec.chunk_size,
                rights_declaration=spec.rights_declaration,
                overwrite=spec.overwrite,
                emit_legacy_tasks=not lean,
            )
        return {
            "schema": "arcvellum/project-archaeology-import-receipt/v1",
            "work_id": result.work_id,
            "mode": spec.mode,
            "source_count": result.source_count,
            "chunk_count": result.chunk_count,
            "status": "imported",
            "next_action": (
                "来源已保全；继续规划时将引用代表性片段。"
                if lean else "启动整理，让 Agent 按证据逐块理解这部作品。"
            ),
        }
