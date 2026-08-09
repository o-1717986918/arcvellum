from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.observability.runtime_benchmark import (
    build_historical_runtime_report,
    load_benchmark_catalog,
    reconstruct_benchmark_case,
    render_historical_report_markdown,
)


CATALOG = Path(__file__).parent / "fixtures" / "runtime_benchmarks" / "catalog.json"


class RuntimeBenchmarkTests(unittest.TestCase):
    def test_catalog_covers_five_classes_and_marks_deep_prose_fixture_pending(self):
        cases = load_benchmark_catalog(CATALOG)
        self.assertEqual(len(cases), 5)
        self.assertEqual(
            {item.benchmark_class for item in cases},
            {"structured", "analysis", "prose", "review", "planning"},
        )
        prose = next(item for item in cases if item.benchmark_class == "prose")
        self.assertEqual(prose.availability, "pending-p0b")

    def test_all_ready_cases_are_reconstructed_through_real_deterministic_prefix(self):
        cases = [item for item in load_benchmark_catalog(CATALOG) if item.availability == "ready"]
        with tempfile.TemporaryDirectory() as temporary:
            results = [
                reconstruct_benchmark_case(case, Path(temporary) / case.case_id)
                for case in cases
            ]
        self.assertEqual(len(results), 4)
        self.assertEqual(
            {item.current_state for item in results},
            {
                "asset-creation-agent-task",
                "roleplay-agent-task",
                "canon-review-agent-task",
                "story-architecture-agent-task",
            },
        )
        for result in results:
            self.assertEqual(result.execution_policy, "agent-required")
            self.assertGreaterEqual(result.deterministic_steps, 1)
            self.assertEqual(len(result.task_contract_sha256), 64)
            self.assertNotIn("project_root", result.safe_projection())

    def test_historical_report_omits_paths_prompts_and_reasoning_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "project-private" / "run-private"
            run.mkdir(parents=True)
            (run / "run.json").write_text(
                json.dumps(
                    {
                        "run_id": "private-run",
                        "status": "complete",
                        "created_at": "2026-08-09T00:00:00+00:00",
                        "updated_at": "2026-08-09T00:00:02+00:00",
                        "runtime": "opencode",
                        "project_root": "C:/secret/work",
                        "task_id": "private-character-name-review",
                        "route": "review-and-audit",
                        "current_state": "canon-review-agent-task",
                        "prepared_context_characters": 1200,
                        "context_ledger_digest": "digest",
                        "context_budget": {"task_kind": "review", "mode": "shadow"},
                        "prepared_context_cache": {"status": "disabled"},
                        "execution_contract": {"agent_role": "main-review-agent"},
                        "runtime_metadata": {"time_to_first_event_ms": 200, "total_ms": 2000},
                    }
                ),
                encoding="utf-8",
            )
            (run / "runtime.events.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"event": "usage.updated", "at": "2026-08-09T00:00:01+00:00", "usage_id": "u1", "model": "model-a", "usage": {"input": 10, "output": 4, "reasoning": 3}, "cost_usd": 0.01}),
                        json.dumps({"event": "agent.message.completed", "at": "2026-08-09T00:00:02+00:00", "text": "SECRET PROSE AND REASONING"}),
                    ]
                ),
                encoding="utf-8",
            )
            report = build_historical_runtime_report(root)
            encoded = json.dumps(report, ensure_ascii=False)
            markdown = render_historical_report_markdown(report)
        self.assertEqual(report["sample_count"], 1)
        self.assertNotIn("C:/secret/work", encoded)
        self.assertNotIn("SECRET PROSE", encoded)
        self.assertNotIn("private-run", encoded)
        self.assertNotIn("private-character-name", encoded)
        self.assertIn("model-a", markdown)
        self.assertEqual(report["samples"][0]["usage"]["total_tokens"], 17)


if __name__ == "__main__":
    unittest.main()
