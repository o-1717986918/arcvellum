from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.verification.pi_continuous_e2e import collect_evidence


class PiContinuousE2ETests(unittest.TestCase):
    def test_evidence_requires_the_same_scene_to_close_and_the_next_to_be_claimed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in (
                "drafts/scenes/scene_0001.md",
                "reviews/agent/scene_0001_scene_review.json",
                "characters/state_patches/scene_0001_state_apply.json",
                "plot/ledger_deltas/scene_0001_apply.json",
            ):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}", encoding="utf-8")
            promotion = root / "drafts/promotions/scene_0001_promotion.json"
            promotion.parent.mkdir(parents=True, exist_ok=True)
            promotion.write_text(
                json.dumps({"candidate_review": {"status": "pass"}, "candidate_generation": {"status": "pass"}}),
                encoding="utf-8",
            )
            events = [
                {"event": "worker.runner.provider.request.started", "data": {}},
                {"event": "worker.task.opened", "data": {"task_id": "scene_0002:context-packet"}},
            ]
            evidence = collect_evidence(
                root,
                {"runtime": "pi-worker", "current_task_id": "scene_0002:context-packet"},
                events,
                {"sessions": [{"runtime": "pi-worker"}]},
            )

        self.assertTrue(evidence.complete)

    def test_promotion_without_state_and_continuity_is_not_a_complete_loop(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "drafts/promotions").mkdir(parents=True)
            (root / "drafts/promotions/scene_0001_promotion.json").write_text(
                json.dumps({"candidate_review": {"status": "pass"}, "candidate_generation": {"status": "pass"}}),
                encoding="utf-8",
            )
            evidence = collect_evidence(root, {"runtime": "pi-worker"}, [], {"sessions": []})

        self.assertFalse(evidence.complete)
        self.assertFalse(evidence.state_applied)
        self.assertFalse(evidence.continuity_applied)
        self.assertFalse(evidence.next_scene_claimed)


if __name__ == "__main__":
    unittest.main()
