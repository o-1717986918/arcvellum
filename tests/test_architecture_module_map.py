from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.generate_module_map import _source_file_count, render_module_map


class ArchitectureModuleMapTests(unittest.TestCase):
    def test_map_records_static_boundaries_and_discovered_features(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            feature = root / "client/src/features/example"
            feature.mkdir(parents=True)
            (feature / "ExampleView.vue").write_text("<template />\n", encoding="utf-8")

            rendered = render_module_map(root)

        self.assertIn("`src/literary_engineering_studio/application`", rendered)
        self.assertIn("`workers/pi-worker/src`", rendered)
        self.assertIn("| `example` | 1 |", rendered)

    def test_tracked_source_count_ignores_build_and_test_residue(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "src/example"
            package.mkdir(parents=True)
            (package / "tracked.py").write_text("VALUE = 1\n", encoding="utf-8")
            (package / "generated.py").write_text("VALUE = 2\n", encoding="utf-8")

            count = _source_file_count(
                package,
                repository_root=root,
                tracked_sources=("src/example/tracked.py",),
            )

        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
