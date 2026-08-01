from __future__ import annotations

import unittest

from literary_engineering_studio.runtime.context_cache import (
    ContextCacheKey,
    cache_key_violations,
    context_cache_key_fingerprint,
    partition_reusable,
)
from literary_engineering_studio.runtime.session_lease import (
    SessionLease,
    SessionRole,
    session_lease_violations,
    session_reusable,
)


def _key(**overrides):
    base = dict(
        project_revision="rev-1",
        scope_kind="scene",
        scope_id="scene_0001",
        canon_digest="canon-1",
        character_state_digest="state-1",
        style_mount_hash="style-1",
        word_budget_revision="budget-1",
        rhythm_bridge_hash="rhythm-1",
        task_role="writer",
        task_kind="formal_scene_prose",
    )
    base.update(overrides)
    return ContextCacheKey(**base)


def _lease(**overrides):
    base = dict(
        session_id="session-1",
        role=SessionRole.WRITER,
        project_id="project-test",
        model_id="model-1",
        style_mount_hash="style-1",
        context_ledger_epoch="epoch-1",
        previous_task_completed=True,
        token_used=1000,
        elapsed_seconds=60.0,
        failure_count=0,
        max_tokens=5000,
        max_seconds=600.0,
        max_failures=2,
    )
    base.update(overrides)
    return SessionLease(**base)


class ContextCacheKeyTests(unittest.TestCase):
    def test_fingerprint_is_stable_and_sensitive_to_identity_fields(self):
        first = context_cache_key_fingerprint(_key())
        second = context_cache_key_fingerprint(_key())
        changed = context_cache_key_fingerprint(_key(canon_digest="canon-2"))

        self.assertEqual(first, second)
        self.assertNotEqual(first, changed)

    def test_missing_fields_are_reported(self):
        violations = cache_key_violations(_key(project_revision="", scope_id=""))

        self.assertEqual(len(violations), 2)
        self.assertEqual({item.code for item in violations}, {"missing-field"})

    def test_invalid_scope_kind_is_reported(self):
        violations = cache_key_violations(_key(scope_kind="book"))

        self.assertEqual({item.code for item in violations}, {"invalid-scope-kind"})

    def test_partition_reuse_requires_exact_identity(self):
        self.assertTrue(partition_reusable(_key(), _key()))
        self.assertFalse(
            partition_reusable(_key(), _key(style_mount_hash="style-2"))
        )
        self.assertFalse(
            partition_reusable(_key(), _key(task_role="reviewer"))
        )


class SessionLeaseTests(unittest.TestCase):
    def test_identical_lease_is_reusable(self):
        decision = session_reusable(
            _lease(),
            role=SessionRole.WRITER,
            project_id="project-test",
            model_id="model-1",
            style_mount_hash="style-1",
            context_ledger_epoch="epoch-1",
        )

        self.assertTrue(decision.reusable)
        self.assertEqual(decision.reasons, ())

    def test_role_mismatch_blocks_reuse(self):
        decision = session_reusable(
            _lease(role=SessionRole.WRITER),
            role=SessionRole.REVIEWER,
            project_id="project-test",
            model_id="model-1",
            style_mount_hash="style-1",
            context_ledger_epoch="epoch-1",
        )

        self.assertFalse(decision.reusable)
        self.assertIn("role-mismatch", decision.reasons)

    def test_identity_changes_block_reuse(self):
        decision = session_reusable(
            _lease(),
            role=SessionRole.WRITER,
            project_id="project-other",
            model_id="model-2",
            style_mount_hash="style-2",
            context_ledger_epoch="epoch-2",
        )

        self.assertFalse(decision.reusable)
        for reason in (
            "project-mismatch",
            "model-mismatch",
            "style-mismatch",
            "context-ledger-invalidated",
        ):
            self.assertIn(reason, decision.reasons)

    def test_budgets_and_completion_block_reuse(self):
        decision = session_reusable(
            _lease(
                previous_task_completed=False,
                token_used=6000,
                elapsed_seconds=700.0,
                failure_count=3,
            ),
            role=SessionRole.WRITER,
            project_id="project-test",
            model_id="model-1",
            style_mount_hash="style-1",
            context_ledger_epoch="epoch-1",
        )

        self.assertFalse(decision.reusable)
        for reason in (
            "previous-task-incomplete",
            "token-budget-exceeded",
            "time-budget-exceeded",
            "failure-budget-exceeded",
        ):
            self.assertIn(reason, decision.reasons)

    def test_lease_structural_violations(self):
        violations = session_lease_violations(
            _lease(
                session_id="",
                token_used=-1,
                elapsed_seconds=-1.0,
            )
        )

        codes = {item.code for item in violations}
        self.assertIn("missing-session-id", codes)
        self.assertIn("invalid-counter", codes)
        self.assertIn("invalid-duration", codes)

    def test_valid_lease_has_no_violations(self):
        self.assertEqual(session_lease_violations(_lease()), ())


if __name__ == "__main__":
    unittest.main()
