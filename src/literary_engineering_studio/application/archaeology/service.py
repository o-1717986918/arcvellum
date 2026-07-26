"""Project Archaeology application service."""

from __future__ import annotations

from pathlib import Path

from .contracts import ArchaeologyImportSpec, mode_catalog
from .import_service import ArchaeologyImportService
from .projection import project_archaeology_catalog, project_archaeology_workbench


class ArchaeologyApplicationService:
    def __init__(self, importer: ArchaeologyImportService | None = None):
        self.importer = importer or ArchaeologyImportService()

    def options(self) -> dict[str, object]:
        return {
            "schema": "arcvellum/project-archaeology-options/v1",
            "modes": mode_catalog(),
            "supported_extensions": [".txt", ".md", ".markdown", ".docx"],
            "max_source_bytes": 25 * 1024 * 1024,
        }

    def catalog(self, project_root: Path) -> dict[str, object]:
        return project_archaeology_catalog(project_root)

    def workbench(self, project_root: Path, work_id: str) -> dict[str, object]:
        return project_archaeology_workbench(project_root, work_id)

    def import_source(
        self,
        project_root: Path,
        spec: ArchaeologyImportSpec,
    ) -> dict[str, object]:
        receipt = self.importer.import_source(project_root, spec)
        return {
            "receipt": receipt,
            "workbench": self.workbench(project_root, str(receipt["work_id"])),
        }
