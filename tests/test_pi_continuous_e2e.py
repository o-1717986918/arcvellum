from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.verification.pi_continuous_e2e import (
    FullWorkAcceptance,
    collect_evidence,
    collect_full_work_evidence,
)


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

    def test_full_work_requires_every_scene_delivery_and_exact_character_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _complete_full_work_fixture(root)
            evidence = collect_full_work_evidence(
                root,
                {"runtime": "pi-worker", "status": "complete"},
                [{"event": "worker.runner.provider.request.started", "data": {}}],
                {"sessions": [{"runtime": "pi-worker"}]},
                {"total_chinese_content_chars": 30000},
                {"status": "ready", "files": [{"path": "releases/work.docx"}]},
                FullWorkAcceptance(2, 6, 30000),
            )

        self.assertTrue(evidence.complete)

    def test_full_work_rejects_an_apparently_complete_run_with_short_prose(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _complete_full_work_fixture(root)
            evidence = collect_full_work_evidence(
                root,
                {"runtime": "pi-worker", "status": "complete"},
                [{"event": "worker.runner.provider.request.started", "data": {}}],
                {"sessions": [{"runtime": "pi-worker"}]},
                {"total_chinese_content_chars": 29999},
                {"status": "ready", "files": [{"path": "releases/work.docx"}]},
                FullWorkAcceptance(2, 6, 30000),
            )

        self.assertFalse(evidence.complete)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _complete_full_work_fixture(root: Path) -> None:
    for chapter_id in ("chapter_0001", "chapter_0002"):
        _write(root / f"outline/chapters/{chapter_id}.yaml", "status: formal\n")
    for number in range(1, 7):
        scene_id = f"scene_{number:04d}"
        for relative in (
            f"scenes/{scene_id}.yaml",
            f"drafts/scenes/{scene_id}.md",
            f"reviews/agent/{scene_id}_scene_review.json",
            f"characters/state_patches/{scene_id}_state_apply.json",
            f"plot/ledger_deltas/{scene_id}_apply.json",
        ):
            _write(root / relative, "{}\n")
        _write(
            root / f"drafts/promotions/{scene_id}_promotion.json",
            json.dumps(
                {
                    "candidate_review": {"status": "pass"},
                    "candidate_generation": {"status": "pass"},
                }
            ),
        )


if __name__ == "__main__":
    unittest.main()
