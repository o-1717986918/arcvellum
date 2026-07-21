from pathlib import Path
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace

from literary_engineering_studio.bootstrap import ApplicationBootstrapService, BOOTSTRAP_SCHEMA


class _Lifecycle:
    def __init__(self, *, database_ready=True, supervisor_ready=True, runner_available=True):
        self.database_ready = database_ready
        self.supervisor_ready = supervisor_ready
        self.runner_available = runner_available

    def health(self):
        return {
            "ready": self.database_ready,
            "job_store": {"ready": self.database_ready, "job_count": 3},
            "worker_supervisor": {"ready": self.supervisor_ready, "active_jobs": []},
            "agent_runners": [
                {"runner_id": "opencode", "available": self.runner_available},
            ],
        }


class ApplicationBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.services = []

    def tearDown(self):
        for service in self.services:
            service.shutdown()

    def _service(self, **kwargs):
        config = {
            "model_connections": {"connections": []},
            "agent_runners": {"opencode": {"model": "opencode/example-model"}},
        }
        service = ApplicationBootstrapService(config, kwargs.pop("lifecycle", _Lifecycle()), **kwargs)
        self.services.append(service)
        return service

    def test_optional_model_failure_does_not_block_workspace(self):
        def fail_catalog(_config):
            raise RuntimeError("runner unavailable")

        service = self._service(
            catalog_loader=fail_catalog,
            project_loader=lambda: {"current_project": "", "projects": []},
            engine_probe=lambda: SimpleNamespace(returncode=0, stderr=""),
        )
        self.assertTrue(service.start_warmup())
        service._catalog_future.result(timeout=2)
        snapshot = service.snapshot()

        self.assertEqual(snapshot["schema"], BOOTSTRAP_SCHEMA)
        self.assertTrue(snapshot["ready"])
        self.assertTrue(snapshot["can_enter_workspace"])
        self.assertTrue(snapshot["degraded"])
        model_step = next(item for item in snapshot["steps"] if item["id"] == "model_catalog")
        self.assertEqual(model_step["status"], "degraded")
        self.assertFalse(model_step["blocking"])

    def test_failed_core_engine_is_a_real_blocker(self):
        service = self._service(
            catalog_loader=lambda _config: {},
            project_loader=lambda: {"current_project": "", "projects": []},
            engine_probe=lambda: SimpleNamespace(returncode=1, stderr="engine missing"),
        )
        service._engine_future.result(timeout=2)
        snapshot = service.snapshot()

        self.assertFalse(snapshot["ready"])
        self.assertFalse(snapshot["can_enter_workspace"])
        self.assertEqual(snapshot["phase"], "blocked")
        engine_step = next(item for item in snapshot["steps"] if item["id"] == "engine_registry")
        self.assertEqual(engine_step["status"], "blocked")
        self.assertIn("engine missing", engine_step["detail"])

    def test_model_catalog_is_deferred_until_connections_are_opened(self):
        calls = []
        service = self._service(
            catalog_loader=lambda _config: calls.append(1) or {},
            project_loader=lambda: {"current_project": "", "projects": []},
            engine_probe=lambda: SimpleNamespace(returncode=0, stderr=""),
        )

        service._engine_future.result(timeout=2)
        snapshot = service.snapshot()

        self.assertEqual(snapshot["model_warmup"]["status"], "deferred")
        self.assertTrue(snapshot["can_enter_workspace"])
        self.assertEqual(calls, [])

    def test_catalog_warmup_is_single_flight(self):
        entered = threading.Event()
        release = threading.Event()
        calls = []

        def slow_catalog(_config):
            calls.append(1)
            entered.set()
            release.wait(timeout=2)
            return {
                "selected_model": "provider/model",
                "available_model_count": 2,
                "providers": [],
            }

        service = self._service(
            catalog_loader=slow_catalog,
            project_loader=lambda: {"current_project": "", "projects": []},
            engine_probe=lambda: SimpleNamespace(returncode=0, stderr=""),
        )
        self.assertTrue(service.start_warmup())
        self.assertTrue(entered.wait(timeout=1))
        self.assertFalse(service.start_warmup())
        self.assertEqual(service.snapshot()["model_warmup"]["status"], "loading")
        release.set()
        service._catalog_future.result(timeout=2)

        snapshot = service.snapshot()
        self.assertEqual(len(calls), 1)
        self.assertEqual(snapshot["model_warmup"]["status"], "ready")
        self.assertEqual(snapshot["model_catalog"]["selected_model"], "provider/model")

    def test_current_project_is_exposed_without_raw_project_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = str(Path(temporary).resolve())
            service = self._service(
                catalog_loader=lambda _config: {},
                project_loader=lambda: {
                    "current_project": root,
                    "projects": [{"path": root, "title": "长夜来信", "status": "drafting"}],
                },
                engine_probe=lambda: SimpleNamespace(returncode=0, stderr=""),
            )
            service._engine_future.result(timeout=2)
            snapshot = service.snapshot()

        self.assertEqual(snapshot["project"]["title"], "长夜来信")
        self.assertEqual(snapshot["project_count"], 1)
        self.assertNotIn("project.yaml", str(snapshot))

    def test_slow_engine_probe_is_reported_without_blocking_snapshot(self):
        entered = threading.Event()
        release = threading.Event()

        def slow_probe():
            entered.set()
            release.wait(timeout=2)
            return SimpleNamespace(returncode=0, stderr="")

        service = self._service(
            project_loader=lambda: {"current_project": "", "projects": []},
            engine_probe=slow_probe,
        )
        self.assertTrue(entered.wait(timeout=1))
        before = time.monotonic()
        snapshot = service.snapshot()
        self.assertLess(time.monotonic() - before, 0.2)
        self.assertEqual(snapshot["phase"], "starting")
        engine_step = next(item for item in snapshot["steps"] if item["id"] == "engine_registry")
        self.assertEqual(engine_step["status"], "loading")
        release.set()
        service._engine_future.result(timeout=2)
        self.assertTrue(service.snapshot()["can_enter_workspace"])


if __name__ == "__main__":
    unittest.main()
