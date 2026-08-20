from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

from literary_engineering_studio import read_model_cache
from literary_engineering_studio.read_model_cache import ReadModelCache


class ReadModelCacheTests(unittest.TestCase):
    def test_reuses_same_revision_and_rebuilds_after_project_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "project.yaml").write_text("title: first\n", encoding="utf-8")
            calls = []
            cache = ReadModelCache(ttl_seconds=30)

            def build():
                calls.append(1)
                return {"value": len(calls)}

            self.assertEqual(cache.get("dashboard", project, build)["value"], 1)
            cached = cache.get("dashboard", project, build)
            cached["value"] = 99
            self.assertEqual(cache.get("dashboard", project, build)["value"], 1)
            (project / "project.yaml").write_text("title: changed and longer\n", encoding="utf-8")
            self.assertEqual(cache.get("dashboard", project, build)["value"], 2)

    def test_same_revision_survives_ttl_and_derived_dashboard_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "project.yaml").write_text("title: stable\n", encoding="utf-8")
            calls = []
            cache = ReadModelCache(ttl_seconds=0.1)

            def build():
                calls.append(1)
                dashboard = project / "workflow" / "dashboard" / "workflow_dashboard.json"
                dashboard.parent.mkdir(parents=True, exist_ok=True)
                dashboard.write_text(f'{{"build": {len(calls)}}}\n', encoding="utf-8")
                return {"value": len(calls)}

            self.assertEqual(cache.get("dashboard", project, build)["value"], 1)
            time.sleep(0.12)
            self.assertEqual(cache.get("dashboard", project, build)["value"], 1)
            self.assertEqual(len(calls), 1)

    def test_explicit_invalidation_rebuilds_only_the_target_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first"
            second = Path(temporary) / "second"
            first.mkdir()
            second.mkdir()
            cache = ReadModelCache(fallback_scan_seconds=30)
            calls = {"first": 0, "second": 0}

            def build(label):
                calls[label] += 1
                return {"value": calls[label]}

            cache.get("first", first, lambda: build("first"))
            cache.get("second", second, lambda: build("second"))
            self.assertEqual(cache.invalidate(first, reason="test-write"), 1)
            self.assertEqual(cache.revision(first), 1)
            self.assertEqual(cache.get("first", first, lambda: build("first"))["value"], 2)
            self.assertEqual(cache.get("second", second, lambda: build("second"))["value"], 1)

    def test_external_nested_edit_is_detected_by_bounded_fallback_scan(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            scene = project / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir()
            scene.write_text("status: planned\n", encoding="utf-8")
            calls = []
            cache = ReadModelCache(ttl_seconds=0.1, fallback_scan_seconds=0.1)

            def build():
                calls.append(1)
                return {"value": len(calls)}

            self.assertEqual(cache.get("dashboard", project, build)["value"], 1)
            scene.write_text("status: drafted-and-reviewed\n", encoding="utf-8")
            time.sleep(0.12)
            self.assertEqual(cache.get("dashboard", project, build)["value"], 2)

    def test_does_not_deep_scan_again_before_ttl_when_root_signature_is_stable(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "project.yaml").write_text("title: stable\n", encoding="utf-8")
            cache = ReadModelCache(ttl_seconds=30)
            with mock.patch.object(
                read_model_cache,
                "project_revision_fingerprint",
                wraps=read_model_cache.project_revision_fingerprint,
            ) as fingerprint:
                cache.get("dashboard", project, lambda: {"value": 1})
                calls_after_first_read = fingerprint.call_count
                cache.get("dashboard", project, lambda: {"value": 2})
                self.assertEqual(fingerprint.call_count, calls_after_first_read)


if __name__ == "__main__":
    unittest.main()
