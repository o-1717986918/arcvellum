"""Managed sidecars release resources inherited by Windows launcher children."""

import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

from literary_engineering_studio.runtime.process_manager import ProcessManager, ProcessSpec


@unittest.skipUnless(os.name == "nt", "Windows launcher process-tree regression")
class WindowsProcessManagerTests(unittest.TestCase):
    def test_stop_waits_for_launcher_children_and_releases_log(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ready = root / "child-ready"
            child_code = (
                "from pathlib import Path; import time; "
                f"Path({str(ready)!r}).write_text('ready'); time.sleep(30)"
            )
            parent_code = (
                "import subprocess, sys, time; "
                f"subprocess.Popen([sys.executable, '-c', {child_code!r}]); "
                "time.sleep(30)"
            )
            manager = ProcessManager(root / "logs")
            try:
                record = manager.start(ProcessSpec(
                    component_id="launcher-tree",
                    kind="test",
                    command=(sys.executable, "-c", parent_code),
                    cwd=root,
                    environment={},
                ))
                deadline = time.monotonic() + 5
                while not ready.is_file() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(ready.is_file(), "sidecar child did not initialize")
                stopped = manager.stop("launcher-tree")
                self.assertEqual(stopped.state, "stopped")
                self.assertIsNone(stopped.pid)
                renamed = Path(record.log_path).rename(root / "released.log")
                self.assertTrue(renamed.is_file())
            finally:
                manager.shutdown()


if __name__ == "__main__":
    unittest.main()
