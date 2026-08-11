from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.integrations.pi_worker.installation import locate_pi_worker


class PiWorkerInstallationTests(unittest.TestCase):
    def test_embedded_paths_override_generic_node_default(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            entrypoint = root / "main.js"
            entrypoint.write_text("", encoding="utf-8")
            with patch.dict(
                os.environ,
                {
                    "LES_PI_WORKER_EXECUTABLE": sys.executable,
                    "LES_PI_WORKER_ENTRYPOINT": str(entrypoint),
                },
                clear=False,
            ):
                installation = locate_pi_worker({"executable": "node", "entrypoint": ""})
                self.assertTrue(installation.available)
                self.assertEqual(installation.executable, str(Path(sys.executable).resolve()))
                self.assertEqual(installation.entrypoint, entrypoint.resolve())
                self.assertEqual(installation.source, "embedded")

    def test_explicit_user_paths_remain_authoritative(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            configured = root / "configured.js"
            embedded = root / "embedded.js"
            configured.write_text("", encoding="utf-8")
            embedded.write_text("", encoding="utf-8")
            with patch.dict(
                os.environ,
                {
                    "LES_PI_WORKER_EXECUTABLE": "missing-embedded-node",
                    "LES_PI_WORKER_ENTRYPOINT": str(embedded),
                },
                clear=False,
            ):
                installation = locate_pi_worker(
                    {"executable": sys.executable, "entrypoint": str(configured)}
                )
                self.assertTrue(installation.available)
                self.assertEqual(installation.entrypoint, configured.resolve())
                self.assertEqual(installation.source, "configured")

    def test_source_checkout_build_is_discovered(self):
        with patch.dict(
            os.environ,
            {"LES_PI_WORKER_EXECUTABLE": "", "LES_PI_WORKER_ENTRYPOINT": ""},
            clear=False,
        ):
            installation = locate_pi_worker({"executable": sys.executable})

        self.assertTrue(installation.available)
        self.assertEqual(installation.source, "source-checkout")
        self.assertEqual(installation.entrypoint.name, "main.js")


if __name__ == "__main__":
    unittest.main()
