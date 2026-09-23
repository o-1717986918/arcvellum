from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from benchmarks.prose_style_ab import ARMS, FIXTURE, build_baseline, build_blind_packet, validate_frozen_baseline


class ProseStyleBenchmarkTests(unittest.TestCase):
    def test_fixture_covers_eight_families_and_four_adjacent_pairs(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cases = fixture["cases"]
        self.assertEqual(len(cases), 8)
        self.assertEqual(len({item["family"] for item in cases}), 8)
        self.assertEqual(len(fixture["adjacent_groups"]), 4)

    def test_blind_packet_has_one_manifest_per_generated_candidate(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        with TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            candidates = root / "candidates"
            for case in fixture["cases"]:
                scene_id = case["scene_id"]
                baseline = project / "drafts" / "scenes" / f"{scene_id}.md"
                baseline.parent.mkdir(parents=True, exist_ok=True)
                baseline.write_text(f"{scene_id} 基线正文。", encoding="utf-8")
                for arm in ARMS[1:]:
                    path = candidates / arm / f"{scene_id}.md"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(f"{scene_id} {arm} 版正文。", encoding="utf-8")
                    path.with_suffix(".prompt.json").write_text(json.dumps({
                        "scene": f"plot/scenes/{scene_id}.yaml",
                        "expression_plan_digest": "expression",
                        "style_reference_selection": {"status": "selected"},
                        "voice_digest": "voice",
                    }), encoding="utf-8")
            baseline = build_baseline(project, fixture)
            self.assertEqual(len(baseline["scenes"]), 8)
            first = build_blind_packet(project, candidates, fixture, seed=7)
            second = build_blind_packet(project, candidates, fixture, seed=7)
            self.assertEqual(first, second)
            self.assertNotIn("A 版", first[0])
            self.assertEqual(len(first[1]["cases"]), 8)
            with self.assertRaisesRegex(ValueError, "frozen"):
                validate_frozen_baseline(baseline, {**baseline, "scenes": []})


if __name__ == "__main__":
    unittest.main()
