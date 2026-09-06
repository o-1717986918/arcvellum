from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.preflight.common import PreflightIssue
from literary_engineering_studio.preflight.style import validate_style_prompt_contract
from literary_engineering_studio.sandbox import SandboxManifest


class StylePromptPreflightTests(unittest.TestCase):
    def test_oversized_revision_is_rejected_before_writeback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            relative = "style/atelier/example/style_prompt.md"
            path = workspace / relative
            path.parent.mkdir(parents=True)
            path.write_text("汉，" * 1400, encoding="utf-8")
            task = TaskPackage(
                project_root=root,
                task_json_path=root / "task.json",
                task_markdown_path=root / "task.md",
                payload={
                    "task_id": "style-engineering-example-style-eval-revision",
                    "route": "style-engineering",
                    "current_state": "style-eval-revision",
                    "task_type": "platform-agent-revision",
                    "source_paths": [relative],
                    "expected_outputs": [relative],
                },
            )
            sandbox = SandboxManifest(
                run_id="style-length-test",
                run_root=root,
                workspace=workspace,
                prompt_path=root / "prompt.md",
                manifest_path=root / "manifest.json",
                baseline_path=root / "baseline.json",
                expected_outputs=task.expected_outputs,
            )
            issues: list[PreflightIssue] = []

            validate_style_prompt_contract(task, sandbox, issues)

            length_issue = next(item for item in issues if item.code == "style-prompt-length")
            self.assertIn("2800", length_issue.message)
            self.assertIn("不得机械截断", length_issue.repair)

    def test_unrelated_task_does_not_validate_a_source_prompt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            relative = "style/atelier/example/style_prompt.md"
            path = workspace / relative
            path.parent.mkdir(parents=True)
            path.write_text("汉，" * 1400, encoding="utf-8")
            task = TaskPackage(
                project_root=root,
                task_json_path=root / "task.json",
                task_markdown_path=root / "task.md",
                payload={
                    "task_id": "style-engineering-example-style-eval-agent-task",
                    "route": "style-engineering",
                    "current_state": "style-eval-agent-task",
                    "task_type": "platform-agent-evaluation",
                    "source_paths": [relative],
                    "expected_outputs": [
                        "style/atelier/example/evaluation_results/formal/candidate.md"
                    ],
                },
            )
            sandbox = SandboxManifest(
                run_id="style-source-test",
                run_root=root,
                workspace=workspace,
                prompt_path=root / "prompt.md",
                manifest_path=root / "manifest.json",
                baseline_path=root / "baseline.json",
                expected_outputs=task.expected_outputs,
            )
            issues: list[PreflightIssue] = []

            validate_style_prompt_contract(task, sandbox, issues)

            self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
