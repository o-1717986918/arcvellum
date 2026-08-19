from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from literary_engineering_studio.api_server import create_app
from literary_engineering_studio.application.container import build_application_container
from literary_engineering_studio.application.ports import ApplicationPorts


def _ports() -> ApplicationPorts:
    store = Mock()
    store.health.return_value = {"ready": True}
    live_events = Mock()
    read_models = Mock()
    prepared_context_cache = Mock()
    prepared_context_cache.status.return_value = {"enabled": False, "entries": 0}
    process_manager = Mock()
    process_manager.status.return_value = []
    runtime_pool = Mock()
    runtime_pool.status.return_value = {"running": 0}
    supervisor = Mock()
    supervisor.health.return_value = {"ready": True}
    return ApplicationPorts(
        store=store,
        live_events=live_events,
        read_models=read_models,
        prepared_context_cache=prepared_context_cache,
        process_manager=process_manager,
        runtime_pool=runtime_pool,
        execution_coordinator=Mock(),
        supervisor=supervisor,
        runtime_ids=("pi-worker",),
        runner_status_loader=lambda _config, **_kwargs: [],
        model_connection_status_loader=lambda _config: {"ready": True},
    )


class ApplicationContainerTests(unittest.TestCase):
    def test_containers_do_not_share_mutable_application_services(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = {
                "application": {
                    "data_root": temporary,
                    "database_path": str(Path(temporary) / "studio.sqlite3"),
                }
            }
            first_ports = _ports()
            second_ports = _ports()
            first = build_application_container(config, first_ports)
            second = build_application_container(config, second_ports)
            self.addCleanup(first.shutdown)
            self.addCleanup(second.shutdown)

            self.assertIsNot(first.services.style_mounts, second.services.style_mounts)
            self.assertIs(first.services.lifecycle.prepared_context_cache, first_ports.prepared_context_cache)
            self.assertIs(second.services.lifecycle.prepared_context_cache, second_ports.prepared_context_cache)
            self.assertIsNot(first.ports.prepared_context_cache, second.ports.prepared_context_cache)

    def test_api_consumes_the_supplied_container(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = {
                "application": {
                    "data_root": temporary,
                    "database_path": str(Path(temporary) / "studio.sqlite3"),
                }
            }
            container = build_application_container(config, _ports())
            self.addCleanup(container.shutdown)

            app = create_app(container=container)

            self.assertIs(app.state.container, container)
            self.assertIs(app.state.lifecycle, container.services.lifecycle)
            self.assertIs(app.state.autopilot, container.services.autopilot)

    def test_api_rejects_two_composition_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = {
                "application": {
                    "data_root": temporary,
                    "database_path": str(Path(temporary) / "studio.sqlite3"),
                }
            }
            container = build_application_container(config, _ports())
            self.addCleanup(container.shutdown)

            with self.assertRaisesRegex(ValueError, "config_override or container"):
                create_app(config, container=container)


if __name__ == "__main__":
    unittest.main()
