import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.project_manager import (
    create_project,
    list_projects,
    read_directions,
    record_direction,
)


class ProjectManagerTests(unittest.TestCase):
    def test_create_register_and_record_direction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = root / "studio" / "config.json"
            with patch.dict(os.environ, {"LES_CONFIG_PATH": str(config_path)}):
                project = create_project(
                    parent_directory=str(root),
                    title="潮汐档案",
                    folder_name="tide-archive",
                    target_length=500000,
                    premise="一座海港城市逐年遗忘自己的历史。",
                    genre="悬疑",
                )
                project_root = Path(project["path"])
                self.assertTrue((project_root / "project.yaml").is_file())
                self.assertEqual(project["title"], "潮汐档案")
                self.assertEqual(list_projects()["current_project"], str(project_root))

                record_direction(project_root, "第一卷保持克制，不要过早揭露城市失忆的原因。")
                directions = read_directions(project_root)
                self.assertEqual(len(directions), 1)
                self.assertIn("不要过早揭露", directions[0]["message"])
                self.assertTrue((project_root / "workflow" / "studio" / "user_directions.md").is_file())


if __name__ == "__main__":
    unittest.main()
