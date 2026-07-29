from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from literary_engineering_studio_engine.flow_gates import FlowGateError
from literary_engineering_studio_engine.literary.scene.promotion.candidate import (
    candidate_generation_gate,
    candidate_review_gate,
    promote_scene_candidate,
)
from literary_engineering_studio_engine.literary.scene.promotion.historical import (
    validate_historical_promotion,
)

from tests.scene_lifecycle_support import candidate_text, prepare_promotable_candidate


class DeterministicProsePromotionE2ETests(unittest.TestCase):
    """Exercise the non-LLM half of candidate-to-draft promotion end to end.

    Agent-authored artifacts are controlled fixtures here. The production code
    still validates their provenance, exact candidate digest, task receipts,
    independent reviewer identity, quality contracts, and lint gate before it
    is allowed to promote a candidate.
    """

    def test_clean_candidate_is_promoted_only_after_all_deterministic_gates_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, candidate = prepare_promotable_candidate(Path(temporary))

            generation = candidate_generation_gate(root, "scene_0001", candidate)
            review = candidate_review_gate(root, "scene_0001", candidate)
            self.assertEqual(generation["status"], "pass", generation)
            self.assertEqual(review["status"], "pass", review)

            result = promote_scene_candidate(
                root,
                scene=Path("scenes/scene_0001.yaml"),
                candidate=candidate.relative_to(root),
                overwrite=True,
            )

            self.assertTrue(result.draft_path.is_file())
            draft = result.draft_path.read_text(encoding="utf-8")
            self.assertIn("林舟把手电压低", draft)
            self.assertNotIn("[AGENT_TASK:", draft)
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertFalse(manifest["allow_unreviewed"])
            self.assertFalse(manifest["allow_review_notes"])
            self.assertEqual(manifest["candidate_generation"]["status"], "pass")
            self.assertEqual(manifest["candidate_review"]["status"], "pass")
            historical = validate_historical_promotion(
                root,
                "scene_0001",
                manifest,
            )
            self.assertTrue(historical.passed, historical.errors)
            self.assertTrue(historical.current)

    def test_tampering_or_style_lint_failure_blocks_repromotion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, candidate = prepare_promotable_candidate(Path(temporary))
            candidate.write_text(
                candidate_text("不是门后没有人，而是有人刚刚离开。"),
                encoding="utf-8",
            )

            stale = candidate_review_gate(root, "scene_0001", candidate)
            self.assertNotEqual(stale["status"], "pass", stale)
            self.assertEqual(stale["style_lint"]["status"], "blocking", stale)
            with self.assertRaises(FlowGateError):
                promote_scene_candidate(
                    root,
                    scene=Path("scenes/scene_0001.yaml"),
                    candidate=candidate.relative_to(root),
                    overwrite=True,
                )

    def test_cli_promote_candidate_runs_without_any_bypass_option(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, candidate = prepare_promotable_candidate(Path(temporary))
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "literary_engineering_studio_engine",
                    "promote-candidate",
                    str(root),
                    "--scene",
                    "scenes/scene_0001.yaml",
                    "--candidate",
                    candidate.relative_to(root).as_posix(),
                    "--overwrite",
                ],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("draft:", result.stdout)
            self.assertTrue((root / "drafts" / "scenes" / "scene_0001.md").is_file())

if __name__ == "__main__":
    unittest.main()
