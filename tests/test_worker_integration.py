from pathlib import Path
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.config import default_config
from literary_engineering_studio.core_read_models import install_core_import_path
from literary_engineering_studio.project_manager import record_direction
from literary_engineering_studio.worker import AgentWorker, _resolve_task_json_path


class WorkerIntegrationTests(unittest.TestCase):
    def test_archaeology_fan_in_runs_in_deterministic_control_workspace(self):
        config = default_config()
        install_core_import_path(config)
        from literary_engineering_studio_engine.agent_tasks import (
            write_agent_completion_marker,
        )
        from literary_engineering_studio_engine.literary.ingest import (
            CHUNK_EXTRACTION_SCHEMA,
        )
        from literary_engineering_studio_engine.projects.source_ingest import (
            ingest_existing_work,
        )

        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            project = temporary_root / "work"
            project.mkdir()
            (project / "project.yaml").write_text(
                "schema: test-project\n",
                encoding="utf-8",
            )
            result = ingest_existing_work(
                project,
                text="# 第一章\n甲抵达城门。\n\n# 第二章\n甲离开城门。\n",
                work_id="source-work",
                rights_declaration="Authorized test source.",
            )
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            chunks = {
                item["chunk_id"]: item
                for item in manifest["chunks"]
            }
            for item in manifest["archaeology"]["chunk_tasks"]:
                chunk = chunks[item["chunk_id"]]
                source = project / item["source_chunk_path"]
                output = project / item["expected_output"]
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(
                    json.dumps(
                        {
                            "schema": CHUNK_EXTRACTION_SCHEMA,
                            "work_id": "source-work",
                            "chunk_id": item["chunk_id"],
                            "source_chunk_path": item["source_chunk_path"],
                            "source_chunk_sha256": hashlib.sha256(
                                source.read_bytes()
                            ).hexdigest(),
                            "evidence_revision": manifest["evidence_index"]["revision"],
                            "status": "complete",
                            "entities": [],
                            "events": [],
                            "relations": [],
                            "claims": [],
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                write_agent_completion_marker(
                    project / item["task_path"],
                    root=project,
                    handled_by="test-worker",
                )
            config["worker"]["runs_root"] = str(temporary_root / "runs")

            with patch(
                "literary_engineering_studio.worker.build_runtime",
                side_effect=AssertionError("runtime must not run"),
            ):
                worker_result = AgentWorker(config).run_once(
                    project,
                    route="source-ingest",
                    runtime_id="opencode",
                )

            self.assertEqual(worker_result.status, "complete")
            self.assertEqual(worker_result.runtime, "deterministic-engine")
            aggregate = json.loads(
                (project / manifest["archaeology"]["aggregate_path"]).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(aggregate["fan_in"]["status"], "ready")

    def test_resolves_canonical_task_when_reported_chinese_path_is_mojibake(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "你好，新世界"
            task = project / "workflow" / "tasks" / "planning-demo.task.json"
            task.parent.mkdir(parents=True)
            task.write_text("{}\n", encoding="utf-8")
            resolved = _resolve_task_json_path(
                project,
                "planning-demo",
                r"C:\Users\Fold\Documents\ArcVellum\Works\���K��������\workflow\tasks\planning-demo.task.json",
            )
            self.assertEqual(resolved, task.resolve())

    def test_rejects_invalid_task_identity_before_path_resolution(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            with self.assertRaisesRegex(ValueError, "invalid task id"):
                _resolve_task_json_path(project, "../outside", "")

    def test_asset_intake_runs_concrete_seed_command_and_writes_sidecars(self):
        config = default_config()
        install_core_import_path(config)
        from literary_engineering_studio_engine.init_project import InitOptions, init_work_project

        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            project = temporary_root / "work"
            init_work_project(InitOptions(target=project, title="Asset Seed Verification", target_length=50000))
            config["worker"]["runs_root"] = str(temporary_root / "runs")
            with (
                patch("literary_engineering_studio.worker.build_runtime", side_effect=AssertionError("runtime must not run")),
                patch(
                    "literary_engineering_studio.core_bridge.CoreBridge.route_audit",
                    side_effect=AssertionError("full route audit must not run after every exact task"),
                ),
            ):
                result = AgentWorker(config).run_once(
                    project,
                    route="character-and-world-assets",
                    runtime_id="opencode",
                )
            self.assertEqual(result.status, "complete")
            self.assertTrue((project / "canon/candidates/world_rules/world-foundation.agent_tasks.md").is_file())
            self.assertTrue((project / "characters/candidates/protagonist-foundation.agent_tasks.md").is_file())

    def test_deterministic_task_runs_in_sandbox_without_agent_runtime(self):
        config = default_config()
        install_core_import_path(config)
        from literary_engineering_studio_engine.init_project import InitOptions, init_work_project

        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            project = temporary_root / "work"
            init_work_project(InitOptions(target=project, title="Deterministic Worker Verification", target_length=30000))
            config["worker"]["runs_root"] = str(temporary_root / "runs")
            with patch("literary_engineering_studio.worker.build_runtime", side_effect=AssertionError("runtime must not run")):
                result = AgentWorker(config).run_once(
                    project,
                    route="longform-planning",
                    runtime_id="opencode",
                )
            self.assertEqual(result.status, "complete")
            self.assertEqual(result.runtime, "deterministic-engine")
            # Longform planning now starts with the candidate story
            # architecture.  A word budget is intentionally unavailable until
            # that architecture receives independent review.
            self.assertTrue((project / "plot" / "story_architecture.candidate.json").is_file())
            self.assertTrue((project / "plot" / "story_architecture.agent_tasks.md").is_file())
            self.assertFalse((project / "plot" / "word_budget" / "word_budget.json").exists())

    def test_prepares_real_core_task_for_host_agent(self):
        config = default_config()
        install_core_import_path(config)
        from literary_engineering_studio_engine.init_project import InitOptions, init_work_project

        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            project = temporary_root / "work"
            init_work_project(InitOptions(target=project, title="Studio Worker Verification", target_length=50000))
            record_direction(project, "优先建立人物关系压力，不要提前解释核心谜底。")
            config["worker"]["runs_root"] = str(temporary_root / "runs")
            task, sandbox, terminal = AgentWorker(config).prepare(
                project,
                route="longform-planning",
                runtime_id="host-agent",
            )
            self.assertIsNone(terminal)
            self.assertIsNotNone(task)
            self.assertIsNotNone(sandbox)
            self.assertFalse(sandbox.prompt_path.exists())
            self.assertFalse((sandbox.workspace / "_task").exists())
            self.assertFalse((sandbox.workspace / "TASK_CONTEXT.json").exists())
            self.assertFalse((sandbox.workspace / "workflow" / "studio" / "user_directions.md").exists())
            # This first longform task is CLI-owned.  Its scaffold belongs to
            # the control workspace until the state machine issues the
            # following Agent task; exposing it early would blur the
            # command/Agent boundary again.
            self.assertTrue((sandbox.control_workspace / "plot" / "story_architecture.candidate.json").is_file())
            self.assertTrue((sandbox.control_workspace / "plot" / "story_architecture.agent_tasks.md").is_file())
            self.assertFalse((sandbox.workspace / "plot" / "story_architecture.candidate.json").exists())
            self.assertFalse((sandbox.workspace / "plot" / "story_architecture.agent_tasks.md").exists())
            self.assertFalse((project / "plot" / "story_architecture.candidate.json").exists())
            self.assertFalse((project / "plot" / "word_budget" / "word_budget.json").exists())
            manifest = json.loads(sandbox.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["missing_sources"], [])
            self.assertTrue(manifest["agent_workspace_deferred"])
            self.assertIn("execution_policy", manifest["execution_contract"])
            self.assertFalse(manifest["execution_contract"]["compatibility_derived"])
            self.assertEqual(task.route, "longform-planning")
            self.assertIn("prompt_asset", task.payload)


if __name__ == "__main__":
    unittest.main()
