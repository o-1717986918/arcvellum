from pathlib import Path
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest import mock

from literary_engineering_studio.projections import read_model_cache
from literary_engineering_studio.projections.read_model_cache import ReadModelCache


class ReadModelCacheTests(unittest.TestCase):
    def test_selected_values_are_isolated_and_do_not_copy_unselected_bulk_on_hits(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            cache = ReadModelCache()
            value = {"revision": "one", "nodes": [{"label": "原文"}]}
            cache.get("projection", project, lambda: value)
            with mock.patch.object(read_model_cache, "deepcopy", wraps=read_model_cache.deepcopy) as clone:
                self.assertIsNone(cache.get("projection", project, lambda: None,
                                            selector=lambda p: None if p["revision"] == "one" else p))
                self.assertIsNone(clone.call_args.args[0])
            detail = cache.get("projection", project, lambda: None, selector=lambda p: p["nodes"][0])
            detail["label"] = "修改返回值"
            self.assertEqual(cache.get("projection", project, lambda: None)["nodes"][0]["label"], "原文")

    def test_slow_build_does_not_block_unrelated_keys_and_same_key_builds_once(self):
        with tempfile.TemporaryDirectory() as temporary, ThreadPoolExecutor(max_workers=3) as pool:
            project = Path(temporary)
            cache, started, release = ReadModelCache(), Event(), Event()
            calls = []
            def slow():
                calls.append(1)
                started.set()
                if not release.wait(5):
                    raise TimeoutError("test did not release builder")
                return {"value": 1}
            first = pool.submit(cache.get, "slow", project, slow)
            self.assertTrue(started.wait(2))
            second = pool.submit(cache.get, "slow", project, slow)
            try:
                fast = pool.submit(cache.get, "other", project, lambda: {"value": 2})
                self.assertEqual(fast.result(timeout=2), {"value": 2})
            finally:
                release.set()
            self.assertEqual(first.result(timeout=2), second.result(timeout=2))
            self.assertEqual(len(calls), 1)

    def test_invalidation_or_clear_during_build_cannot_publish_the_old_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            for clear_all in (False, True):
                cache, calls = ReadModelCache(), []
                root = Path(temporary)
                def build():
                    calls.append(1)
                    if len(calls) == 1:
                        cache.clear() if clear_all else cache.invalidate(root)
                    return {"value": len(calls)}
                self.assertEqual(cache.get("x", root, build), {"value": 2})
                self.assertEqual(cache.get("x", root, lambda: {"value": 99}), {"value": 2})

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
