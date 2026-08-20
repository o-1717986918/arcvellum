from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.observability.prompt_audit import (
    build_prompt_audit_report,
    render_prompt_audit_markdown,
)
from literary_engineering_studio.runtime.prompt_metrics import lint_prompt, measure_prompt


class PromptMetricsTests(unittest.TestCase):
    def test_measurement_is_content_safe_and_detects_duplicate_evidence(self):
        body = "这是足够长的正式证据。" * 12
        prompt = f"""# Task

必须完成正式输出。
必须完成正式输出。

----- BEGIN AUTHORIZED FILE: `canon/a.md` (sha256={'a' * 64}, characters={len(body)}) -----
{body}
----- END AUTHORIZED FILE: `canon/a.md` -----

----- BEGIN AUTHORIZED FILE: `canon/a.md` (sha256={'a' * 64}, characters={len(body)}) -----
{body}
----- END AUTHORIZED FILE: `canon/a.md` -----

### Exact On Demand
- `reviews/full.md`
"""
        metrics = measure_prompt(prompt)
        projection = metrics.safe_projection()
        self.assertEqual(metrics.unique_source_count, 1)
        self.assertEqual(metrics.source_occurrence_count, 2)
        self.assertEqual(metrics.duplicate_path_count, 1)
        self.assertEqual(metrics.duplicate_digest_count, 1)
        self.assertEqual(metrics.exact_on_demand_count, 1)
        self.assertGreater(metrics.evidence_characters, 0)
        self.assertGreater(metrics.nested_duplicate_characters, 0)
        self.assertNotIn(body, str(projection))

    def test_audit_report_does_not_expose_paths_or_prompt_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "AGENT_TASK.md"
            source.write_text("# Task\n\n不得跳过门禁。\n", encoding="utf-8")
            report = build_prompt_audit_report({"structured": source})
        rendered = render_prompt_audit_markdown(report)
        self.assertEqual(report["case_count"], 1)
        self.assertNotIn(str(source), str(report))
        self.assertNotIn("不得跳过门禁", str(report))
        self.assertIn("structured", rendered)

    def test_tool_worker_on_demand_instruction_is_not_counted_as_evidence(self):
        prompt = """## Exact On Demand

- `Dxxx` 仅为标签；按路径读取。
- `D001` `canon/facts.json` (canon): 按需读取
- `D002` `reviews/task.agent_tasks.md` (recovery): 仅预检点名才读

## Stop Contract
"""

        self.assertEqual(measure_prompt(prompt).exact_on_demand_count, 2)

    def test_machine_source_identities_preserve_metrics_when_paths_are_hidden(self):
        metrics = measure_prompt(
            "### E001: role=canon\n\n----- BEGIN EVIDENCE E001 -----\n事实\n----- END EVIDENCE E001 -----",
            source_identities=(("canon/world_rules.yaml", "a" * 64),),
        )

        self.assertEqual(metrics.unique_source_count, 1)
        self.assertEqual(metrics.duplicate_path_count, 0)

    def test_lint_rejects_direct_conflicts_and_tool_host_instructions(self):
        metrics = measure_prompt(
            "## Constraints\n\n- `C001` 必须修改 Canon。\n- `C002` 不得修改 Canon。\n"
            "- 先运行 task-submit 再继续。\n"
        )
        report = lint_prompt(
            metrics,
            hard_character_limit=10_000,
            output_count=1,
            reject_host_instructions=True,
        )

        self.assertEqual(report.status, "error")
        self.assertEqual(
            {item.code for item in report.issues},
            {"conflicting_constraints", "ineffective_host_instruction"},
        )

    def test_lint_rejects_incomplete_output_contract(self):
        report = lint_prompt(
            measure_prompt("完成任务。"),
            hard_character_limit=100,
            output_count=1,
            output_contract_complete=False,
        )

        self.assertEqual(report.issues[0].code, "incomplete_output_contract")


if __name__ == "__main__":
    unittest.main()
