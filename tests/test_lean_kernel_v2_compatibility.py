from __future__ import annotations

import json
import argparse
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.automation.controller import AutopilotService
from literary_engineering_studio.application.scene_transaction_cli import (
    _remaining_steps,
    run_scene_transaction_command,
)
from literary_engineering_studio.compatibility.literary_kernel import (
    initial_kernel_selection,
    kernel_compatibility_manifest,
    mark_studio_created_project,
)
from literary_engineering_studio.persistence.job_store import JobStore
from tests.test_lean_kernel_v2_autopilot_loop import _project
from literary_engineering_studio_engine.public.literary import SceneTransactionStatus


class LeanKernelCompatibilityTests(unittest.TestCase):
    def test_cli_run_step_budget_is_an_integer_and_stops_committed_work(self):
        active = argparse.Namespace(status=SceneTransactionStatus.PREPARED)
        committed = argparse.Namespace(status=SceneTransactionStatus.COMMITTED)

        self.assertEqual(_remaining_steps(active, 12), 12)
        self.assertEqual(_remaining_steps(active, 100), 32)
        self.assertEqual(_remaining_steps(committed, 12), 0)

    def test_manifest_keeps_lean_preview_behind_literary_gate(self):
        manifest = kernel_compatibility_manifest()

        self.assertFalse(manifest["adoption"]["ready_for_default"])
        self.assertEqual(manifest["kernels"]["lean-v2"]["status"], "preview")
        self.assertFalse(manifest["retirement"]["strict-v1"]["deletion_allowed"])

    def test_unmarked_project_preserves_strict_route(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "legacy"
            project.mkdir()
            selection = initial_kernel_selection(project)

        self.assertEqual(selection.kernel, "strict-v1")
        self.assertEqual(selection.source, "legacy-project-fallback")

    def test_studio_project_uses_evidence_gated_recommendation(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "new"
            project.mkdir()
            marker = mark_studio_created_project(project)
            selection = initial_kernel_selection(project)

            marker_payload = json.loads(marker.read_text(encoding="utf-8"))

        self.assertEqual(marker_payload["schema"], "arcvellum/studio-project-origin/v1")
        self.assertEqual(selection.kernel, "strict-v1")
        self.assertEqual(selection.source, "new-project-evidence-fallback")
        self.assertFalse(selection.ready_for_default)

    def test_explicit_migration_persists_and_rolls_back(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()
            (project / "project.yaml").write_text("title: Migration\n", encoding="utf-8")
            store = JobStore(root / "studio.sqlite3")
            service = AutopilotService({"application": {"data_root": str(root)}}, store)
            self.addCleanup(service.shutdown)

            initial = service.policy(project)["policy"]
            migrated = service.migrate_kernel(
                project,
                target_kernel="lean-v2",
                scene_execution_mode="publication",
            )
            reloaded = service.policy(project)["policy"]
            rolled_back = service.migrate_kernel(project, target_kernel="strict-v1")

        self.assertEqual(initial["literary_kernel"], "strict-v1")
        self.assertEqual(migrated["previous_kernel"], "strict-v1")
        self.assertEqual(migrated["current_kernel"], "lean-v2")
        self.assertEqual(migrated["compatibility_status"], "preview")
        self.assertEqual(reloaded["literary_kernel"], "lean-v2")
        self.assertEqual(reloaded["scene_execution_mode"], "publication")
        self.assertEqual(rolled_back["current_kernel"], "strict-v1")

    def test_cli_prepares_and_reads_the_same_durable_transaction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            _project(project)
            (project / "project.yaml").write_text("title: Diagnostics\n", encoding="utf-8")
            config = {
                "application": {
                    "data_root": str(root / "data"),
                    "database_path": str(root / "studio.sqlite3"),
                    "max_workers": 1,
                    "lease_seconds": 90,
                }
            }
            prepared_output = StringIO()
            with redirect_stdout(prepared_output):
                result = run_scene_transaction_command(
                    argparse.Namespace(
                        command="scene-transaction-prepare",
                        project=str(project),
                        scene="scene_0001",
                        mode="standard",
                    ),
                    config,
                )
            prepared = json.loads(prepared_output.getvalue())
            status_output = StringIO()
            with redirect_stdout(status_output):
                status_result = run_scene_transaction_command(
                    argparse.Namespace(
                        command="scene-transaction-status",
                        project=str(project),
                        transaction_id=prepared["transaction"]["transaction_id"],
                        scene="",
                        limit=20,
                    ),
                    config,
                )
            status = json.loads(status_output.getvalue())

        self.assertEqual(result, 0)
        self.assertEqual(status_result, 0)
        self.assertEqual(prepared["transaction"]["status"], "prepared")
        self.assertEqual(status["items"][0]["transaction_id"], prepared["transaction"]["transaction_id"])


if __name__ == "__main__":
    unittest.main()
