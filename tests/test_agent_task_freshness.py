from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.agent_tasks import (
    agent_task_digest,
    agent_task_completion_status,
    write_agent_completion_marker,
    write_agent_tasks,
)
from literary_engineering_studio_engine.word_budget import build_word_budget


class AgentTaskFreshnessTests(unittest.TestCase):
    def test_reissued_task_invalidates_older_completion_marker(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = root / "branches" / "scene_0001" / "roleplay_simulation.agent_tasks.md"
            task.parent.mkdir(parents=True)
            task.write_text("first task\n", encoding="utf-8")
            completion = task.with_name("roleplay_simulation.agent_completion.json")
            completion.write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/agent-task-completion/v1",
                        "source_task": "branches/scene_0001/roleplay_simulation.agent_tasks.md",
                        "status": "complete",
                        "handled_by": "legacy-agent",
                        "completed_at": "2026-01-01T00:00:00+00:00",
                        "expected_artifacts_checked": True,
                        "notes": [],
                    }
                ),
                encoding="utf-8",
            )
            os.utime(completion, ns=(1_000_000_000, 1_000_000_000))
            os.utime(task, ns=(2_000_000_000, 2_000_000_000))

            status = agent_task_completion_status(task, root=root)

            self.assertFalse(status["complete"])
            self.assertEqual(status["status"], "stale_completion")
            self.assertIn("predates", str(status["message"]))

    def test_identical_task_render_does_not_invalidate_completion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = root / "plot" / "word_budget" / "word_budget.agent_tasks.md"
            write_agent_tasks(
                task,
                title="budget",
                root=root,
                source_paths=[],
                tasks=[("review", "read the budget")],
            )
            completion = write_agent_completion_marker(task, root=root)
            completion_time = completion.stat().st_mtime_ns
            write_agent_tasks(
                task,
                title="budget",
                root=root,
                source_paths=[],
                tasks=[("review", "read the budget")],
            )

            status = agent_task_completion_status(task, root=root)

            self.assertTrue(status["complete"])
            self.assertEqual(completion_time, completion.stat().st_mtime_ns)

    def test_explicit_reissue_refreshes_identity_preserving_task(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = root / "reviews" / "agent" / "canon_review.agent_tasks.md"
            arguments = {
                "title": "canon review",
                "root": root,
                "source_paths": [],
                "tasks": [("review", "inspect current evidence")],
            }
            write_agent_tasks(task, **arguments)
            original_digest = agent_task_digest(task)
            os.utime(task, ns=(1_000_000_000, 1_000_000_000))

            write_agent_tasks(task, **arguments, reissue=True)

            self.assertEqual(agent_task_digest(task), original_digest)
            self.assertGreater(task.stat().st_mtime_ns, 1_000_000_000)

    def test_digest_receipt_rejects_changed_task_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = root / "branches" / "scene_0001" / "roleplay_simulation.agent_tasks.md"
            write_agent_tasks(
                task,
                title="roleplay",
                root=root,
                source_paths=[],
                tasks=[("propose", "first instruction")],
            )
            write_agent_completion_marker(task, root=root)
            write_agent_tasks(
                task,
                title="roleplay",
                root=root,
                source_paths=[],
                tasks=[("propose", "changed instruction")],
            )

            status = agent_task_completion_status(task, root=root)

            self.assertFalse(status["complete"])
            self.assertEqual(status["status"], "stale_completion")
            self.assertIn("different task revision", str(status["message"]))

    def test_repeated_word_budget_does_not_expire_completed_budget_task(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: Test\ntarget_length: 120000\n", encoding="utf-8")
            (root / "plot").mkdir()
            (root / "plot" / "outline.md").write_text("# Outline\n", encoding="utf-8")
            first = build_word_budget(root, target_words=120000)
            write_agent_completion_marker(first.agent_tasks_path, root=root)

            second = build_word_budget(root, target_words=120000)
            status = agent_task_completion_status(second.agent_tasks_path, root=root)

            self.assertTrue(status["complete"])
            self.assertEqual(status["status"], "complete")


if __name__ == "__main__":
    unittest.main()
