import unittest

from benchmarks.narrative_visual_performance import (
    benchmark_materialized_narrative,
    validate_materialized_narrative,
)


class NarrativeVisualPerformanceTests(unittest.TestCase):
    def test_real_projects_keep_complete_bounded_narrative_projections(self):
        report = benchmark_materialized_narrative()
        self.assertEqual(report["violations"], [])
        self.assertEqual([sample["scene_count"] for sample in report["samples"]], [100, 300, 1000])

    def test_gate_rejects_scene_loss_reference_explosion_and_unbounded_payload(self):
        violations = validate_materialized_narrative([{
            "scene_count": 1000,
            "evidence_scene_count": 250,
            "projection_scene_count": 250,
            "unresolved_character_refs": 500,
            "payload_bytes": 20_000_000,
            "evidence_ms": 20_000,
            "projection_ms": 20_000,
        }])
        self.assertEqual(len(violations), 6)


if __name__ == "__main__":
    unittest.main()
