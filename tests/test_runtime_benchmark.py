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
from literary_engineering_studio.application.config import default_config
from literary_engineering_studio.runtime.engine_bridge import CoreBridge


CATALOG = Path(__file__).parent / "fixtures" / "runtime_benchmarks" / "catalog.json"


class RuntimeBenchmarkTests(unittest.TestCase):
    def test_catalog_covers_five_ready_runtime_classes(self):
        cases = load_benchmark_catalog(CATALOG)
        self.assertEqual(len(cases), 6)
        self.assertEqual(
            {item.benchmark_class for item in cases},
            {"structured", "analysis", "prose", "review", "planning"},
        )
        self.assertTrue(all(item.availability == "ready" for item in cases))

    def test_all_ready_cases_are_reconstructed_through_real_route_prefix(self):
        cases = [item for item in load_benchmark_catalog(CATALOG) if item.availability == "ready"]
        with tempfile.TemporaryDirectory() as temporary:
            results = [
                reconstruct_benchmark_case(case, Path(temporary) / case.case_id)
                for case in cases
            ]
        self.assertEqual(len(results), 6)
        self.assertEqual(
            {item.current_state for item in results},
            {
                "asset-creation-agent-task",
                "roleplay-agent-task",
                "candidate-generation-provenance",
                "candidate-review",
                "canon-review-agent-task",
                "story-architecture-agent-task",
            },
        )
        for result in results:
            self.assertEqual(result.execution_policy, "agent-required")
            self.assertGreaterEqual(result.deterministic_steps, 1)
            self.assertEqual(
                result.preparation_steps,
                result.deterministic_steps + result.synthetic_agent_steps,
            )
            self.assertEqual(len(result.task_contract_sha256), 64)
            self.assertNotIn("project_root", result.safe_projection())
        prose = next(item for item in results if item.benchmark_class == "prose")
        self.assertEqual(prose.synthetic_agent_steps, 3)
        scene_review = next(item for item in results if item.case_id == "review-scene-candidate")
        self.assertEqual(scene_review.synthetic_agent_steps, 4)

    def test_scene_review_benchmark_uses_exact_candidate_context_contract(self):
        case = next(
            item
            for item in load_benchmark_catalog(CATALOG)
            if item.case_id == "review-scene-candidate"
        )
        with tempfile.TemporaryDirectory() as temporary:
            result = reconstruct_benchmark_case(case, Path(temporary) / case.case_id)
            task = json.loads(
                (result.project_root / "workflow" / "tasks" / f"{result.task_id}.task.json").read_text(
                    encoding="utf-8"
                )
            )
            candidate = "drafts/candidates/scene_0001-platform-agent.md"
            evidence = task.get("context_evidence_contract")
            self.assertEqual(task["current_state"], "candidate-review")
            self.assertEqual(task["candidate"], candidate)
            self.assertIn(candidate, task["agent_source_paths"])
            self.assertIsInstance(evidence, dict)
            self.assertEqual(
                evidence.get("schema"),
                "literary-engineering-workbench/scene-review-context-declaration/v1",
            )
            CoreBridge(default_config()).execute_task_command(
                task["command"],
                result.project_root,
            )
            context = json.loads(
                (result.project_root / evidence["artifact_path"]).read_text(encoding="utf-8")
            )
            self.assertEqual(
                context.get("schema"),
                "literary-engineering-workbench/scene-review-context/v1",
            )
            self.assertEqual(context["candidate"]["path"], candidate)
            self.assertEqual(context["deterministic_evidence"]["style_lint"]["status"], "pass")

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
                        "runtime_metadata": {
                            "time_to_process_ready_ms": 20,
                            "time_to_session_created_ms": 40,
                            "time_to_prompt_submitted_ms": 60,
                            "time_to_first_reasoning_ms": 120,
                            "time_to_first_event_ms": 200,
                            "time_to_first_output_ms": 350,
                            "total_ms": 2000,
                        },
                    }
                ),
                encoding="utf-8",
            )
            (run / "runtime.events.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"event": "runtime_started", "at": "2026-08-09T00:00:00+00:00"}),
                        json.dumps({"event": "runner.ready", "at": "2026-08-09T00:00:00.020000+00:00"}),
                        json.dumps({"event": "runner.session.created", "at": "2026-08-09T00:00:00.040000+00:00"}),
                        json.dumps({"event": "runner.reasoning.started", "at": "2026-08-09T00:00:00.120000+00:00"}),
                        json.dumps({"event": "agent.message.delta", "at": "2026-08-09T00:00:00.350000+00:00", "text": "SECRET PROSE"}),
                        json.dumps({"event": "usage.updated", "at": "2026-08-09T00:00:01+00:00", "usage_id": "u1", "model": "model-a", "usage": {"input": 10, "output": 4, "reasoning": 3}, "cost_usd": 0.01}),
                        json.dumps({"event": "agent.message.completed", "at": "2026-08-09T00:00:02+00:00", "text": "SECRET PROSE AND REASONING"}),
                        json.dumps({"event": "runtime_finished", "at": "2026-08-09T00:00:02+00:00"}),
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
        self.assertEqual(report["samples"][0]["time_to_first_reasoning_ms"], 120)
        self.assertEqual(report["samples"][0]["time_to_first_event_ms"], 200)
        self.assertEqual(report["samples"][0]["time_to_first_output_ms"], 350)
        self.assertEqual(report["samples"][0]["persisted_event_count"], 8)


if __name__ == "__main__":
    unittest.main()
