from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.integrations.opencode.opencode_server import (
    OpenCodeServer,
)
from literary_engineering_studio.runtime.process_manager import ProcessRecord


class _ProcessManager:
    def __init__(self) -> None:
        self.spec = None

    def start(self, spec):
        self.spec = spec
        return ProcessRecord(
            component_id=spec.component_id,
            kind=spec.kind,
            state="ready",
            pid=123,
            command=spec.command,
            cwd=str(spec.cwd),
            readiness_url=spec.readiness_url,
            log_path="",
            started_at="",
            updated_at="",
        )


class OpenCodeServerTests(unittest.TestCase):
    def test_windows_home_fallback_is_isolated_inside_studio_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            workspace.mkdir()
            manager = _ProcessManager()
            server = OpenCodeServer(
                manager,
                executable=root / "opencode.exe",
                shared_data_root=root / "studio-data",
            )

            server.start(
                component_id="opencode-worker",
                workspace=workspace,
                run_root=root / "run",
                role="worker",
                model="fixture/model",
            )

            self.assertIsNotNone(manager.spec)
            environment = manager.spec.environment
            expected_home = (root / "studio-data" / "opencode" / "home").resolve()
            self.assertEqual(Path(environment["HOME"]), expected_home)
            self.assertEqual(Path(environment["USERPROFILE"]), expected_home)
            self.assertTrue((expected_home / ".config" / "opencode").is_dir())
            self.assertTrue(Path(environment["XDG_CONFIG_HOME"]).is_relative_to(root))


if __name__ == "__main__":
    unittest.main()
