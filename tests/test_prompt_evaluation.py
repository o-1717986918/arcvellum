from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.prompt_evaluation import HIGH_RISK_CASES, evaluate_prompt_assets, write_prompt_evaluation
from literary_engineering_studio.runtimes.claude_code import ClaudeCodeRuntime
from literary_engineering_studio.runtimes.opencode import OpenCodeRuntime


class PromptEvaluationTests(unittest.TestCase):
    def test_all_high_risk_assets_are_exact_and_pass(self):
        report = evaluate_prompt_assets()
        self.assertEqual(report["status"], "pass", report)
        self.assertEqual(report["case_count"], len(HIGH_RISK_CASES))
        self.assertTrue(all(case["exact"] for case in report["cases"]))

    def test_report_can_be_persisted(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "prompt-eval.json"
            report = write_prompt_evaluation(target)
            self.assertTrue(target.is_file())
            self.assertEqual(report["failure_count"], 0)

    def test_claude_and_opencode_transport_identical_prompt(self):
        with tempfile.TemporaryDirectory() as temporary:
            prompt = Path(temporary) / "AGENT_TASK.md"
            prompt.write_text("精确任务提示：只写 expected outputs。", encoding="utf-8")
            claude = ClaudeCodeRuntime({})
            opencode = OpenCodeRuntime({})
            self.assertEqual(claude.load_execution_prompt(prompt), opencode.load_execution_prompt(prompt))


if __name__ == "__main__":
    unittest.main()
