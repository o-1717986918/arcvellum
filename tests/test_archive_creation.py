from pathlib import Path
import tempfile
import unittest
from unittest import mock

from literary_engineering_studio.application.assets.contracts import OwnerAssetCreation, SemanticReview
from literary_engineering_studio.application.assets.creation import (
    AssetCreationConflictError,
    AssetCreationPreviewStaleError,
    OwnerCreationService,
    creation_template,
    materialize_creation_template,
)
from literary_engineering_studio.application.assets.loader import AssetLoader
from literary_engineering_studio.application.assets.registry import AssetViewRegistry
from literary_engineering_studio.application.assets.revisions import AssetRevisionService
from literary_engineering_studio.persistence.job_store import JobStore


class ArchiveCreationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        data = Path(self.temporary.name)
        self.root = data / "work"
        self.root.mkdir()
        (self.root / "project.yaml").write_text("title: 创建测试\n", encoding="utf-8")
        self.registry = AssetViewRegistry.default()
        self.loader = AssetLoader(self.registry)
        self.store = JobStore(data / "studio.sqlite3")
        self.service = OwnerCreationService(
            self.registry,
            self.loader,
            AssetRevisionService(self.store),
        )

    def tearDown(self):
        self.temporary.cleanup()

    def test_all_registered_creation_templates_have_stable_controlled_shapes(self):
        options = self.service.options(self.root)["items"]
        self.assertEqual(len(options), 7)
        for option in options:
            asset_type = str(option["asset_type"])
            definition = self.registry.definition(asset_type)
            local_id = definition.fixed_id or f"new_{asset_type.replace('-', '_')}"
            content = materialize_creation_template(str(option["template"]), local_id)
            if asset_type == "character":
                content = content.replace('name: ""', 'name: "新人物"', 1)
            if asset_type == "scene":
                content = content.replace('chapter_id: ""', 'chapter_id: "chapter_0001"', 1)
                content = content.replace("word_count_target: 0", "word_count_target: 1600", 1)
            creation = OwnerAssetCreation.create(
                asset_id=self.registry.asset_id(definition, local_id),
                asset_type=asset_type,
                content=content,
                semantic_review=SemanticReview.WAIVED,
                reason="作者创建新的正式作品资产。",
            )
            preview = self.service.preview(self.root, creation)
            self.assertTrue(preview["validation"]["valid"], asset_type)
            self.assertTrue(preview["committable"], asset_type)

    def test_creation_records_history_and_refuses_existing_target(self):
        creation = self._character_creation()
        preview = self.service.preview(self.root, creation)
        receipt = self.service.create(
            self.root,
            creation,
            preview_digest=str(preview["preview_digest"]),
        )

        self.assertEqual(receipt["operation"], "create")
        self.assertTrue((self.root / "characters" / "new_hero.yaml").is_file())
        history = self.store.list_asset_transactions(str(self.root), creation.asset_id)
        self.assertEqual(history[0]["operation"], "create")
        with self.assertRaises(AssetCreationConflictError):
            self.service.create(
                self.root,
                self._character_creation(),
                preview_digest=str(preview["preview_digest"]),
            )

    def test_preview_digest_binds_content_and_reason(self):
        creation = self._character_creation()
        preview = self.service.preview(self.root, creation)
        changed = OwnerAssetCreation.create(
            asset_id=creation.asset_id,
            asset_type=creation.asset_type,
            content=creation.content.replace("新人物", "另一个人物"),
            semantic_review=SemanticReview.WAIVED,
            reason=creation.reason,
        )
        with self.assertRaises(AssetCreationPreviewStaleError):
            self.service.create(
                self.root,
                changed,
                preview_digest=str(preview["preview_digest"]),
            )
        self.assertFalse((self.root / "characters" / "new_hero.yaml").exists())

    def test_invalid_stable_id_and_missing_required_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            self.registry.parse_asset_id("character:../escape")
        creation = OwnerAssetCreation.create(
            asset_id="character:new_hero",
            asset_type="character",
            content="character_id: new_hero\nimportance: major\n",
            semantic_review=SemanticReview.WAIVED,
            reason="作者创建新的正式作品资产。",
        )
        preview = self.service.preview(self.root, creation)
        self.assertFalse(preview["validation"]["valid"])
        self.assertFalse(preview["committable"])

    def test_failed_transaction_finalization_removes_new_formal_file(self):
        creation = self._character_creation()
        preview = self.service.preview(self.root, creation)
        original_replace = Path.replace

        def fail_transaction_directory(path: Path, target: Path):
            if path.name.startswith(".owner-create-"):
                raise OSError("injected transaction finalization failure")
            return original_replace(path, target)

        with mock.patch.object(Path, "replace", autospec=True, side_effect=fail_transaction_directory):
            with self.assertRaises(OSError):
                self.service.create(
                    self.root,
                    creation,
                    preview_digest=str(preview["preview_digest"]),
                )
        self.assertFalse((self.root / "characters" / "new_hero.yaml").exists())

    def _character_creation(self) -> OwnerAssetCreation:
        content = materialize_creation_template(creation_template("character"), "new_hero")
        content = content.replace('name: ""', 'name: "新人物"', 1)
        return OwnerAssetCreation.create(
            asset_id="character:new_hero",
            asset_type="character",
            content=content,
            semantic_review=SemanticReview.WAIVED,
            reason="作者创建新的正式作品资产。",
        )


if __name__ == "__main__":
    unittest.main()
