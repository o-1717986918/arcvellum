from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.generate_module_map import render_module_map


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


if __name__ == "__main__":
    unittest.main()
