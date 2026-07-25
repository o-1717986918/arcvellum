"""Resolve registered asset identities inside a project boundary."""

from __future__ import annotations

from pathlib import Path

from literary_engineering_studio_engine.display_cleaner import scalar_from_yaml_text

from .contracts import AssetRecord, AssetViewDefinition
from .registry import AssetViewRegistry
from .revisions import content_revision


class AssetLoader:
    def __init__(self, registry: AssetViewRegistry):
        self.registry = registry

    def load(self, project_root: Path, asset_id: str) -> AssetRecord:
        root = self.project_root(project_root)
        definition, local_id = self.registry.parse_asset_id(asset_id)
        path = self._asset_path(root, definition, local_id)
        if not path.is_file():
            raise FileNotFoundError(f"Archive asset not found: {asset_id}")
        content = path.read_text(encoding="utf-8")
        return self._record(root, definition, local_id, path, content)

    def resolve_path(self, project_root: Path, asset_id: str) -> Path:
        """Resolve a registered asset path without requiring it to exist."""

        root = self.project_root(project_root)
        definition, local_id = self.registry.parse_asset_id(asset_id)
        return self._asset_path(root, definition, local_id)

    def list(self, project_root: Path) -> tuple[AssetRecord, ...]:
        root = self.project_root(project_root)
        records: list[AssetRecord] = []
        for definition in self.registry.definitions():
            if definition.fixed_id:
                candidates = ((definition.fixed_id, self._asset_path(root, definition, definition.fixed_id)),)
            else:
                folder = (root / definition.relative_directory).resolve()
                candidates = tuple(
                    (path.stem, path)
                    for path in sorted(folder.glob(definition.filename_template.replace("{id}", "*")))
                    if path.is_file() and not path.name.startswith("_") and "candidates" not in path.parts
                ) if folder.is_dir() and folder.is_relative_to(root) else ()
            for local_id, path in candidates:
                if not path.is_file():
                    continue
                self.registry.parse_asset_id(self.registry.asset_id(definition, local_id))
                safe_path = self._assert_inside(root, path)
                content = safe_path.read_text(encoding="utf-8")
                records.append(self._record(root, definition, local_id, safe_path, content))
        return tuple(records)

    def _asset_path(self, root: Path, definition: AssetViewDefinition, local_id: str) -> Path:
        filename = definition.filename_template.format(id=local_id)
        return self._assert_inside(root, root / definition.relative_directory / filename)

    @staticmethod
    def _assert_inside(root: Path, path: Path) -> Path:
        resolved = path.resolve()
        if not resolved.is_relative_to(root) or path.is_symlink():
            raise ValueError("archive asset path escapes the project boundary")
        return resolved

    @staticmethod
    def project_root(project_root: Path) -> Path:
        root = project_root.expanduser().resolve()
        if not root.is_dir() or not (root / "project.yaml").is_file():
            raise ValueError("archive project must contain project.yaml")
        return root

    def _record(
        self,
        root: Path,
        definition: AssetViewDefinition,
        local_id: str,
        path: Path,
        content: str,
    ) -> AssetRecord:
        title = scalar_from_yaml_text(content, definition.title_field) if definition.title_field else ""
        return AssetRecord(
            asset_id=self.registry.asset_id(definition, local_id),
            asset_type=definition.asset_type,
            local_id=local_id,
            relative_path=path.relative_to(root).as_posix(),
            revision=content_revision(content),
            title=title or local_id.replace("_", " "),
            content=content,
            media_type=_media_type(path),
        )


def _media_type(path: Path) -> str:
    return {
        ".json": "application/json",
        ".md": "text/markdown",
        ".yaml": "application/yaml",
        ".yml": "application/yaml",
    }.get(path.suffix.lower(), "text/plain")
