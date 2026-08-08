from __future__ import annotations

import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from literary_engineering_studio.application.config import default_config
from literary_engineering_studio.automation.controller import AutopilotService
from literary_engineering_studio.automation.policy import default_policy
from literary_engineering_studio.jobs import JobStore
from literary_engineering_studio.runtime.worker import WorkerRunResult


class AutopilotCampaignIntegrationTests(unittest.TestCase):
    def test_formal_progress_commits_due_checkpoint_in_existing_run(self):
        class ProgressWorker:
            calls = 0

            def __init__(self, config, **kwargs):
                self.config = config

            def run_once(self, project, *, route, runtime_id):
                self.__class__.calls += 1
                if self.__class__.calls == 1:
                    output = project / "plot" / "word_budget.json"
                    output.parent.mkdir()
                    output.write_text('{"target":500000}\n', encoding="utf-8")
                    return WorkerRunResult(
                        "complete",
                        project,
                        route,
                        "word-budget",
                        runtime_id,
                        None,
                        None,
                        "budget created",
                    )
                return WorkerRunResult(
                    "route_ready",
                    project,
                    route,
                    "",
                    runtime_id,
                    None,
                    None,
                    "route ready",
                )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = _project(root)
            config = _campaign_config(root, interval=1)
            store = JobStore(root / "studio.sqlite3")
            policy = default_policy("supervised_auto")
            run = store.create_autopilot_run(
                str(project.resolve()),
                mode="supervised_auto",
                runtime="opencode",
                policy=policy,
            )
            service = AutopilotService(config, store)

            with (
                patch(
                    "literary_engineering_studio.automation.controller.AgentWorker",
                    ProgressWorker,
                ),
                patch(
                    "literary_engineering_studio.automation.controller.current_choices",
                    return_value={"choices": []},
                ),
                patch(
                    "literary_engineering_studio.automation.controller.ROUTE_ORDER",
                    ("longform-planning",),
                ),
            ):
                service._run_claimed(run["run_id"], threading.Event())

            completed = store.read_autopilot_run(run["run_id"])
            events = store.autopilot_events_since(run["run_id"])
            checkpoints = [
                item
                for item in events
                if item["event"] == "campaign.checkpoint.created"
            ]
            self.assertEqual(completed["tasks_completed"], 1)
            self.assertEqual(len(checkpoints), 2)
            self.assertEqual(checkpoints[-1]["data"]["completed_steps"], 1)
            self.assertTrue(
                any(
                    item["event"] == "campaign.checkpoint.committed"
                    for item in events
                )
            )

    def test_touch_only_worker_is_stopped_as_no_progress(self):
        class TouchWorker:
            def __init__(self, config, **kwargs):
                self.config = config

            def run_once(self, project, *, route, runtime_id):
                target = project / "project.yaml"
                stat = target.stat()
                os.utime(
                    target,
                    ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000),
                )
                return WorkerRunResult(
                    "complete",
                    project,
                    route,
                    "touch-only",
                    runtime_id,
                    None,
                    None,
                    "touched",
                )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = _project(root)
            config = _campaign_config(root, interval=1)
            store = JobStore(root / "studio.sqlite3")
            policy = default_policy("full_auto")
            run = store.create_autopilot_run(
                str(project.resolve()),
                mode="full_auto",
                runtime="opencode",
                policy=policy,
            )
            service = AutopilotService(config, store)

            with (
                patch(
                    "literary_engineering_studio.automation.controller.AgentWorker",
                    TouchWorker,
                ),
                patch(
                    "literary_engineering_studio.automation.controller.current_choices",
                    return_value={"choices": []},
                ),
                patch(
                    "literary_engineering_studio.automation.controller.ROUTE_ORDER",
                    ("longform-planning",),
                ),
            ):
                service._run_claimed(run["run_id"], threading.Event())

            stopped = store.read_autopilot_run(run["run_id"])
            events = store.autopilot_events_since(run["run_id"])
            self.assertEqual(stopped["status"], "paused")
            self.assertEqual(stopped["stop_reason"], "no-progress")
            self.assertEqual(stopped["tasks_completed"], 0)
            recovery_steps = [
                item["data"]["step"]
                for item in events
                if item["event"] == "campaign.recovery.selected"
            ]
            self.assertEqual(
                recovery_steps,
                ["bounded-replan", "stop-with-evidence"],
            )

    def test_runtime_recovery_rejects_checkpoint_after_formal_drift(self):
        class DriftingFailureWorker:
            resume_calls = 0

            def __init__(self, config, **kwargs):
                self.config = config

            def run_once(self, project, *, route, runtime_id):
                (project / "project.yaml").write_text(
                    "title: Drifted\n", encoding="utf-8"
                )
                run_root = project.parent / "run-failed"
                return WorkerRunResult(
                    "runtime_failed",
                    project,
                    route,
                    "failing-task",
                    runtime_id,
                    run_root,
                    run_root / "workspace",
                    "runtime disconnected",
                )

            def resume_from_run(self, run_root):
                self.__class__.resume_calls += 1
                raise AssertionError("drifted checkpoint must block sandbox resume")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = _project(root)
            config = _campaign_config(root, interval=1)
            store = JobStore(root / "studio.sqlite3")
            policy = default_policy("full_auto")
            policy["limits"]["max_failures_per_task"] = 0
            run = store.create_autopilot_run(
                str(project.resolve()),
                mode="full_auto",
                runtime="opencode",
                policy=policy,
            )
            service = AutopilotService(config, store)

            with (
                patch(
                    "literary_engineering_studio.automation.controller.AgentWorker",
                    DriftingFailureWorker,
                ),
                patch(
                    "literary_engineering_studio.automation.controller.current_choices",
                    return_value={"choices": []},
                ),
                patch(
                    "literary_engineering_studio.automation.controller.ROUTE_ORDER",
                    ("longform-planning",),
                ),
            ):
                service._run_claimed(run["run_id"], threading.Event())

            events = store.autopilot_events_since(run["run_id"])
            rejected = [
                item
                for item in events
                if item["event"] == "task.recovery_rejected"
            ]
            self.assertEqual(DriftingFailureWorker.resume_calls, 0)
            self.assertEqual(
                rejected[-1]["data"]["reason"],
                "checkpoint-project-drift",
            )

    def test_runtime_failure_replans_once_then_stops_with_evidence(self):
        class AlwaysFailingWorker:
            def __init__(self, config, **kwargs):
                self.config = config

            def run_once(self, project, *, route, runtime_id):
                run_root = project.parent / "run-failed"
                return WorkerRunResult(
                    "runtime_failed",
                    project,
                    route,
                    "failing-task",
                    runtime_id,
                    run_root,
                    run_root / "workspace",
                    "runtime disconnected",
                )

            def resume_from_run(self, run_root):
                raise ValueError("sandbox incomplete")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = _project(root)
            config = _campaign_config(root, interval=1)
            store = JobStore(root / "studio.sqlite3")
            policy = default_policy("full_auto")
            policy["limits"]["max_failures_per_task"] = 10
            run = store.create_autopilot_run(
                str(project.resolve()),
                mode="full_auto",
                runtime="opencode",
                policy=policy,
            )
            service = AutopilotService(config, store)

            with (
                patch(
                    "literary_engineering_studio.automation.controller.AgentWorker",
                    AlwaysFailingWorker,
                ),
                patch(
                    "literary_engineering_studio.automation.controller.current_choices",
                    return_value={"choices": []},
                ),
                patch(
                    "literary_engineering_studio.automation.controller.ROUTE_ORDER",
                    ("longform-planning",),
                ),
            ):
                service._run_claimed(run["run_id"], threading.Event())

            stopped = store.read_autopilot_run(run["run_id"])
            events = store.autopilot_events_since(run["run_id"])
            steps = [
                item["data"]["step"]
                for item in events
                if item["event"] == "campaign.recovery.selected"
            ]
            self.assertEqual(
                steps,
                ["checkpoint-restore", "bounded-replan", "stop-with-evidence"],
            )
            self.assertEqual(stopped["status"], "paused")
            self.assertEqual(stopped["stop_reason"], "recovery-exhausted")
            self.assertEqual(
                len(
                    [
                        item
                        for item in events
                        if item["event"] == "campaign.replan.requested"
                    ]
                ),
                1,
            )


def _project(root: Path) -> Path:
    project = root / "project"
    project.mkdir()
    (project / "project.yaml").write_text("title: Test\n", encoding="utf-8")
    return project


def _campaign_config(root: Path, *, interval: int) -> dict:
    config = default_config()
    config["application"]["data_root"] = str(root)
    config["orchestration"].update(
        {
            "enabled": True,
            "mode": "assisted",
            "campaign_runtime": True,
            "campaign_checkpoint_interval_steps": interval,
        }
    )
    return config


if __name__ == "__main__":
    unittest.main()
