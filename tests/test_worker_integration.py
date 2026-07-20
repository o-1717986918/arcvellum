from pathlib import Path
import json
import tempfile
import unittest

from literary_engineering_studio.config import default_config
from literary_engineering_studio.core_read_models import install_core_import_path
from literary_engineering_studio.project_manager import record_direction
from literary_engineering_studio.worker import AgentWorker


class WorkerIntegrationTests(unittest.TestCase):
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
            self.assertTrue((sandbox.workspace / "workflow" / "studio" / "user_directions.md").is_file())
            manifest = json.loads(sandbox.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["missing_sources"], [])
            self.assertEqual(task.route, "longform-planning")


if __name__ == "__main__":
    unittest.main()
