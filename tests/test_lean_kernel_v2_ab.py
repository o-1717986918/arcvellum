from __future__ import annotations

import unittest

from literary_engineering_studio.observability.lean_kernel_ab import (
    LITERARY_DIMENSIONS,
    RouteEvidence,
    compare_routes,
)


class LeanKernelV2ABTests(unittest.TestCase):
    def setUp(self) -> None:
        self.strict = RouteEvidence("strict-v1", 8, 31, 8)
        self.lean = RouteEvidence("lean-v2-standard", 2, 5, 0)

    def test_structural_win_cannot_replace_missing_literary_evidence(self) -> None:
        report = compare_routes(self.strict, self.lean)

        self.assertEqual(report["decision"], "pending-literary-evidence")
        self.assertFalse(report["ready_for_default"])
        self.assertGreaterEqual(
            report["reductions"]["project_agent_task_files"],
            0.70,
        )

    def test_noninferior_blind_scores_open_the_default_gate(self) -> None:
        scores = {
            "strict-v1": {item: 4.0 for item in LITERARY_DIMENSIONS},
            "lean-v2": {item: 3.9 for item in LITERARY_DIMENSIONS},
        }

        report = compare_routes(self.strict, self.lean, literary_scores=scores)

        self.assertEqual(report["decision"], "ready-for-default")
        self.assertTrue(report["ready_for_default"])

    def test_incomplete_or_inferior_scores_keep_the_gate_closed(self) -> None:
        incomplete = compare_routes(
            self.strict,
            self.lean,
            literary_scores={"strict-v1": {}, "lean-v2": {}},
        )
        inferior = compare_routes(
            self.strict,
            self.lean,
            literary_scores={
                "strict-v1": {item: 4.5 for item in LITERARY_DIMENSIONS},
                "lean-v2": {item: 3.0 for item in LITERARY_DIMENSIONS},
            },
        )

        self.assertEqual(incomplete["decision"], "pending-literary-evidence")
        self.assertEqual(inferior["decision"], "hold")


if __name__ == "__main__":
    unittest.main()
