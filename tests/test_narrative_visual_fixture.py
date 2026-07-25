import tempfile
from pathlib import Path
import unittest

from benchmarks.narrative_visual_fixture import (
    FIXTURE_SCHEMA,
    materialize_narrative_visual_fixture,
)
from literary_engineering_studio_engine.project_library import build_narrative_evidence


class NarrativeVisualFixtureTests(unittest.TestCase):
    def test_fixture_materializes_graph_relations_rhythm_and_prose(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "fixture"
            report = materialize_narrative_visual_fixture(root, 100)
            evidence = build_narrative_evidence(root)

            self.assertEqual(report["schema"], FIXTURE_SCHEMA)
            self.assertEqual(report["scene_count"], 100)
            self.assertEqual(len(evidence["sections"]["scenes"]), 100)
            self.assertTrue(evidence["sections"]["characters"])
            self.assertTrue(evidence["sections"]["branches"])
            self.assertTrue(evidence["sections"]["reviews"])
            self.assertTrue(evidence["sections"]["canon_patches"])
            self.assertTrue((root / "plot" / "rhythm_plan.json").is_file())
            self.assertTrue((root / "drafts" / "scenes" / "scene_0001.md").is_file())

    def test_fixture_refuses_to_overwrite_an_existing_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "fixture"
            root.mkdir()
            root.joinpath("keep.txt").write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(FileExistsError, "not empty"):
                materialize_narrative_visual_fixture(root, 100)


if __name__ == "__main__":
    unittest.main()
