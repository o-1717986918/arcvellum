from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.task_registry import _enrich_task_payload, revert_task_submission, submit_task


class TaskSubmissionRevertTests(unittest.TestCase):
    def test_reverted_submission_cannot_claim_rolled_back_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: rollback\n", encoding="utf-8")
            output = root / "drafts" / "candidates" / "scene_0001.md"
            output.parent.mkdir(parents=True)
            output.write_text("candidate\n", encoding="utf-8")
            tasks = root / "workflow" / "tasks"
            tasks.mkdir(parents=True)
            task_id = "scene-development-scene_0001-roleplay-agent-task"
            payload = _enrich_task_payload(
                {
                    "schema": "literary-engineering-workbench/agent-task/v1",
                    "task_id": task_id,
                    "status": "opened",
                    "route": "scene-development",
                    "scene_id": "scene_0001",
                    "current_state": "roleplay-agent-task",
                    "task_type": "platform-agent-judgment",
                    "prompt_asset_id": "route.scene-development.roleplay.execute.v1",
                    "command": "",
                    "required_reading": [],
                    "source_paths": ["project.yaml"],
                    "expected_outputs": ["drafts/candidates/scene_0001.md"],
                    "hard_constraints": [],
                    "style_constraints": [],
                    "validation_gates": [],
                    "forbidden_shortcuts": [],
                }
            )
            (tasks / f"{task_id}.task.json").write_text(json.dumps(payload), encoding="utf-8")
            (tasks / f"{task_id}.agent_tasks.md").write_text("# task\n", encoding="utf-8")
            submit_task(root, task_id, [output])
            reverted = revert_task_submission(root, task_id, reason="core gate failed")
            self.assertEqual(reverted.status, "blocked")
            stored = json.loads((tasks / f"{task_id}.task.json").read_text(encoding="utf-8"))
            self.assertNotIn("submission", stored)
            self.assertNotIn("submitted_artifacts", stored)
            self.assertTrue(stored["rollback"]["archived_submission"])
            self.assertTrue((root / stored["rollback"]["archived_submission"]).is_file())


if __name__ == "__main__":
    unittest.main()
