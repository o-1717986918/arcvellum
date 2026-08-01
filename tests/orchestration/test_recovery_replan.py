from __future__ import annotations

import unittest

from literary_engineering_studio.orchestration import (
    RecoveryStep,
    ReplanBudgetState,
    ReplanTrigger,
    recovery_step,
    recovery_violations,
    replan_allowed,
    replan_budget_violations,
)


class RecoveryLadderTests(unittest.TestCase):
    def test_provider_unavailable_escalates_from_retry_to_stop(self):
        self.assertEqual(
            recovery_step("provider_unavailable", 1).step,
            RecoveryStep.RETRY,
        )
        self.assertEqual(
            recovery_step("provider_unavailable", 2).step,
            RecoveryStep.RETRY,
        )
        self.assertEqual(
            recovery_step("provider_unavailable", 3).step,
            RecoveryStep.SESSION_RENEW,
        )
        self.assertEqual(
            recovery_step("provider_unavailable", 4).step,
            RecoveryStep.STOP_WITH_EVIDENCE,
        )
        self.assertEqual(
            recovery_step("provider_unavailable", 9).step,
            RecoveryStep.STOP_WITH_EVIDENCE,
        )

    def test_process_crash_and_version_conflict_restore_then_replan(self):
        for failure in ("process_crash", "version_conflict"):
            self.assertEqual(
                recovery_step(failure, 1).step,
                RecoveryStep.CHECKPOINT_RESTORE,
            )
            self.assertEqual(
                recovery_step(failure, 2).step,
                RecoveryStep.BOUNDED_REPLAN,
            )
            self.assertEqual(
                recovery_step(failure, 3).step,
                RecoveryStep.STOP_WITH_EVIDENCE,
            )

    def test_no_progress_replans_once_then_stops(self):
        self.assertEqual(
            recovery_step("no_progress", 1).step,
            RecoveryStep.BOUNDED_REPLAN,
        )
        self.assertEqual(
            recovery_step("no_progress", 2).step,
            RecoveryStep.STOP_WITH_EVIDENCE,
        )

    def test_authorization_expired_renews_then_stops(self):
        self.assertEqual(
            recovery_step("authorization_expired", 1).step,
            RecoveryStep.SESSION_RENEW,
        )
        self.assertEqual(
            recovery_step("authorization_expired", 2).step,
            RecoveryStep.STOP_WITH_EVIDENCE,
        )

    def test_budget_exhausted_stops_without_retry(self):
        decision = recovery_step("budget_exhausted", 1)

        self.assertEqual(decision.step, RecoveryStep.STOP_WITH_EVIDENCE)
        self.assertEqual(decision.reasons, ())

    def test_unknown_failure_and_invalid_attempt_fail_closed(self):
        self.assertEqual(
            recovery_step("mystery", 1).step,
            RecoveryStep.STOP_WITH_EVIDENCE,
        )
        self.assertEqual(
            recovery_step("provider_unavailable", 0).step,
            RecoveryStep.STOP_WITH_EVIDENCE,
        )

    def test_recovery_violations(self):
        violations = recovery_violations("", 0)

        codes = {item.code for item in violations}
        self.assertEqual(codes, {"missing-failure-code", "invalid-attempt"})


class BoundedReplanTests(unittest.TestCase):
    def test_replan_allowed_within_budget(self):
        decision = replan_allowed(
            ReplanBudgetState(scope_key="chapter_01", replan_count=1),
            trigger=ReplanTrigger.REVIEW_FAILED,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reasons, ())

    def test_replan_budget_exhaustion_blocks(self):
        decision = replan_allowed(
            ReplanBudgetState(scope_key="chapter_01", replan_count=2),
            trigger=ReplanTrigger.REVIEW_FAILED,
        )

        self.assertFalse(decision.allowed)
        self.assertIn("replan-budget-exhausted", decision.reasons)

    def test_user_direction_replan_is_limited_after_first(self):
        decision = replan_allowed(
            ReplanBudgetState(scope_key="chapter_01", replan_count=1),
            trigger=ReplanTrigger.USER_DIRECTION_CHANGED,
        )

        self.assertFalse(decision.allowed)
        self.assertIn("user-direction-replan-limited", decision.reasons)

    def test_budget_state_violations(self):
        violations = replan_budget_violations(
            ReplanBudgetState(scope_key="", replan_count=-1, max_replans=0)
        )

        codes = {item.code for item in violations}
        self.assertEqual(
            codes,
            {
                "missing-scope-key",
                "invalid-replan-count",
                "invalid-max-replans",
            },
        )


if __name__ == "__main__":
    unittest.main()
