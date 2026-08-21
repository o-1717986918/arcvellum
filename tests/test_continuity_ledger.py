import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio_engine.agent_tasks import write_agent_completion_marker
from literary_engineering_studio_engine.continuity_ledger import (
    DELTA_SCHEMA,
    REVIEW_SCHEMA,
    apply_continuity_ledger,
    author_task_path,
    delta_path,
    prepare_continuity_ledger,
    prepare_continuity_ledger_review,
    promise_ledger_path,
    normalize_ledger_rows,
    reader_ledger_path,
    review_path,
    review_task_path,
)
import literary_engineering_studio_engine.routes.scene.gates as scene_gates


class ContinuityLedgerTests(unittest.TestCase):
    def test_scene_gate_accepts_the_full_continuity_status_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = {"scene_id": "scene_0001", "current_state": "continuity-ledger-agent-task"}
            with patch.object(scene_gates, "continuity_ledger_status", return_value=(True, "ready", {})), patch.object(
                scene_gates, "continuity_ledger_task_status", return_value=(True, "ready")
            ):
                errors, _notes = scene_gates._state_gate_validation(root, task)

            self.assertEqual(errors, [])

    def test_only_reviewed_digest_bound_delta_can_change_formal_ledgers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "drafts" / "scenes").mkdir(parents=True)
            (root / "drafts" / "promotions").mkdir(parents=True)
            (root / "drafts" / "scenes" / "scene_0001.md").write_text("# Draft\n\n钟声响了。\n", encoding="utf-8")
            (root / "drafts" / "promotions" / "scene_0001_promotion.json").write_text("{}", encoding="utf-8")
            delta, task = prepare_continuity_ledger(root, "scene_0001")
            payload = json.loads(delta.read_text(encoding="utf-8"))
            payload.update({
                "schema": DELTA_SCHEMA,
                "status": "complete",
                "writer_session_id": "writer-1",
                "evidence_paths": ["drafts/scenes/scene_0001.md"],
                "reader_question_changes": [{"question_id": "q-bell", "visible_question": "谁敲响钟？", "status": "open", "target_window": "scene_0003", "evidence": "钟声响了。"}],
                "promise_changes": [{"promise_id": "p-bell", "promised_effect": "钟声来源会揭示", "status": "open", "due_window": "scene_0003", "evidence": "钟声响了。"}],
            })
            delta.write_text(json.dumps(payload), encoding="utf-8")
            write_agent_completion_marker(task, root=root)
            review, review_task = prepare_continuity_ledger_review(root, "scene_0001")
            review_payload = json.loads(review.read_text(encoding="utf-8"))
            review_payload.update({
                "schema": REVIEW_SCHEMA,
                "status": "complete",
                "delta_sha256": hashlib.sha256(delta.read_bytes()).hexdigest(),
                "reviewer_session_id": "reviewer-2",
                "verdict": "pass",
            })
            review.write_text(json.dumps(review_payload), encoding="utf-8")
            write_agent_completion_marker(review_task, root=root)

            questions, promises = apply_continuity_ledger(root, "scene_0001")
            self.assertTrue(questions.is_file())
            self.assertTrue(promises.is_file())
            self.assertEqual(json.loads(reader_ledger_path(root).read_text(encoding="utf-8"))["reader_questions"][0]["id"], "q-bell")
            self.assertEqual(json.loads(reader_ledger_path(root).read_text(encoding="utf-8"))["reader_questions"][0]["status"], "open")
            self.assertEqual(json.loads(promise_ledger_path(root).read_text(encoding="utf-8"))["promises"][0]["id"], "p-bell")

            payload["reader_question_changes"][0]["visible_question"] = "changed"
            delta_path(root, "scene_0001").write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "stale"):
                apply_continuity_ledger(root, "scene_0001")

    def test_event_aliases_fold_back_into_the_original_ledger_identity(self):
        rows = normalize_ledger_rows(
            "reader_questions",
            [
                {"id": "q1", "change": "setup", "question": "谁敲钟？", "evidence": "钟响了", "responsibility": "后续回答"},
                {
                    "id": "scene_0003-reader_questions-1",
                    "question_id": "q1",
                    "change": "closure",
                    "question": "谁敲钟？",
                    "evidence": "守钟人承认了",
                    "resolution_summary": "身份揭晓",
                    "last_advanced_at": "scene_0003",
                },
            ],
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "q1")
        self.assertEqual(rows[0]["status"], "resolved")
        self.assertEqual(rows[0]["actual_payoff_scene"], "scene_0003")


if __name__ == "__main__":
    unittest.main()
