from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.project_manager import create_project, validate_project_location


class ProjectLocationTests(unittest.TestCase):
    def test_create_uses_default_projects_root_when_parent_is_empty(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict("os.environ", {"LES_PROJECTS_ROOT": temporary, "LES_CONFIG_PATH": str(Path(temporary) / "config.json")}):
                result = create_project(parent_directory="", title="Default Location", target_length=1000)
        self.assertEqual(result["title"], "Default Location")

    def test_create_persists_explicit_story_structure_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict("os.environ", {"LES_CONFIG_PATH": str(Path(temporary) / "config.json")}):
                result = create_project(
                    parent_directory=temporary,
                    title="Two Scenes",
                    target_length=6000,
                    target_chapters=1,
                    target_scenes=2,
                )
                project_text = (Path(result["path"]) / "project.yaml").read_text(encoding="utf-8")
        self.assertEqual(result["target_chapters"], 1)
        self.assertEqual(result["target_scenes"], 2)
        self.assertIn("target_chapters: 1", project_text)
        self.assertIn("target_scenes: 2", project_text)

    def test_create_location_reports_conflict_without_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "already-exists").mkdir()
            result = validate_project_location(
                mode="create",
                parent_directory=str(root),
                folder_name="already-exists",
            )
        self.assertFalse(result["valid"])
        self.assertTrue(result["writable"])
        self.assertIn("同名", result["conflicts"][0])

    def test_open_location_requires_an_arcvellum_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            invalid = validate_project_location(mode="open", project_root=str(root))
            (root / "project.yaml").write_text("title: test\n", encoding="utf-8")
            valid = validate_project_location(mode="open", project_root=str(root))
        self.assertFalse(invalid["valid"])
        self.assertIn("ArcVellum", invalid["conflicts"][0])
        self.assertTrue(valid["valid"])


if __name__ == "__main__":
    unittest.main()
