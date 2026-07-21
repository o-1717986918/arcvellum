from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.config import default_config
from literary_engineering_studio.opencode_runtime_pool import OpenCodeRuntimePool


class _ProcessManager:
    def __init__(self):
        self.stopped = []

    def stop(self, component_id, *, force=False):
        self.stopped.append((component_id, force))


class _ServerFactory:
    def __init__(self):
        self.starts = []

    def __call__(self, *args, **kwargs):
        factory = self

        class Server:
            def start(self, **start):
                factory.starts.append(start)
                index = len(factory.starts)
                endpoint = SimpleNamespace(
                    base_url=f"http://127.0.0.1:{9000 + index}",
                    username="studio",
                    password="fixture",
                )
                client = SimpleNamespace(health=lambda: {"ok": True}, dispose=lambda: None)
                return SimpleNamespace(
                    endpoint=endpoint,
                    component_id=start["component_id"],
                    profile_path=Path(start["profile_root"]),
                    process=SimpleNamespace(pid=1000 + index),
                    client=client,
                )

        return Server()


class OpenCodeRuntimePoolTests(unittest.TestCase):
    def test_reuses_each_role_but_keeps_profiles_isolated(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "work"
            workspace.mkdir()
            config = default_config()
            config["application"]["data_root"] = str(root / "data")
            manager = _ProcessManager()
            factory = _ServerFactory()
            with (
                patch("literary_engineering_studio.opencode_runtime_pool.locate_opencode", return_value=root / "opencode.exe"),
                patch("literary_engineering_studio.opencode_runtime_pool.OpenCodeServer", side_effect=factory),
            ):
                pool = OpenCodeRuntimePool(config, manager)
                first = pool.acquire("worker", workspace)
                pool.release(first)
                second = pool.acquire("worker", workspace)
                pool.release(second)
                advisor = pool.acquire("advisor", workspace)
                pool.release(advisor)

                self.assertFalse(first.reused)
                self.assertTrue(second.reused)
                self.assertEqual(first.component_id, second.component_id)
                self.assertNotEqual(first.profile_path, advisor.profile_path)
                self.assertEqual(len(factory.starts), 2)
                self.assertNotEqual(Path(factory.starts[0]["workspace"]), workspace)
                self.assertEqual(Path(factory.starts[0]["workspace"]).name, "service-workspace")
                self.assertEqual(first.client.endpoint.directory, workspace.resolve())
                pool.shutdown()

            self.assertEqual({item[0] for item in manager.stopped}, {"opencode-worker", "opencode-advisor"})

    def test_model_change_restarts_only_idle_role(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "work"
            workspace.mkdir()
            config = default_config()
            config["application"]["data_root"] = str(root / "data")
            manager = _ProcessManager()
            factory = _ServerFactory()
            with (
                patch("literary_engineering_studio.opencode_runtime_pool.locate_opencode", return_value=root / "opencode.exe"),
                patch("literary_engineering_studio.opencode_runtime_pool.OpenCodeServer", side_effect=factory),
            ):
                pool = OpenCodeRuntimePool(config, manager)
                first = pool.acquire("worker", workspace)
                pool.release(first)
                config["agent_runners"]["opencode"]["models"]["worker"] = "deepseek/deepseek-chat"
                second = pool.acquire("worker", workspace)
                pool.release(second)
                self.assertFalse(second.reused)
                self.assertGreater(second.generation, first.generation)
                self.assertIn(("opencode-worker", False), manager.stopped)
                pool.shutdown()


if __name__ == "__main__":
    unittest.main()
