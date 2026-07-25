"""Compose Archive projections from controlled asset services."""

from __future__ import annotations

from pathlib import Path

from ...application.assets.loader import AssetLoader
from ...application.assets.registry import AssetViewRegistry
from .detail import project_asset_detail
from .tree import project_asset_tree


class ArchiveProjectionService:
    def __init__(self, registry: AssetViewRegistry, loader: AssetLoader):
        self.registry = registry
        self.loader = loader

    def tree(self, project_root: Path) -> dict[str, object]:
        return project_asset_tree(self.loader.list(project_root), self.registry)

    def detail(self, project_root: Path, asset_id: str) -> dict[str, object]:
        return project_asset_detail(self.loader.load(project_root, asset_id), self.registry)
