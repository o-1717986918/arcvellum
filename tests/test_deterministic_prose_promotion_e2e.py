from __future__ import annotations

import json
import hashlib
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
from literary_engineering_studio_engine.literary.scene.promotion.gate_support import (
    candidate_body,
)
from literary_engineering_studio_engine.canon_evolver import canon_writeback_status

from tests.scene_lifecycle_support import candidate_text, prepare_promotable_candidate


class DeterministicProsePromotionE2ETests(unittest.TestCase):
    """Exercise the non-LLM half of candidate-to-draft promotion end to end.

    Agent-authored artifacts are controlled fixtures here. The production code
    still validates their provenance, exact candidate digest, task receipts,
    independent reviewer identity, quality contracts, and lint gate before it
    is allowed to promote a candidate.
    """

    def test_candidate_body_accepts_pi_worker_prose_only_artifact(self):
        prose = "# 章节题目\n\n## 第一场\n\n林舟把手电压低，沿墙找到新鲜划痕。"

        self.assertEqual(candidate_body(prose), prose)

    def test_candidate_body_strips_workbench_sections_but_preserves_literary_subheadings(self):
        artifact = (
            "## 修订正文候选\n\n"
            "# 章节题目\n\n## 第一场\n\n林舟把手电压低。\n\n"
            "## 第二场\n\n门从里面开了。\n\n"
            "## 状态变化候选\n\n- 林舟改变判断。\n"
        )

        self.assertEqual(
            candidate_body(artifact),
            "# 章节题目\n\n## 第一场\n\n林舟把手电压低。\n\n## 第二场\n\n门从里面开了。",
        )

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

    def test_clean_pi_prose_keeps_structured_writeback_and_reviewed_canon_declaration(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, candidate = prepare_promotable_candidate(Path(temporary))
            candidate.write_text(
                "# 旧楼里的电流声\n\n林舟把手电压低，推开旧楼的门。",
                encoding="utf-8",
            )
            composition = root / "drafts" / "compositions" / "scene_0001_composition.json"
            composition.parent.mkdir(parents=True, exist_ok=True)
            composition.write_text(
                json.dumps(
                    {
                        "writeback_candidates": {
                            "new_facts": ["旧楼断电后仍有稳定电流声。"],
                            "character_changes": ["林舟决定进入旧楼继续调查。"],
                            "relationship_changes": [],
                            "foreshadowing_changes": ["电流声来源等待后续确认。"],
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            # The candidate must be derived from the current composition
            # packet, even when the prose body itself does not change.
            candidate.touch()
            review_path = root / "reviews" / "agent" / "scene_0001_scene_review.json"
            review = json.loads(review_path.read_text(encoding="utf-8"))
            review["candidate_sha256"] = hashlib.sha256(candidate.read_bytes()).hexdigest()
            review["canon_writeback"] = {
                "status": "pending_canon_evolve",
                "canon_change": True,
                "no_canon_change_reason": "",
                "candidate_patch": "旧楼断电后的稳定电流声是需要跨场景约束的地点事实。",
            }
            review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            result = promote_scene_candidate(
                root,
                scene=Path("scenes/scene_0001.yaml"),
                candidate=candidate.relative_to(root),
                overwrite=True,
            )

            draft = result.draft_path.read_text(encoding="utf-8")
            self.assertIn("林舟决定进入旧楼继续调查", draft)
            self.assertNotIn("无。\n\n### 人物状态变化\n\n- 无。", draft)
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(
                manifest["writeback_sections_source"],
                "drafts/compositions/scene_0001_composition.json",
            )
            self.assertIs(manifest["canon_writeback"]["canon_change"], True)
            self.assertEqual(
                manifest["canon_writeback"]["source"],
                "reviews/agent/scene_0001_scene_review.json",
            )
            status = canon_writeback_status(root, "scene_0001")
            self.assertEqual(status["status"], "missing_patch", status)
            self.assertIs(status["declaration"]["canon_change"], True)

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
