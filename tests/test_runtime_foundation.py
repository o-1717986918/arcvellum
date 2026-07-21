from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from literary_engineering_studio.config import default_config
from literary_engineering_studio.lifecycle import ApplicationLifecycleManager
from literary_engineering_studio.process_manager import ProcessSpec
from literary_engineering_studio.runtimes.base import AgentRuntime


class FakeAgentRunner(AgentRuntime):
    runtime_id = "fake-runner"

    def build_command(self, workspace: Path):
        return (
            sys.executable,
            "-c",
            "import sys; print('fake-runner:' + sys.stdin.read().strip())",
        )


class RuntimeFoundationTests(unittest.TestCase):
    def test_fake_runner_executes_and_records_local_events(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            workspace.mkdir()
            prompt = root / "prompt.md"
            prompt.write_text("perform fixture", encoding="utf-8")
            runner = FakeAgentRunner({"executable": sys.executable})
            result = runner.execute(workspace, prompt, root, timeout=10)
            self.assertEqual(result.status, "completed")
            self.assertIn("fake-runner:perform fixture", result.output_path.read_text(encoding="utf-8"))
            self.assertTrue((root / "runtime.events.jsonl").is_file())

    def test_lifecycle_health_uses_durable_components(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = default_config()
            config["application"]["database_path"] = str(Path(temporary) / "studio.sqlite3")
            lifecycle = ApplicationLifecycleManager(config)
            health = lifecycle.health()
            lifecycle.shutdown()
            self.assertTrue(health["ready"])
            self.assertTrue(health["job_store"]["ready"])
            self.assertIn("worker_id", health["worker_supervisor"])
            self.assertIn("agent_runners", health)
            self.assertIn("model_connections", health)

    def test_lifecycle_health_never_waits_for_slow_runner_probe(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = default_config()
            config["application"]["database_path"] = str(Path(temporary) / "studio.sqlite3")
            started = threading.Event()
            release = threading.Event()

            def slow_status(*_args, **_kwargs):
                started.set()
                release.wait(2)
                return [{"runner_id": "opencode", "available": True}]

            with patch("literary_engineering_studio.lifecycle.agent_runner_status", side_effect=slow_status):
                lifecycle = ApplicationLifecycleManager(config)
                self.assertTrue(started.wait(1))
                before = time.monotonic()
                health = lifecycle.health()
                elapsed = time.monotonic() - before
                self.assertLess(elapsed, 0.2)
                self.assertTrue(health["agent_runner_refreshing"])
                self.assertEqual(len(health["agent_runners"]), 4)
                release.set()
                refreshed = lifecycle.refresh_agent_runners(wait=True, force=False)
                lifecycle.shutdown()
                self.assertEqual(refreshed[0]["runner_id"], "opencode")
                self.assertTrue(refreshed[0]["available"])

    def test_lifecycle_manages_sidecar_start_and_stop(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = default_config()
            config["application"]["data_root"] = str(root)
            config["application"]["database_path"] = str(root / "studio.sqlite3")
            lifecycle = ApplicationLifecycleManager(config)
            record = lifecycle.start_sidecar(
                ProcessSpec(
                    component_id="fake-sidecar",
                    kind="test",
                    command=(sys.executable, "-c", "import time; time.sleep(30)"),
                    cwd=root,
                    environment={},
                )
            )
            self.assertEqual(record.state, "ready")
            self.assertTrue(any(item["component_id"] == "fake-sidecar" for item in lifecycle.health()["managed_processes"]))
            stopped = lifecycle.stop_sidecar("fake-sidecar")
            lifecycle.shutdown()
            self.assertEqual(stopped.state, "stopped")


if __name__ == "__main__":
    unittest.main()
