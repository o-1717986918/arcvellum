import unittest

from literary_engineering_studio.application.failures import (
    failure_identity,
    present_failure,
    present_run,
)


class FailurePresentationTests(unittest.TestCase):
    def test_issue_20_prompt_limit_becomes_actionable_chinese_contract(self):
        raw = (
            "Pi Worker Prompt v3 lint failed; refusing legacy v2 fallback: "
            "prompt hard limit exceeded: 67021 > 48000"
        )

        failure = present_failure(raw)

        self.assertIsNotNone(failure)
        assert failure is not None
        self.assertEqual(failure.code, "prompt_input_over_budget")
        self.assertIn("资料过多", failure.title)
        self.assertEqual(failure.technical_detail, raw)
        self.assertEqual(failure.recovery_actions[0].action_id, "compact-and-resume")

    def test_issue_20_runtime_failures_have_distinct_stable_codes(self):
        repair = present_failure("repair timeout")
        stalled = present_failure("no-progress guard stopped 2 identical turns")
        preflight = present_failure("sandbox output still fails deterministic preflight")

        self.assertEqual(repair.code, "repair_timed_out")
        self.assertEqual(stalled.code, "agent_no_progress")
        self.assertEqual(preflight.code, "output_validation_failed")

    def test_unresolved_state_patch_is_not_misreported_as_missing_receipt(self):
        failure = present_failure(
            "state patch has unresolved character or relationship changes; "
            "rebuild the patch contract instead of repeating semantic review"
        )

        self.assertIsNotNone(failure)
        assert failure is not None
        self.assertEqual(failure.code, "state_writeback_needs_revision")
        self.assertIn("重新归属", failure.title)

    def test_run_projection_keeps_diagnostic_nested_but_humanizes_compat_field(self):
        raw = "no-progress guard stopped 2 identical turns"

        projected = present_run(
            {
                "run_id": "run-1",
                "status": "paused",
                "last_error": raw,
                "stop_reason": "repeated-task-failure",
            }
        )

        self.assertNotEqual(projected["last_error"], raw)
        self.assertEqual(projected["failure"]["technical_detail"], raw)
        self.assertEqual(projected["failure"]["schema"], "arcvellum/failure-presentation/v1")

    def test_failure_identity_ignores_attempt_suffix_and_changing_wording(self):
        first = failure_identity(
            "sidecar incomplete: 2 files",
            route="scene-development",
            task_id="scene-review-attempt-1",
        )
        second = failure_identity(
            "sidecar incomplete: 5 files",
            route="scene-development",
            task_id="scene-review-attempt-2",
        )

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
