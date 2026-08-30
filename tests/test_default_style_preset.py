from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.application.project_manager import create_project
from literary_engineering_studio_engine.literary.style.defaults import (
    DEFAULT_STYLE_ID,
    ensure_default_style_mount,
)
from literary_engineering_studio_engine.literary.style.lab import active_project_style
from literary_engineering_studio_engine.literary.style.prompt import (
    style_prompt_quality_report,
)
from literary_engineering_studio_engine.prompting.style_context import (
    resolve_style_prompt_context,
)


class DefaultStylePresetTests(unittest.TestCase):
    def test_studio_project_creation_mounts_reviewed_default_through_formal_mount(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            with patch(
                "literary_engineering_studio.application.project_manager.default_config_path",
                return_value=base / "studio" / "config.json",
            ):
                project = create_project(
                    parent_directory=str(base),
                    title="清简叙事验证",
                    folder_name="work",
                )

            root = Path(project["path"])
            active = active_project_style(root)
            self.assertEqual(active["style_id"], DEFAULT_STYLE_ID)
            self.assertEqual(active["integrity"]["status"], "pass")
            self.assertEqual(active["scope"], "project")
            self.assertEqual(active["priority"], "highest")
            self.assertEqual(
                active["enforcement"],
                {
                    "director": "required",
                    "composition": "required",
                    "generation": "required",
                    "revision": "required",
                    "review": "required",
                },
            )

            context = resolve_style_prompt_context(root, text_limit=20000)
            self.assertIsNotNone(context.path)
            assert context.path is not None
            self.assertTrue(context.path.is_relative_to(root / "style" / "mounted"))
            self.assertEqual(context.snapshot["style_id"], DEFAULT_STYLE_ID)
            quality = style_prompt_quality_report(
                context.path.read_text(encoding="utf-8")
            )
            self.assertTrue(quality["length_ok"])
            self.assertTrue(quality["structure_ok"])
            self.assertGreaterEqual(int(quality["detail_chars"]), 500)
            self.assertLessEqual(int(quality["detail_chars"]), 2500)

            config = json.loads(
                (root / "style" / "default_style.json").read_text(encoding="utf-8")
            )
            self.assertEqual(config["style_id"], DEFAULT_STYLE_ID)
            self.assertEqual(config["version_id"], active["version_id"])
            self.assertTrue(config["replaceable"])

    def test_default_mount_is_idempotent_and_does_not_replace_an_active_style(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            with patch(
                "literary_engineering_studio.application.project_manager.default_config_path",
                return_value=base / "studio" / "config.json",
            ):
                project = create_project(
                    parent_directory=str(base),
                    title="幂等验证",
                    folder_name="work",
                )
            root = Path(project["path"])
            before = active_project_style(root)

            repeated = ensure_default_style_mount(root)
            after = active_project_style(root)

            self.assertFalse(repeated.mounted)
            self.assertIn("already has an active style", repeated.skipped_reason)
            self.assertEqual(before["style_id"], after["style_id"])
            self.assertEqual(before["version_id"], after["version_id"])
            self.assertEqual(before["content_hash"], after["content_hash"])


if __name__ == "__main__":
    unittest.main()
