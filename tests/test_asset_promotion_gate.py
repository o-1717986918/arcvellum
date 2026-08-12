from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio_engine.agent_tasks import write_agent_completion_marker
from literary_engineering_studio_engine.approval import record_workflow_approval
from literary_engineering_studio_engine.asset_workshop import _dry_payload, promote_candidate_asset


class AssetPromotionGateTests(unittest.TestCase):
    def test_direct_promotion_rejects_approval_without_independent_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = self._write_candidate(root)
            self._approve(root, candidate)

            with self.assertRaisesRegex(RuntimeError, "review"):
                promote_candidate_asset(
                    root,
                    candidate,
                    group="character",
                    approval_run_id=candidate.stem,
                )

            self.assertFalse((root / "characters" / "protagonist.yaml").exists())

    def test_review_without_current_candidate_digest_cannot_authorize_promotion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = self._write_candidate(root)
            self._write_review(root, candidate, candidate_sha256="")
            self._approve(root, candidate)

            with self.assertRaisesRegex(RuntimeError, "candidate_sha256"):
                promote_candidate_asset(
                    root,
                    candidate,
                    group="character",
                    approval_run_id=candidate.stem,
                )

    def test_exact_current_review_and_approval_allow_deterministic_promotion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = self._write_candidate(root)
            self._write_review(root, candidate, candidate_sha256=self._sha(candidate))
            self._approve(root, candidate)

            result = promote_candidate_asset(
                root,
                candidate,
                group="character",
                approval_run_id=candidate.stem,
            )

            self.assertEqual(result.status, "promoted")
            self.assertTrue((root / "characters" / "protagonist.yaml").is_file())

    def test_candidate_change_invalidates_an_older_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = self._write_candidate(root)
            self._write_review(root, candidate, candidate_sha256=self._sha(candidate))
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            payload["name"] = "林昭（修订）"
            candidate.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            self._approve(root, candidate)

            with self.assertRaisesRegex(RuntimeError, "current candidate"):
                promote_candidate_asset(
                    root,
                    candidate,
                    group="character",
                    approval_run_id=candidate.stem,
                )

    def test_promotion_write_failure_restores_existing_formal_asset(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = self._write_candidate(root)
            self._write_review(root, candidate, candidate_sha256=self._sha(candidate))
            self._approve(root, candidate)
            formal = root / "characters" / "protagonist.yaml"
            formal.parent.mkdir(parents=True, exist_ok=True)
            formal.write_text("name: 旧版本\n", encoding="utf-8")

            def fail_after_overwrite(_root, _asset_type, _payload):
                formal.write_text("name: 损坏的新版本\n", encoding="utf-8")
                raise OSError("simulated promotion write failure")

            with patch(
                "literary_engineering_studio_engine.literary.assets.workshop._write_promoted_asset",
                side_effect=fail_after_overwrite,
            ):
                with self.assertRaisesRegex(OSError, "simulated"):
                    promote_candidate_asset(
                        root,
                        candidate,
                        group="character",
                        approval_run_id=candidate.stem,
                    )

            self.assertEqual(formal.read_text(encoding="utf-8"), "name: 旧版本\n")
            self.assertFalse(
                (root / "workflow" / "asset_promotions" / f"{candidate.stem}_promotion.json").exists()
            )

    def test_world_promotion_does_not_turn_candidate_lifecycle_into_canon(self):
        from literary_engineering_studio_engine.literary.assets.workshop import _write_promoted_asset

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "canon").mkdir()
            outputs = _write_promoted_asset(
                root,
                "world",
                {
                    "world_name": "测试世界",
                    "core_rules": [
                        {"id": "fuel_deadline", "description": "燃料限制行动。"},
                        {
                            "id": "candidate_not_confirmed",
                            "description": "本候选资产未经 schema 审查与人工批准不得晋升。",
                        },
                    ],
                    "constraints": ["飞船不能凭空补充燃料。", "candidate_status=ready_for_review"],
                    "power_sources": [],
                    "social_order": [],
                    "taboos": [],
                    "history_pressure": [],
                    "open_questions": [],
                },
            )

            rendered = outputs[0].read_text(encoding="utf-8")
            self.assertIn("fuel_deadline", rendered)
            self.assertIn("飞船不能凭空补充燃料", rendered)
            self.assertNotIn("candidate_not_confirmed", rendered)
            self.assertNotIn("ready_for_review", rendered)

    @staticmethod
    def _write_candidate(root: Path) -> Path:
        candidate = root / "characters" / "candidates" / "protagonist-foundation.json"
        candidate.parent.mkdir(parents=True)
        payload = _dry_payload("character", candidate.stem, root, "", "protagonist", None)
        candidate.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        candidate.with_suffix(".md").write_text("# 主角候选\n", encoding="utf-8")
        return candidate

    @staticmethod
    def _write_review(root: Path, candidate: Path, *, candidate_sha256: str) -> None:
        review_dir = root / "reviews" / "assets"
        review_dir.mkdir(parents=True)
        review_json = review_dir / f"{candidate.stem}_review.json"
        review_md = review_json.with_suffix(".md")
        review_task = review_json.with_suffix(".agent_tasks.md")
        review_task.write_text("# independent review\n", encoding="utf-8")
        review_json.write_text(
            json.dumps(
                {
                    "schema": "literary-engineering-workbench/candidate-asset-review/v0.1",
                    "candidate": candidate.relative_to(root).as_posix(),
                    "candidate_id": candidate.stem,
                    "candidate_sha256": candidate_sha256,
                    "asset_type": "character",
                    "status": "pass",
                    "blocking_issues": [],
                    "warnings": [],
                    "revision_actions": [],
                    "promotion_risks": [],
                    "reviewed_at": "2026-07-25T00:00:00Z",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        review_md.write_text("# 独立审查\n\n结论：通过。\n", encoding="utf-8")
        write_agent_completion_marker(review_task, root=root, handled_by="independent-reviewer")

    @staticmethod
    def _approve(root: Path, candidate: Path) -> None:
        record_workflow_approval(
            root,
            candidate.stem,
            "approve",
            subject_sha256=AssetPromotionGateTests._sha(candidate),
        )

    @staticmethod
    def _sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
