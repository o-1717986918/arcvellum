from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.config import default_config
from literary_engineering_studio.core_read_models import install_core_import_path
from literary_engineering_studio.project_manager import record_direction
from literary_engineering_studio.worker import AgentWorker, _resolve_task_json_path


class WorkerIntegrationTests(unittest.TestCase):
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
            self.assertTrue((project / "plot" / "word_budget" / "word_budget.json").is_file())

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
            self.assertTrue(sandbox.prompt_path.is_file())
            self.assertTrue((sandbox.workspace / "_task" / "task.json").is_file())
            self.assertTrue((sandbox.workspace / "_task" / "execution_contract.json").is_file())
            self.assertTrue((sandbox.workspace / "TASK_CONTEXT.json").is_file())
            self.assertTrue((sandbox.workspace / "workflow" / "studio" / "user_directions.md").is_file())
            self.assertTrue((sandbox.workspace / "plot" / "word_budget" / "word_budget.json").is_file())
            self.assertFalse((project / "plot" / "word_budget" / "word_budget.json").exists())
            manifest = json.loads(sandbox.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["missing_sources"], [])
            self.assertIn("execution_policy", manifest["execution_contract"])
            self.assertFalse(manifest["execution_contract"]["compatibility_derived"])
            self.assertEqual(task.route, "longform-planning")
            self.assertIn("prompt_asset", task.payload)
            prompt_text = sandbox.prompt_path.read_text(encoding="utf-8")
            self.assertIn("# ArcVellum Studio Worker Program", prompt_text)
            self.assertIn("## Hard Constraints", prompt_text)
            self.assertIn("## Review Requirements", prompt_text)
            self.assertIn("## Forbidden Shortcuts", prompt_text)
            self.assertIn("## Allowed Outputs", prompt_text)
            self.assertNotIn("## Agent Execution", prompt_text)
            self.assertNotIn("推荐提交命令", prompt_text)


if __name__ == "__main__":
    unittest.main()
