import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.config import default_config
from literary_engineering_studio.contracts import load_task_package
from literary_engineering_studio.runtime.sandbox import stage_task
from literary_engineering_studio.worker import AgentWorker


class WorkerRecoveryTests(unittest.TestCase):
    def test_recovery_rejects_a_sandbox_without_fresh_agent_output(self):
        """A timed-out task must not resubmit an output copied into its baseline."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: recovery fixture\n", encoding="utf-8")
            task_dir = root / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            markdown = task_dir / "review.agent_tasks.md"
            markdown.write_text("# Review\n", encoding="utf-8")
            task_json = task_dir / "review.task.json"
            task_json.write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/agent-task/v1",
                        "task_id": "review",
                        "status": "opened",
                        "route": "scene-development",
                        "current_state": "candidate-review",
                        "task_type": "platform-agent-review",
                        "prompt_asset_id": "route.scene-development.review.v1",
                        "required_reading": [],
                        "source_paths": [],
                        "expected_outputs": ["reviews/agent/scene_0001_scene_review.json"],
                        "submission_command": "lew task-submit",
                        "completion_command": "lew task-complete",
                        "validation_gates": [],
                        "forbidden_shortcuts": [],
                        "task_markdown": "workflow/tasks/review.agent_tasks.md",
                    }
                ),
                encoding="utf-8",
            )
            task = load_task_package(root, task_json)
            sandbox = stage_task(task, root / "runs", runtime="opencode")

            with self.assertRaisesRegex(ValueError, "fresh Agent-authored expected outputs"):
                AgentWorker(default_config()).resume_from_run(sandbox.run_root)


if __name__ == "__main__":
    unittest.main()
