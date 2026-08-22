from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "packaging" / "pi_worker_bundle.py"
SPEC = importlib.util.spec_from_file_location("arcvellum_pi_worker_bundle", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class PiWorkerBundleTests(unittest.TestCase):
    def _fixture(self, root: Path) -> Path:
        worker = root / "workers" / "pi-worker"
        (worker / "src").mkdir(parents=True)
        (worker / "test").mkdir()
        (worker / "package.json").write_text(
            json.dumps({"name": "@arcvellum/pi-worker", "version": "0.99.0"}),
            encoding="utf-8",
        )
        (worker / "package-lock.json").write_text("{}\n", encoding="utf-8")
        (worker / "tsconfig.build.json").write_text("{}\n", encoding="utf-8")
        (worker / "src" / "main.ts").write_text("export {};\n", encoding="utf-8")
        (worker / "test" / "main.test.ts").write_text("export {};\n", encoding="utf-8")
        destination = root / "desktop" / "src-tauri" / "resources" / "pi-worker"
        (destination / "dist").mkdir(parents=True)
        (destination / "node.exe").write_bytes(b"node-fixture")
        (destination / "dist" / "main.js").write_text("fixture\n", encoding="utf-8")
        return destination

    def test_receipt_detects_stale_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = self._fixture(root)
            payload = MODULE._receipt_payload(root=root, destination=destination)
            (destination / MODULE.RECEIPT_NAME).write_text(
                json.dumps(payload), encoding="utf-8"
            )

            verified = MODULE.verify_bundle(root=root, destination=destination)
            (destination / "dist" / "main.js").write_text("changed\n", encoding="utf-8")

            self.assertEqual(verified["worker_version"], "0.99.0")
            with self.assertRaisesRegex(RuntimeError, "bundle_sha256"):
                MODULE.verify_bundle(root=root, destination=destination)


if __name__ == "__main__":
    unittest.main()
