from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.application.assets.document_codec import AssetDocumentError
from literary_engineering_studio.application.assets.loader import AssetLoader
from literary_engineering_studio.application.assets.registry import AssetViewRegistry
from literary_engineering_studio.application.assets.structured_editor import (
    StructuredAssetService,
    StructuredDraftStaleError,
    StructuredFieldError,
)
from literary_engineering_studio.application.assets.validation import validate_asset_content


class ArchiveStructuredEditorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "work"
        self.root.mkdir()
        (self.root / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
        (self.root / "characters").mkdir()
        self.character_content = (
            "# 人物资产注释\n"
            "character_id: lin\n"
            'name: "林澈" # 保留引号\n'
            "importance: major\n"
            'role: "观察者"\n'
            "aliases: []\n"
            "background_story:\n"
            '  summary: "旧港长大"\n'
            "psychology: {}\n"
            "bdi: {}\n"
            "state: {}\n"
            "engine_owned: true\n"
        )
        (self.root / "characters" / "lin.yaml").write_text(
            self.character_content,
            encoding="utf-8",
        )
        self.registry = AssetViewRegistry.default()
        self.loader = AssetLoader(self.registry)
        self.service = StructuredAssetService(self.registry, self.loader)

    def tearDown(self):
        self.temporary.cleanup()

    def test_projection_and_render_preserve_yaml_comments_quotes_and_order(self):
        projection = self.service.project(
            self.root,
            "character:lin",
            self.character_content,
        )
        fields = {item["name"]: item for item in projection["fields"]}
        self.assertEqual(fields["name"]["value"], "林澈")
        self.assertEqual(fields["importance"]["options"], ["major", "secondary", "minor"])

        rendered = self.service.render(
            self.root,
            "character:lin",
            self.character_content,
            projection["source_revision"],
            {"name": "林汐", "aliases": ["潮生"]},
        )
        content = rendered["content"]

        self.assertIn("# 人物资产注释", content)
        self.assertIn('name: "林汐"', content)
        self.assertIn("# 保留引号", content)
        self.assertIn("engine_owned: true", content)
        self.assertLess(content.index("character_id:"), content.index("name:"))
        self.assertLess(content.index("name:"), content.index("importance:"))
        self.assertTrue(rendered["validation"]["valid"])

    def test_unregistered_field_and_stale_projection_are_rejected(self):
        projection = self.service.project(self.root, "character:lin", self.character_content)
        with self.assertRaises(StructuredFieldError):
            self.service.render(
                self.root,
                "character:lin",
                self.character_content,
                projection["source_revision"],
                {"character_id": "other"},
            )
        with self.assertRaises(StructuredDraftStaleError):
            self.service.render(
                self.root,
                "character:lin",
                self.character_content + "\n",
                projection["source_revision"],
                {"name": "林汐"},
            )

    def test_duplicate_yaml_keys_fail_the_formal_validation_gate(self):
        definition = self.registry.definition("character")
        duplicate = (
            "character_id: lin\n"
            "name: 林澈\n"
            "name: 林汐\n"
            "importance: major\n"
        )

        result = validate_asset_content(self.root, definition, "lin", duplicate)

        self.assertFalse(result.valid)
        self.assertIn("invalid_yaml", {issue.code for issue in result.issues})
        with self.assertRaises(AssetDocumentError):
            self.service.project(self.root, "character:lin", duplicate)

    def test_json_ledger_round_trips_through_the_same_contract(self):
        ledger = self.root / "plot" / "promises" / "ledger.json"
        ledger.parent.mkdir(parents=True)
        original = '{\n  "schema": "ledger/v1",\n  "promises": []\n}\n'
        ledger.write_text(original, encoding="utf-8")
        projection = self.service.project(
            self.root,
            "promise-ledger:ledger",
            original,
        )

        rendered = self.service.render(
            self.root,
            "promise-ledger:ledger",
            original,
            projection["source_revision"],
            {
                "promises": [
                    {
                        "promise_id": "p-001",
                        "content": "灯塔会在第三章重新亮起",
                    }
                ]
            },
        )

        self.assertIn('"schema": "ledger/v1"', rendered["content"])
        self.assertIn('"promise_id": "p-001"', rendered["content"])
        self.assertTrue(rendered["validation"]["valid"])


if __name__ == "__main__":
    unittest.main()
