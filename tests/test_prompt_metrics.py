from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.observability.prompt_audit import (
    build_prompt_audit_report,
    render_prompt_audit_markdown,
)
from literary_engineering_studio.runtime.prompt_metrics import measure_prompt


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


if __name__ == "__main__":
    unittest.main()
