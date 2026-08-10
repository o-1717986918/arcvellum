from __future__ import annotations

import unittest

from literary_engineering_studio.runtime.context_budget import ContextTaskKind
from literary_engineering_studio.runtime.reasoning_policy import (
    ReasoningAction,
    ReasoningUsage,
    decide_reasoning_action,
    resolve_reasoning_budget,
)
from literary_engineering_studio.observability.reasoning_benchmark_projection import (
    reasoning_budget_projection,
)


class ReasoningPolicyTests(unittest.TestCase):
    def test_budget_matrix_keeps_reasoning_separate_from_visible_output(self):
        structured = resolve_reasoning_budget(ContextTaskKind.STRUCTURED, "agent-required")
        review = resolve_reasoning_budget(ContextTaskKind.REVIEW, "agent-required")

        self.assertEqual((structured.initial_level, structured.maximum_level), ("minimal", "low"))
        self.assertEqual(structured.total_tokens, 768)
        self.assertEqual((review.initial_level, review.maximum_level), ("low", "medium"))
        self.assertEqual(review.total_tokens, 3_072)

    def test_deterministic_task_has_no_reasoning_budget(self):
        budget = resolve_reasoning_budget(ContextTaskKind.STRUCTURED, "deterministic")
        decision = decide_reasoning_action(budget, current_level="off", attempt=1)

        self.assertEqual(budget.total_tokens, 0)
        self.assertEqual(decision.action, ReasoningAction.STOP)
        self.assertEqual(decision.reason, "deterministic-task")

    def test_mechanical_failure_retries_without_escalating(self):
        budget = resolve_reasoning_budget(ContextTaskKind.REVIEW, "agent-required")
        decision = decide_reasoning_action(
            budget,
            current_level="low",
            attempt=1,
            issue_categories=("invalid-json", "missing_field"),
        )

        self.assertEqual(decision.action, ReasoningAction.RETRY_SAME)
        self.assertEqual(decision.level, "low")

    def test_semantic_conflict_allows_only_one_level_escalation(self):
        budget = resolve_reasoning_budget(ContextTaskKind.REVIEW, "agent-required")
        first = decide_reasoning_action(
            budget,
            current_level="low",
            attempt=1,
            issue_categories=("character_logic",),
        )
        exhausted = decide_reasoning_action(
            budget,
            current_level="medium",
            attempt=2,
            issue_categories=("character_logic",),
            usage=ReasoningUsage(escalations=1),
        )

        self.assertEqual(first.action, ReasoningAction.ESCALATE)
        self.assertEqual(first.level, "medium")
        self.assertEqual(exhausted.action, ReasoningAction.KEEP)
        self.assertEqual(exhausted.level, "medium")

    def test_second_identical_progress_fingerprint_stops(self):
        budget = resolve_reasoning_budget(ContextTaskKind.CREATIVE, "agent-required")
        decision = decide_reasoning_action(
            budget,
            current_level="low",
            attempt=2,
            issue_categories=("semantic_preflight",),
            repeated_progress_fingerprint=True,
        )

        self.assertEqual(decision.action, ReasoningAction.STOP)
        self.assertEqual(decision.reason, "same-progress-fingerprint-repeated")

    def test_total_or_request_budget_stops_before_retry(self):
        budget = resolve_reasoning_budget(ContextTaskKind.STRUCTURED, "agent-required")
        token_stop = decide_reasoning_action(
            budget,
            current_level="minimal",
            attempt=1,
            usage=ReasoningUsage(reasoning_tokens=budget.total_tokens),
        )
        request_stop = decide_reasoning_action(
            budget,
            current_level="minimal",
            attempt=1,
            usage=ReasoningUsage(provider_requests=budget.max_provider_requests),
        )

        self.assertEqual(token_stop.action, ReasoningAction.STOP)
        self.assertEqual(request_stop.action, ReasoningAction.STOP)

    def test_missing_provider_receipt_is_unavailable_not_zero(self):
        projection = reasoning_budget_projection(
            {
                "execution_profile": {
                    "reasoning_budget": {
                        "status": "shadow",
                        "provider_support": "unsupported",
                        "requested": {"total_tokens": 768},
                    }
                }
            },
            [],
            {"reasoning_tokens": 0},
        )

        self.assertEqual(projection["actual"]["reasoning_tokens"], "unavailable")
        self.assertFalse(projection["actual"]["reasoning_tokens_reported"])
        self.assertEqual(projection["comparison"]["reasoning_token_delta"], "unavailable")


if __name__ == "__main__":
    unittest.main()
