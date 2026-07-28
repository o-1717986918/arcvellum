from __future__ import annotations

import unittest

from literary_engineering_studio.runtime.context_ab_reporting import (
    CONTEXT_AB_SCHEMA,
)
from literary_engineering_studio.runtime.context_ab_suite import (
    CONTEXT_AB_SUITE_SCHEMA,
    build_context_ab_suite_report,
)


class ContextABSuiteTests(unittest.TestCase):
    def test_three_safe_samples_and_rollback_form_exit_candidate(self):
        reports = [
            _report(
                f"scene-{index}",
                token_reduction=token,
                visible_reduction=visible,
            )
            for index, token, visible in (
                (1, 0.4, 0.5),
                (2, 0.5, 0.6),
                (3, 0.6, 0.7),
            )
        ]

        suite = build_context_ab_suite_report(
            reports,
            rollback_drill=_rollback(True),
        )

        self.assertEqual(suite["schema"], CONTEXT_AB_SUITE_SCHEMA)
        self.assertTrue(suite["exit_candidate"])
        self.assertEqual(
            suite["distributions"][
                "non_cached_input_token_reduction"
            ]["median"],
            0.5,
        )
        self.assertEqual(
            suite["distributions"]["bounded_elapsed_seconds"]["p95"],
            90.0,
        )
        self.assertEqual(suite["repair_retry"]["baseline"], "zero")

    def test_single_sample_token_and_review_regression_fail_closed(self):
        report = _report(
            "scene-one",
            token_reduction=-0.0923,
            visible_reduction=0.542,
            bounded_review="pass_with_notes",
        )

        suite = build_context_ab_suite_report(
            [report],
            rollback_drill=_rollback(True),
        )

        self.assertFalse(suite["exit_candidate"])
        self.assertFalse(
            suite["criteria"]["multi_scene_sample"]
        )
        self.assertFalse(
            suite["criteria"][
                "median_non_cached_input_token_reduction_at_least_40_percent"
            ]
        )
        self.assertFalse(
            suite["criteria"]["review_quality_not_degraded"]
        )

    def test_missing_usage_and_rollback_cannot_be_inferred(self):
        reports = [
            _report(
                f"scene-{index}",
                token_reduction=None,
                visible_reduction=0.6,
            )
            for index in range(3)
        ]

        suite = build_context_ab_suite_report(reports)

        self.assertFalse(suite["exit_candidate"])
        self.assertFalse(
            suite["criteria"][
                "median_non_cached_input_token_reduction_at_least_40_percent"
            ]
        )
        self.assertFalse(suite["criteria"]["rollback_drill_passed"])


def _report(
    task_id: str,
    *,
    token_reduction: float | None,
    visible_reduction: float,
    bounded_review: str = "pass",
) -> dict[str, object]:
    required = {
        "same_model": True,
        "requested_modes_applied": True,
        "both_complete": True,
        "both_first_preflight_pass": True,
        "both_reviews_non_fail": True,
        "review_schema_present_and_equal": True,
        "bounded_did_not_add_repair_or_retry_turns": True,
        "bounded_context_reduction_at_least_50_percent": True,
        "bounded_mandatory_complete": True,
        "bounded_tiers_disjoint": True,
        "original_project_unchanged": True,
    }
    return {
        "schema": CONTEXT_AB_SCHEMA,
        "task_id": task_id,
        "route": "scene-development",
        "runtime": "opencode",
        "arms": {
            "shadow": _arm("pass", 1000, 100.0),
            "bounded": _arm(bounded_review, 500, 90.0),
        },
        "comparison": {
            "non_cached_input_token_reduction": token_reduction,
            "first_turn_visible_character_reduction": (
                visible_reduction
            ),
        },
        "criteria": required,
    }


def _arm(
    conclusion: str,
    input_tokens: int,
    elapsed: float,
) -> dict[str, object]:
    return {
        "model_identity": "provider/model",
        "elapsed_seconds": elapsed,
        "repairs": 0,
        "retries": 0,
        "usage": {"non_cached_input_tokens": input_tokens},
        "context_access": {
            "exact_on_demand_read_characters": 0,
        },
        "review": {
            "conclusion": conclusion,
            "blocking_issue_count": 0,
        },
    }


def _rollback(passed: bool) -> dict[str, object]:
    return {
        "schema": "arcvellum/context-rollout-rollback-drill/v1",
        "task_count": 2,
        "criteria": {"all_shadow": passed},
        "passed": passed,
    }


if __name__ == "__main__":
    unittest.main()
