"""Characterization tests for task registry lifecycle compatibility facades."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from literary_engineering_studio_engine.agent_task_status import build_agent_task_status
from literary_engineering_studio_engine.task_paths import events_path, read_events
from literary_engineering_studio_engine.task_registry import build_workflow_events, issue_next_task, open_task


class TaskLifecycleFacadeTests(unittest.TestCase):
    def test_issue_open_and_event_report_keep_their_file_and_event_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: Lifecycle fixture\n", encoding="utf-8")

            issued = issue_next_task(root, route="character-and-world-assets")
            self.assertEqual(issued.status, "issued")
            self.assertTrue(issued.task_json_path and issued.task_json_path.is_file())
            self.assertTrue(issued.task_markdown_path and issued.task_markdown_path.is_file())
            self.assertEqual(issued.task_json_path.parent.relative_to(root).as_posix(), "workflow/tasks")

            opened = open_task(root, issued.task_id)
            self.assertEqual(opened.status, "opened")
            self.assertEqual(opened.task_id, issued.task_id)
            self.assertEqual(opened.expected_output_count, issued.expected_output_count)

            events = read_events(events_path(root))
            self.assertEqual([entry["event_type"] for entry in events[-2:]], ["task_issued", "task_opened"])
            report = build_workflow_events(root)
            self.assertEqual(report.event_count, len(events))
            self.assertTrue(report.markdown_path.is_file())
            self.assertIn(issued.task_id, report.markdown_path.read_text(encoding="utf-8"))

    def test_successor_task_supersedes_obsolete_active_sidecar_in_the_same_scope(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: Lifecycle fixture\n", encoding="utf-8")
            current = issue_next_task(root, route="character-and-world-assets")
            current_payload = json.loads(current.task_json_path.read_text(encoding="utf-8"))
            stale_id = "character-and-world-assets-project-assets-obsolete"
            stale_json = root / "workflow" / "tasks" / f"{stale_id}.task.json"
            stale_sidecar = root / "workflow" / "tasks" / f"{stale_id}.agent_tasks.md"
            stale_payload = {
                **current_payload,
                "task_id": stale_id,
                "status": "opened",
                "current_state": "obsolete",
                "expected_outputs": ["drafts/obsolete.md"],
            }
            stale_json.write_text(json.dumps(stale_payload, ensure_ascii=False), encoding="utf-8")
            stale_sidecar.write_text(
                "# obsolete\n\n- 创建或覆盖 `drafts/obsolete.md`\n",
                encoding="utf-8",
            )

            returned = issue_next_task(root, route="character-and-world-assets")
            retired = json.loads(stale_json.read_text(encoding="utf-8"))
            status = build_agent_task_status(root)
            events = read_events(events_path(root))

            self.assertEqual(returned.task_id, current.task_id)
            self.assertEqual(retired["status"], "superseded")
            self.assertEqual(retired["superseded_by"], current.task_id)
            self.assertEqual(status.pending_count, 1)
            self.assertTrue(
                any(
                    item.get("event_type") == "task_superseded"
                    and item.get("task_id") == stale_id
                    for item in events
                )
            )


if __name__ == "__main__":
    unittest.main()
