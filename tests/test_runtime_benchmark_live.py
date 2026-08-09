from __future__ import annotations

import unittest

from literary_engineering_studio.observability.runtime_benchmark import BenchmarkCase
from literary_engineering_studio.observability.runtime_benchmark_live import _unavailable


class RuntimeBenchmarkLiveTests(unittest.TestCase):
    def test_unavailable_report_is_content_safe_and_explicit(self):
        case = BenchmarkCase(
            case_id="analysis",
            benchmark_class="analysis",
            fixture_id="fixture",
            title="title",
            premise="premise",
            work_type="novel",
            target_length=30000,
            route="scene-development",
            preparation="deterministic-prefix",
            expected_state="roleplay-agent-task",
            availability="ready",
            rationale="rationale",
        )
        report = _unavailable(case, "opencode", "runner missing")
        self.assertEqual(report["status"], "evidence-insufficient")
        self.assertEqual(report["failure_kind"], "runner-unavailable")
        self.assertEqual(report["sample"], {})
        self.assertNotIn("premise", str(report))


if __name__ == "__main__":
    unittest.main()
