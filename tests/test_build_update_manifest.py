from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "packaging" / "build_update_manifest.py"
SPEC = importlib.util.spec_from_file_location("arcvellum_build_update_manifest", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
_remove_stale_outputs = MODULE._remove_stale_outputs


class BuildUpdateManifestTests(unittest.TestCase):
    def test_locked_stale_installer_does_not_block_current_release(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            locked = output / "ArcVellum_0.95.0_x64-setup.exe"
            ordinary = output / "notes.txt"
            locked.write_bytes(b"old")
            ordinary.write_text("keep", encoding="utf-8")
            original_unlink = Path.unlink

            def simulated_unlink(path: Path, *args, **kwargs):
                if path == locked:
                    raise PermissionError("held open")
                return original_unlink(path, *args, **kwargs)

            with patch.object(Path, "unlink", simulated_unlink):
                retained = _remove_stale_outputs(output)

            self.assertEqual(retained, [locked.name])
            self.assertTrue(locked.exists())
            self.assertTrue(ordinary.exists())


if __name__ == "__main__":
    unittest.main()
