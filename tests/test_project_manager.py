from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.project_manager import validate_project_location


class ProjectLocationTests(unittest.TestCase):
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
