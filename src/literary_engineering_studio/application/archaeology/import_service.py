"""Controlled source import that delegates to the Engine transaction."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from literary_engineering_studio_engine.projects.source_ingest import (
    ingest_existing_work,
)

from .contracts import ArchaeologyImportSpec


class ArchaeologyImportService:
    def import_source(
        self,
        project_root: Path,
        spec: ArchaeologyImportSpec,
    ) -> dict[str, object]:
        root = project_root.expanduser().resolve()
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
            )
        return {
            "schema": "arcvellum/project-archaeology-import-receipt/v1",
            "work_id": result.work_id,
            "mode": spec.mode,
            "source_count": result.source_count,
            "chunk_count": result.chunk_count,
            "status": "imported",
            "next_action": "启动整理，让 Agent 按证据逐块理解这部作品。",
        }
