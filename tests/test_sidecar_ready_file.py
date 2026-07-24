import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.request import Request, urlopen


@unittest.skipUnless(__import__("importlib").util.find_spec("uvicorn"), "Uvicorn is not installed")
class SidecarReadyFileTests(unittest.TestCase):
    def test_port_zero_sidecar_publishes_nonce_bound_ready_file_and_authenticated_health(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ready_file = root / "sidecar-ready.json"
            token = "test-sidecar-token"
            nonce = "test-sidecar-nonce"
            environment = {
                **os.environ,
                "LES_DATA_ROOT": str(root / "data"),
                "LES_CONFIG_PATH": str(root / "config.json"),
                "LES_API_TOKEN": token,
                "LES_STARTUP_NONCE": nonce,
            }
            # A configured port makes it observable that the desktop-only
            # ``--port 0`` contract does not silently fall back to config.
            (root / "config.json").write_text(
                json.dumps({"server": {"host": "127.0.0.1", "port": 43121}}),
                encoding="utf-8",
            )
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "literary_engineering_studio.cli",
                    "serve",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "0",
                    "--ready-file",
                    str(ready_file),
                ],
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline and not ready_file.is_file() and process.poll() is None:
                    time.sleep(0.05)
                self.assertIsNone(process.poll(), "sidecar exited before readiness")
                self.assertTrue(ready_file.is_file(), "sidecar did not publish a ready file")
                payload = json.loads(ready_file.read_text(encoding="utf-8"))
                self.assertEqual(payload["application_id"], "arcvellum-studio")
                self.assertEqual(payload["protocol_version"], "arcvellum-sidecar/v1")
                self.assertEqual(payload["startup_nonce"], nonce)
                self.assertNotEqual(payload["port"], 43121)
                request = Request(
                    f"http://127.0.0.1:{payload['port']}/health",
                    headers={"Authorization": f"Bearer {token}"},
                )
                with urlopen(request, timeout=5) as response:
                    health = json.loads(response.read().decode("utf-8"))
                self.assertTrue(health["ok"])
                self.assertEqual(health["startup_nonce"], nonce)
                self.assertEqual(health["application_id"], "arcvellum-studio")
            finally:
                process.terminate()
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=8)


if __name__ == "__main__":
    unittest.main()
