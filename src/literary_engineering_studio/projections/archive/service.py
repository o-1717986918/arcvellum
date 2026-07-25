"""Compose Archive projections from controlled asset services."""

from __future__ import annotations

from pathlib import Path

from ...application.assets.loader import AssetLoader
from ...application.assets.registry import AssetViewRegistry
from ...application.assets.revisions import AssetRevisionService
from .detail import project_asset_detail
from .history import project_asset_history
from .tree import project_asset_tree


class ArchiveProjectionService:
    def __init__(
        self,
        registry: AssetViewRegistry,
        loader: AssetLoader,
        revisions: AssetRevisionService | None = None,
    ):
        self.registry = registry
        self.loader = loader
        self.revisions = revisions

    def tree(self, project_root: Path) -> dict[str, object]:
        return project_asset_tree(self.loader.list(project_root), self.registry)

    def detail(self, project_root: Path, asset_id: str) -> dict[str, object]:
        return project_asset_detail(self.loader.load(project_root, asset_id), self.registry)

    def history(self, project_root: Path, asset_id: str) -> dict[str, object]:
        if self.revisions is None:
            raise RuntimeError("Archive history persistence is unavailable")
        return project_asset_history(project_root, asset_id, self.loader, self.revisions)
