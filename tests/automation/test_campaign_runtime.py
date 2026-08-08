from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.automation.campaign_runtime import (
    CampaignRuntimeCoordinator,
    build_checkpoint_payload,
    formal_progress_evidence,
)
from literary_engineering_studio.automation.policy import default_policy
from literary_engineering_studio.jobs import JobStore


class FormalProgressEvidenceTests(unittest.TestCase):
    def test_coordinator_persists_baseline_and_only_due_progress_checkpoint(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = _project(root)
            store = JobStore(root / "studio.sqlite3")
            run = store.create_autopilot_run(
                str(project),
                mode="full_auto",
                runtime="opencode",
                policy=default_policy("full_auto"),
            )
            coordinator = CampaignRuntimeCoordinator(
                store,
                project,
                run["run_id"],
                max_autonomous_steps=50,
                checkpoint_interval_steps=2,
            )

            first = coordinator.ensure_baseline(run)
            second = coordinator.ensure_baseline(run)
            evidence = coordinator.progress_evidence()
            not_due = coordinator.checkpoint_after_progress(
                {**run, "tasks_completed": 1},
                route="longform-planning",
                task_id="task-1",
                evidence=evidence,
                created_at="2026-08-08T00:00:01+00:00",
            )
            due = coordinator.checkpoint_after_progress(
                {**run, "tasks_completed": 2},
                route="longform-planning",
                task_id="task-2",
                evidence=evidence,
                created_at="2026-08-08T00:00:02+00:00",
            )

            self.assertEqual(first["sequence"], second["sequence"])
            self.assertIsNone(not_due)
            self.assertIsNotNone(due)
            events = store.autopilot_events_since(run["run_id"])
            self.assertEqual(
                len(
                    [
                        item
                        for item in events
                        if item["event"] == "campaign.checkpoint.created"
                    ]
                ),
                2,
            )

    def test_restore_rejects_formal_project_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = _project(root)
            store = JobStore(root / "studio.sqlite3")
            run = store.create_autopilot_run(
                str(project),
                mode="full_auto",
                runtime="opencode",
                policy=default_policy("full_auto"),
            )
            coordinator = CampaignRuntimeCoordinator(
                store,
                project,
                run["run_id"],
                max_autonomous_steps=50,
                checkpoint_interval_steps=5,
            )
            coordinator.ensure_baseline(run)
            self.assertEqual(
                coordinator.restore_allowed(),
                (True, "checkpoint-matched"),
            )

            (project / "project.yaml").write_text(
                "title: Changed\n", encoding="utf-8"
            )

            self.assertEqual(
                coordinator.restore_allowed(),
                (False, "checkpoint-project-drift"),
            )

    def test_touch_without_content_change_does_not_create_progress(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(Path(temporary))
            target = project / "plot" / "word_budget.json"
            target.parent.mkdir()
            target.write_text('{"target":500000}\n', encoding="utf-8")
            before = formal_progress_evidence(project, scope_key="book:test")

            stat = target.stat()
            os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
            after = formal_progress_evidence(project, scope_key="book:test")

            self.assertEqual(before.progress, after.progress)
            self.assertEqual(
                before.base_project_fingerprint,
                after.base_project_fingerprint,
            )

    def test_same_length_content_replacement_changes_progress(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(Path(temporary))
            target = project / "canon" / "world_rules.yaml"
            target.parent.mkdir()
            target.write_text("rule: east\n", encoding="utf-8")
            before = formal_progress_evidence(project, scope_key="book:test")

            target.write_text("rule: west\n", encoding="utf-8")
            after = formal_progress_evidence(project, scope_key="book:test")

            self.assertNotEqual(before.progress, after.progress)
            self.assertNotEqual(
                before.base_project_fingerprint,
                after.base_project_fingerprint,
            )

    def test_checkpoint_includes_chapter_only_when_scene_identity_is_provable(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = _project(Path(temporary))
            scenes = project / "scenes"
            scenes.mkdir()
            (scenes / "scene_0001.yaml").write_text(
                "scene_id: scene_0001\nchapter_id: chapter_0001\n",
                encoding="utf-8",
            )
            evidence = formal_progress_evidence(project, scope_key="book:test")

            scene_payload = build_checkpoint_payload(
                project,
                run_id="autopilot-test",
                route="scene-development",
                task_id="scene_0001-agent-review",
                completed_steps=3,
                evidence=evidence,
                created_at="2026-08-08T00:00:00+00:00",
            )
            planning_payload = build_checkpoint_payload(
                project,
                run_id="autopilot-test",
                route="longform-planning",
                task_id="word-budget",
                completed_steps=4,
                evidence=evidence,
                created_at="2026-08-08T00:00:01+00:00",
            )

            self.assertEqual(
                scene_payload["chapter_checkpoint"]["chapter_id"],
                "chapter_0001",
            )
            self.assertNotIn("chapter_checkpoint", planning_payload)
            self.assertEqual(planning_payload["scope_kind"], "book")


def _project(root: Path) -> Path:
    project = root / "project"
    project.mkdir()
    (project / "project.yaml").write_text("title: Test\n", encoding="utf-8")
    return project


if __name__ == "__main__":
    unittest.main()
