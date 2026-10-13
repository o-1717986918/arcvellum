"""Narrative-mode presets over immutable measured style versions."""
import json
from pathlib import Path
import re

from literary_engineering_studio_engine.public.literary import active_style_reference_catalog

from .stylometry_contracts import CreatorStyleSnapshot, StylePresetV1, StylePresetCollectionV1


class StylePresetService:
    def __init__(self, repository):
        self.repository = repository

    def collection(self, root: Path) -> StylePresetCollectionV1:
        collection = self.repository.presets(root) if hasattr(self.repository, "presets") else StylePresetCollectionV1()
        if collection.revision or collection.presets:
            return collection
        single = self.repository.snapshot(root)
        if not single.enabled:
            return collection
        preset = StylePresetV1("default", "当前作品文风", "沿用当前作品的表达选择", (), (), single.version_id,
                              combine=single.combine, usage=single.usage)
        return StylePresetCollectionV1(0, True, "default", (preset,))

    def save(self, root: Path, collection: StylePresetCollectionV1, expected_revision: int):
        if not (root.resolve() / "project.yaml").is_file():
            raise ValueError("文风预设需要已有作品。")
        ids = [row.preset_id for row in collection.presets]
        if len(ids) > 32 or len(set(ids)) != len(ids):
            raise ValueError("文风预设标识需唯一，最多保存 32 项。")
        for row in collection.presets:
            _validate_preset(row)
            self.repository.version(root, row.stylometry_version_id)
        active = {row.preset_id for row in collection.presets if row.active}
        if collection.enabled and collection.default_preset_id not in active:
            raise ValueError("请选择一个有效的默认文风预设。")
        return self.repository.save_presets(root, collection, expected_revision).to_dict()

    def snapshot(self, root: Path, preset_id: str) -> CreatorStyleSnapshot:
        stored = self.repository.presets(root) if hasattr(self.repository, "presets") else StylePresetCollectionV1()
        if not stored.presets and not stored.revision and preset_id == "default":
            return self.repository.snapshot(root)
        collection = self.collection(root)
        row = next((item for item in collection.presets if item.preset_id == preset_id and item.active), None)
        if not collection.enabled or row is None:
            raise ValueError("文风预设未激活或不存在。")
        record = self.repository.version(root, row.stylometry_version_id)
        compiled = json.loads(record.compiled_json)
        return CreatorStyleSnapshot(True, collection.revision, record.version_id, record.profile_id,
            row.combine, row.usage, record.fragment_text, record.content_sha256,
            compiled["compiler_version"], compiled["profile_sha256"], compiled["controls_sha256"])

    def catalog(self, root: Path):
        collection = self.collection(root)
        rows = []
        for row in collection.presets:
            data = {**row.__dict__, "snapshot": self.snapshot(root, row.preset_id).to_dict()
                    if collection.enabled and row.active else None}
            rows.append(data)
        return {**collection.to_dict(), "presets": rows,
                "reference_catalog": active_style_reference_catalog(root)}


def _validate_preset(row):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,63}", row.preset_id):
        raise ValueError("文风预设标识需使用小写字母、数字和连字符。")
    if not 1 <= len(row.title.strip()) <= 80 or len(row.literary_intent) > 8000:
        raise ValueError("文风预设需要有效标题与文学意图。")
    for values in (row.narrative_modes, row.reference_ids):
        if len(values) > 32 or len(set(values)) != len(values) or any(not value.strip() or len(value) > 120 for value in values):
            raise ValueError("文风预设的叙述方式与参照标识需有效且唯一。")
    if type(row.active) is not bool:
        raise ValueError("文风预设状态需为布尔值。")
    if row.combine not in {"append", "replace"} or row.usage not in {"guide", "observe"}:
        raise ValueError("文风预设需要有效的组合方式与用途。")
