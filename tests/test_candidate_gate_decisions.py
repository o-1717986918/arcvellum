"""Ordered decision regressions for exact-candidate review gates."""

import unittest

from literary_engineering_studio_engine.literary.scene.promotion.review_gate import (
    _review_resolution_checks,
)


class CandidateGateDecisionTests(unittest.TestCase):
    def test_human_decision_note_blocks_before_generic_revision_notes(self):
        checks = _review_resolution_checks(
            {
                "human_decision_notes": ["age: choose the canonical age"],
                "new_character_issues": [],
                "unresolved": ["warnings"],
            }
        )

        first_failure = next(check for check in checks if not check.passed)
        self.assertEqual(first_failure.status, "human_decision_required")
        self.assertIn("choose the canonical age", first_failure.message)

    def test_clean_resolution_contract_has_no_failure(self):
        checks = _review_resolution_checks(
            {
                "human_decision_notes": [],
                "new_character_issues": [],
                "unresolved": [],
            }
        )

        self.assertTrue(all(check.passed for check in checks))


if __name__ == "__main__":
    unittest.main()
