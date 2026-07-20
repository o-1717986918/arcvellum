import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.contracts import load_task_package, normalize_relative_path


class ContractTests(unittest.TestCase):
    def test_rejects_path_traversal(self):
        for value in ("../secret", "C:/secret", "/absolute/path"):
            with self.assertRaises(ValueError):
                normalize_relative_path(value)

    def test_loads_valid_task(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task_dir = root / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            markdown = task_dir / "demo.agent_tasks.md"
            markdown.write_text("# task\n", encoding="utf-8")
            payload = {
                "schema": "literary-engineering-workbench/agent-task/v1",
                "task_id": "demo",
                "status": "opened",
                "route": "scene-development",
                "current_state": "prose-generation",
                "task_type": "platform-agent-prose",
                "prompt_asset_id": "route.scene-development.prose.generate.v1",
                "required_reading": [],
                "source_paths": ["scenes/scene_0001.yaml"],
                "expected_outputs": ["drafts/candidates/scene_0001.md"],
                "submission_command": "lew task-submit",
                "completion_command": "lew task-complete",
                "validation_gates": [],
                "forbidden_shortcuts": [],
                "task_markdown": "workflow/tasks/demo.agent_tasks.md",
            }
            task_json = task_dir / "demo.task.json"
            task_json.write_text(json.dumps(payload), encoding="utf-8")
            task = load_task_package(root, task_json)
            self.assertEqual(task.task_id, "demo")
            self.assertEqual(task.expected_outputs, ("drafts/candidates/scene_0001.md",))


if __name__ == "__main__":
    unittest.main()

