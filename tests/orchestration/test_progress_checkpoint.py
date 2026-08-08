from __future__ import annotations

import unittest

from literary_engineering_studio.orchestration import (
    ChapterCheckpoint,
    ProgressFingerprintInput,
    checkpoint_matches,
    checkpoint_newer,
    checkpoint_violations,
    no_progress_detected,
    progress_fingerprint,
    progress_input_violations,
)


def _progress_input(**overrides):
    base = dict(
        scope_key="chapter_01",
        formal_artifact_digests=(
            ("drafts/scenes/scene_0001.md@promoted", "digest-1"),
        ),
        completed_task_ids=("task-1",),
        passed_gate_ids=("promotion",),
        promoted_hanzi=1800,
        obligation_updates=(("promise_0001", "fulfilled"),),
        review_revision_binding=(("candidate-1.md", "review-1.json"),),
    )
    base.update(overrides)
    return ProgressFingerprintInput(**base)


def _checkpoint(**overrides):
    base = dict(
        checkpoint_id="checkpoint-1",
        chapter_id="chapter_01",
        base_project_fingerprint="project-rev-1",
        progress_fingerprint="progress-1",
        last_task_id="task-1",
        promoted_scene_ids=("scene_0001",),
        pending_decision_ids=(),
        created_at="2026-07-30T00:00:00+00:00",
    )
    base.update(overrides)
    return ChapterCheckpoint(**base)


class ProgressFingerprintTests(unittest.TestCase):
    def test_fingerprint_is_stable_and_sensitive_to_formal_facts(self):
        first = progress_fingerprint(_progress_input())
        second = progress_fingerprint(_progress_input())
        changed = progress_fingerprint(
            _progress_input(
                formal_artifact_digests=(("drafts/scenes/a.md", "digest-2"),)
            )
        )

        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertNotEqual(first.fingerprint, changed.fingerprint)

    def test_obligation_and_review_binding_change_fingerprint(self):
        baseline = progress_fingerprint(_progress_input())
        obligation_changed = progress_fingerprint(
            _progress_input(
                obligation_updates=(("promise_0002", "deferred"),)
            )
        )
        review_changed = progress_fingerprint(
            _progress_input(
                review_revision_binding=(("candidate-2.md", "review-2.json"),)
            )
        )

        self.assertNotEqual(baseline.fingerprint, obligation_changed.fingerprint)
        self.assertNotEqual(baseline.fingerprint, review_changed.fingerprint)

    def test_no_progress_detection(self):
        previous = progress_fingerprint(_progress_input())
        current = progress_fingerprint(_progress_input())
        progressed = progress_fingerprint(
            _progress_input(promoted_hanzi=2400)
        )

        self.assertTrue(no_progress_detected(previous, current))
        self.assertFalse(no_progress_detected(previous, progressed))

    def test_different_scope_is_not_no_progress(self):
        previous = progress_fingerprint(_progress_input(scope_key="chapter_01"))
        current = progress_fingerprint(_progress_input(scope_key="chapter_02"))

        self.assertFalse(no_progress_detected(previous, current))

    def test_input_violations(self):
        violations = progress_input_violations(
            _progress_input(
                scope_key="",
                promoted_hanzi=-1,
                formal_artifact_digests=(
                    ("drafts/a.md", "d1"),
                    ("drafts/a.md", "d2"),
                    ("", ""),
                ),
            )
        )

        codes = {item.code for item in violations}
        self.assertEqual(
            codes,
            {
                "missing-scope-key",
                "invalid-promoted-hanzi",
                "duplicate-artifact-path",
                "invalid-artifact-digest",
            },
        )


class ChapterCheckpointTests(unittest.TestCase):
    def test_checkpoint_matches_requires_both_identities(self):
        checkpoint = _checkpoint()

        self.assertTrue(
            checkpoint_matches(
                checkpoint,
                base_project_fingerprint="project-rev-1",
                progress_fingerprint="progress-1",
            )
        )
        self.assertFalse(
            checkpoint_matches(
                checkpoint,
                base_project_fingerprint="project-rev-2",
                progress_fingerprint="progress-1",
            )
        )
        self.assertFalse(
            checkpoint_matches(
                checkpoint,
                base_project_fingerprint="project-rev-1",
                progress_fingerprint="progress-2",
            )
        )

    def test_checkpoint_newer_uses_iso_order(self):
        older = _checkpoint(created_at="2026-07-29T00:00:00+00:00")
        newer = _checkpoint(created_at="2026-07-30T00:00:00+00:00")

        self.assertTrue(checkpoint_newer(newer, older))
        self.assertFalse(checkpoint_newer(older, newer))

    def test_checkpoint_newer_compares_instants_across_offsets(self):
        earlier_in_utc = _checkpoint(
            created_at="2026-07-30T00:30:00+02:00"
        )
        later_in_utc = _checkpoint(
            created_at="2026-07-29T23:00:00+00:00"
        )

        self.assertFalse(checkpoint_newer(earlier_in_utc, later_in_utc))
        self.assertTrue(checkpoint_newer(later_in_utc, earlier_in_utc))

    def test_checkpoint_rejects_invalid_or_naive_timestamp(self):
        invalid = checkpoint_violations(_checkpoint(created_at="not-a-time"))
        naive = checkpoint_violations(
            _checkpoint(created_at="2026-07-30T00:00:00")
        )

        self.assertIn("invalid-created-at", {item.code for item in invalid})
        self.assertIn("invalid-created-at", {item.code for item in naive})

    def test_checkpoint_violations(self):
        violations = checkpoint_violations(
            _checkpoint(
                checkpoint_id="",
                base_project_fingerprint="",
                progress_fingerprint="",
                last_task_id="",
                created_at="",
                promoted_scene_ids=("scene_0001", "scene_0001"),
            )
        )

        codes = {item.code for item in violations}
        self.assertIn("missing-field", codes)
        self.assertIn("duplicate-promoted-scene", codes)

    def test_valid_checkpoint_has_no_violations(self):
        self.assertEqual(checkpoint_violations(_checkpoint()), ())


if __name__ == "__main__":
    unittest.main()
