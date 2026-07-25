import unittest

from benchmarks.narrative_scale import (
    build_scale_library,
    benchmark_narrative_projection,
    validate_benchmark,
)


class NarrativeScaleBenchmarkTests(unittest.TestCase):
    def test_fixture_has_stable_chapters_characters_and_literary_relations(self):
        library = build_scale_library(100)
        sections = library["sections"]
        self.assertEqual(len(sections["scenes"]), 100)
        self.assertEqual(
            {fact["value"] for scene in sections["scenes"] for fact in scene["facts"] if fact["label"] == "章节"},
            {f"chapter_{index:04d}" for index in range(1, 11)},
        )
        self.assertTrue(sections["characters"])
        self.assertTrue(sections["branches"])
        self.assertTrue(sections["reviews"])

    def test_benchmark_preserves_detailed_nodes_and_stable_revisions(self):
        report = benchmark_narrative_projection((20,), repetitions=2)
        self.assertEqual(report["schema"], "arcvellum/narrative-performance-baseline/v1")
        self.assertEqual(report["violations"], [])
        self.assertEqual(len(report["samples"]), 2)
        detailed = next(item for item in report["samples"] if item["level"] == "scene")
        self.assertGreaterEqual(detailed["projected_node_count"], 20)
        self.assertGreater(detailed["payload_bytes"], 0)
        self.assertTrue(detailed["stable_revision"])

    def test_trend_gate_rejects_semantic_loss_and_extreme_growth(self):
        samples = [
            {
                "source_scene_count": 100,
                "level": "scene",
                "projected_node_count": 100,
                "payload_bytes": 10,
                "median_ms": 1,
                "stable_revision": True,
            },
            {
                "source_scene_count": 1000,
                "level": "scene",
                "projected_node_count": 999,
                "payload_bytes": 10,
                "median_ms": 50,
                "stable_revision": False,
            },
        ]
        violations = validate_benchmark(samples)
        self.assertTrue(any("lost source scenes" in item for item in violations))
        self.assertTrue(any("unstable" in item for item in violations))
        self.assertTrue(any("growth" in item for item in violations))


if __name__ == "__main__":
    unittest.main()
