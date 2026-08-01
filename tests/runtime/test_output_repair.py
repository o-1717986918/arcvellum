from __future__ import annotations

import unittest

from literary_engineering_studio.runtime.output_repair import (
    OutputRepairRequest,
    repair_allowed,
    repair_request_violations,
)


def _request(**overrides):
    base = dict(
        task_id="task-1",
        bundle_id="scene-analysis-scene_0001-abc",
        invalid_outputs=("drafts/scenes/scene_0001.md",),
        preserved_outputs=("drafts/reviews/scene_0001_review.md",),
        preflight_issue_ids=("missing-output",),
        attempt=1,
    )
    base.update(overrides)
    return OutputRepairRequest(**base)


class OutputRepairTests(unittest.TestCase):
    def test_valid_request_is_allowed(self):
        request = _request()

        self.assertEqual(
            repair_request_violations(request, max_attempts=2),
            (),
        )
        self.assertTrue(repair_allowed(request, max_attempts=2).allowed)

    def test_preserved_outputs_are_never_repaired(self):
        request = _request(
            invalid_outputs=("drafts/reviews/scene_0001_review.md",),
        )

        codes = {
            item.code
            for item in repair_request_violations(request, max_attempts=2)
        }
        self.assertIn("preserved-output-targeted", codes)
        self.assertFalse(repair_allowed(request, max_attempts=2).allowed)

    def test_attempt_budget_is_bounded(self):
        for attempt in (0, 3):
            request = _request(attempt=attempt)
            codes = {
                item.code
                for item in repair_request_violations(request, max_attempts=2)
            }
            self.assertIn("attempt-out-of-budget", codes)

    def test_missing_identity_and_evidence_fail_closed(self):
        request = _request(
            task_id="",
            bundle_id="",
            invalid_outputs=(),
            preflight_issue_ids=(),
        )

        codes = {
            item.code
            for item in repair_request_violations(request, max_attempts=2)
        }
        self.assertEqual(
            codes,
            {
                "missing-task-id",
                "missing-bundle-id",
                "empty-invalid-outputs",
                "empty-preflight-issues",
            },
        )
        self.assertFalse(repair_allowed(request, max_attempts=2).allowed)

    def test_repair_allowed_reports_reason_codes(self):
        decision = repair_allowed(
            _request(attempt=9),
            max_attempts=2,
        )

        self.assertIn("attempt-out-of-budget", decision.reasons)


if __name__ == "__main__":
    unittest.main()
