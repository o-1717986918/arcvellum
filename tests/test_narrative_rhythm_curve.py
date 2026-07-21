import unittest

from literary_engineering_studio_engine.narrative_rhythm import (
    analyze_narrative_rhythm_sequence,
    normalize_tension_curve,
)


class NarrativeRhythmCurveTests(unittest.TestCase):
    def test_normalizes_structured_and_compact_curves(self):
        self.assertEqual(normalize_tension_curve({"entry": 2, "peak": 5, "exit": 3}), {"entry": 2, "peak": 5, "exit": 3})
        self.assertEqual(normalize_tension_curve("2 -> 4 -> 1"), {"entry": 2, "peak": 4, "exit": 1})
        self.assertIsNone(normalize_tension_curve("先慢后快"))

    def test_detects_flat_and_exhausting_chapter_sequences(self):
        report = analyze_narrative_rhythm_sequence([
            {"scene_id": "scene_0001", "pace": "fast", "rhythm_role": "conflict", "tension_curve": {"entry": 3, "peak": 4, "exit": 4}},
            {"scene_id": "scene_0002", "pace": "fast", "rhythm_role": "conflict", "tension_curve": {"entry": 4, "peak": 5, "exit": 4}},
            {"scene_id": "scene_0003", "pace": "fast", "rhythm_role": "conflict", "tension_curve": {"entry": 4, "peak": 4, "exit": 3}},
        ])
        codes = {issue["code"] for issue in report["issues"]}
        self.assertEqual(report["status"], "needs_attention")
        self.assertIn("flat_pace_run", codes)
        self.assertIn("flat_role_run", codes)
        self.assertIn("flat_tension_band", codes)
        self.assertIn("sustained_high_pressure", codes)

    def test_missing_curve_is_incomplete_but_varied_curve_passes(self):
        incomplete = analyze_narrative_rhythm_sequence([{"scene_id": "scene_0001", "pace": "slow"}])
        self.assertEqual(incomplete["status"], "incomplete")
        varied = analyze_narrative_rhythm_sequence([
            {"scene_id": "scene_0001", "pace": "slow", "rhythm_role": "setup", "tension_curve": [1, 2, 2]},
            {"scene_id": "scene_0002", "pace": "fast", "rhythm_role": "conflict", "tension_curve": [2, 5, 3]},
            {"scene_id": "scene_0003", "pace": "slow", "rhythm_role": "aftermath", "tension_curve": [3, 3, 1]},
        ])
        self.assertEqual(varied["status"], "pass")


if __name__ == "__main__":
    unittest.main()
