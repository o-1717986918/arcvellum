import json
import hashlib
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.agent_tasks import write_agent_completion_marker
from literary_engineering_studio_engine.continuity_ledger import (
    DELTA_SCHEMA,
    REVIEW_SCHEMA,
    apply_continuity_ledger,
    prepare_continuity_ledger,
    prepare_continuity_ledger_review,
)
from literary_engineering_studio_engine.scene_handoff import (
    HANDOFF_SCHEMA,
    build_scene_handoff,
    scene_handoff_source_status,
    scene_handoff_status,
)


class SceneHandoffTests(unittest.TestCase):
    def _prepare_completed_scene(self, root: Path) -> Path:
        draft = root / "drafts" / "scenes" / "scene_0001.md"
        draft.write_text("# Draft\n\n钟声响了。\n", encoding="utf-8")
        promotion = root / "drafts" / "promotions" / "scene_0001_promotion.json"
        promotion.write_text(
            json.dumps(
                {
                    "scene_id": "scene_0001",
                    "draft_sha256": hashlib.sha256(draft.read_bytes()).hexdigest(),
                    "canon_writeback": {
                        "canon_change": False,
                        "no_canon_change_reason": "本场只推进既有钟声线索，没有形成新的世界事实。",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        state = root / "characters" / "state_patches" / "scene_0001_state_patch.json"
        state.parent.mkdir(parents=True)
        state.write_text(
            json.dumps({"scene_id": "scene_0001", "characters": [], "unresolved_changes": []}),
            encoding="utf-8",
        )
        delta, task = prepare_continuity_ledger(root, "scene_0001")
        delta_payload = json.loads(delta.read_text(encoding="utf-8"))
        delta_payload.update(
            {
                "schema": DELTA_SCHEMA,
                "status": "complete",
                "writer_session_id": "writer-handoff",
                "evidence_paths": ["drafts/scenes/scene_0001.md"],
                "reader_question_changes": [],
                "promise_changes": [],
                "no_change_reason": "本场保留既有钟声疑问，没有新增或结清连续性条目。",
            }
        )
        delta.write_text(json.dumps(delta_payload, ensure_ascii=False), encoding="utf-8")
        write_agent_completion_marker(task, root=root, handled_by="writer-handoff")
        review, review_task = prepare_continuity_ledger_review(root, "scene_0001")
        review_payload = json.loads(review.read_text(encoding="utf-8"))
        review_payload.update(
            {
                "schema": REVIEW_SCHEMA,
                "status": "complete",
                "delta_sha256": hashlib.sha256(delta.read_bytes()).hexdigest(),
                "reviewer_session_id": "reviewer-handoff",
                "verdict": "pass",
            }
        )
        review.write_text(json.dumps(review_payload, ensure_ascii=False), encoding="utf-8")
        write_agent_completion_marker(review_task, root=root, handled_by="reviewer-handoff")
        apply_continuity_ledger(root, "scene_0001")
        return draft

    def test_promoted_predecessor_requires_digest_bound_handoff(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scenes").mkdir(parents=True)
            (root / "drafts" / "scenes").mkdir(parents=True)
            (root / "drafts" / "promotions").mkdir(parents=True)
            (root / "scenes" / "scene_0001.yaml").write_text("scene_id: scene_0001\ntimeline_order: 1\nlocation: dock\nnext_hooks:\n  - bell\n", encoding="utf-8")
            (root / "scenes" / "scene_0002.yaml").write_text("scene_id: scene_0002\ntimeline_order: 2\n", encoding="utf-8")
            draft = self._prepare_completed_scene(root)

            ready, message, _payload = scene_handoff_status(root, "scene_0002")
            self.assertFalse(ready)
            self.assertIn("missing", message)

            handoff = build_scene_handoff(root, "scene_0001")
            self.assertTrue(handoff.is_file())
            ready, _message, payload = scene_handoff_status(root, "scene_0002")
            self.assertTrue(ready)
            self.assertEqual(payload["schema"], HANDOFF_SCHEMA)
            self.assertEqual(payload["outgoing_hooks"], ["bell"])
            self.assertEqual(payload["successor_scene_id"], "scene_0002")
            self.assertIn("continuity_apply", payload["evidence"])

            draft.write_text("# Draft\n\n被改过。\n", encoding="utf-8")
            ready, message, _payload = scene_handoff_status(root, "scene_0002")
            self.assertFalse(ready)
            self.assertIn("promotion manifest", message)

    def test_handoff_refuses_before_continuity_apply(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scenes").mkdir(parents=True)
            (root / "drafts" / "scenes").mkdir(parents=True)
            (root / "drafts" / "promotions").mkdir(parents=True)
            (root / "scenes" / "scene_0001.yaml").write_text("scene_id: scene_0001\ntimeline_order: 1\n", encoding="utf-8")
            self._prepare_completed_scene(root)
            (root / "plot" / "ledger_deltas" / "scene_0001_apply.json").unlink()

            with self.assertRaisesRegex(ValueError, "apply receipt"):
                build_scene_handoff(root, "scene_0001")

    def test_handoff_detects_changed_applied_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scenes").mkdir(parents=True)
            (root / "drafts" / "scenes").mkdir(parents=True)
            (root / "drafts" / "promotions").mkdir(parents=True)
            (root / "scenes" / "scene_0001.yaml").write_text("scene_id: scene_0001\ntimeline_order: 1\n", encoding="utf-8")
            self._prepare_completed_scene(root)
            build_scene_handoff(root, "scene_0001")
            delta = root / "plot" / "ledger_deltas" / "scene_0001.json"
            delta.write_text(delta.read_text(encoding="utf-8") + "\n", encoding="utf-8")

            ready, message, _payload = scene_handoff_source_status(root, "scene_0001")
            self.assertFalse(ready)
            self.assertIn("stale", message)


if __name__ == "__main__":
    unittest.main()
