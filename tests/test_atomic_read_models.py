from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.core_read_models import _read_json_with_retry
from literary_engineering_studio_engine.atomic_io import atomic_write_text


class AtomicReadModelTests(unittest.TestCase):
    def test_atomic_writer_replaces_json_without_leaving_temporary_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "workflow_dashboard.json"
            atomic_write_text(path, '{"version": 1}\n')
            atomic_write_text(path, '{"version": 2, "ready": true}\n')
            self.assertEqual(_read_json_with_retry(path), {"version": 2, "ready": True})
            self.assertEqual(list(path.parent.glob(f".{path.name}.*.tmp")), [])

    def test_reader_retries_a_transient_partial_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "workflow_dashboard.json"
            path.write_text('{"ready": true}', encoding="utf-8")
            original = Path.read_text
            calls = {"count": 0}

            def transient_read(target, *args, **kwargs):
                if target == path and calls["count"] == 0:
                    calls["count"] += 1
                    return "{"
                return original(target, *args, **kwargs)

            with patch.object(Path, "read_text", transient_read):
                self.assertEqual(_read_json_with_retry(path, delay_seconds=0), {"ready": True})
            self.assertEqual(calls["count"], 1)


if __name__ == "__main__":
    unittest.main()
