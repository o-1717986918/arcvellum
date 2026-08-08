from __future__ import annotations

import json
from pathlib import Path
import unittest

from literary_engineering_studio_engine.literary.scene.composition.beats import build_beats
from literary_engineering_studio_engine.literary.scene.facts import SceneFacts


FIXTURE = Path(__file__).parent / "fixtures" / "literary" / "cross_genre_composition_cases.json"
EXPECTED_GENRES = {
    "historical",
    "mystery",
    "realism",
    "ensemble",
    "comedy",
    "stream-of-consciousness",
    "screenplay",
}


class LiteraryCrossGenreCompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_seven_genres_keep_distinct_beat_shapes_and_all_obligations(self) -> None:
        cases = self.fixture["cases"]
        self.assertEqual({item["genre"] for item in cases}, EXPECTED_GENRES)
        required = set(self.fixture["required_obligations"])
        beat_counts: set[int] = set()
        for item in cases:
            with self.subTest(genre=item["genre"]):
                minimum, maximum = item["expected_beat_range"]
                beats = build_beats(_facts(item), [], {"beat_plan": item["beat_plan"]})
                beat_counts.add(len(beats))
                self.assertGreaterEqual(len(beats), minimum)
                self.assertLessEqual(len(beats), maximum)
                self.assertTrue(all(beat["source"] == "agent-branch-plan" for beat in beats))
                covered = {value for beat in beats for value in beat["serves"]}
                self.assertEqual(required - covered, set())
                self.assertTrue(all(beat["visible_action"] and beat["causal_change"] for beat in beats))
        self.assertGreaterEqual(len(beat_counts), 4)

    def test_blind_review_rubric_is_weighted_and_hides_implementation_hints(self) -> None:
        rubric = self.fixture["blind_review_rubric"]
        dimensions = rubric["dimensions"]
        self.assertEqual(sum(item["weight"] for item in dimensions), 100)
        self.assertGreaterEqual(len(dimensions), 7)
        hidden = set(rubric["hidden_metadata"])
        self.assertTrue({"model_id", "runtime_id", "branch_origin", "expected_beat_range"} <= hidden)
        self.assertTrue(all(1 <= item["blocking_floor"] <= 5 for item in dimensions))
        self.assertTrue(rubric["pass_policy"]["no_blocking_dimension_below_floor"])
        self.assertTrue(rubric["pass_policy"]["require_written_rationale"])


def _facts(case: dict[str, object]) -> SceneFacts:
    return SceneFacts(
        scene_id=str(case["id"]),
        chapter_id="chapter_fixture",
        location="fixture",
        participants=[],
        canon_refs=[],
        active_foreshadowing=[],
        scene_goal=str(case["scene_function"]),
        external_conflict="fixture external pressure",
        internal_conflict="fixture internal pressure",
        style_constraints=[],
        next_hooks=["fixture outgoing pressure"],
    )


if __name__ == "__main__":
    unittest.main()
