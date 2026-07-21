from pathlib import Path
import tempfile
import time
import unittest

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


if __name__ == "__main__":
    unittest.main()
