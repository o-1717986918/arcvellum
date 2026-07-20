import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.contracts import load_task_package, normalize_relative_path


class ContractTests(unittest.TestCase):
    def test_longform_review_parser_accepts_markdown_label_but_preserves_status(self):
        from literary_engineering_studio_engine.task_registry import _static_review_conclusion

        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "review.md"
            report.write_text("# Review\n\n- 审查结论：**pass_with_notes**\n", encoding="utf-8")
            self.assertEqual(_static_review_conclusion(report), "pass_with_notes")
            report.write_text("# Review\n\n- 结论： `pass`\n", encoding="utf-8")
            self.assertEqual(_static_review_conclusion(report), "pass")

    def test_deterministic_cli_with_prompt_asset_stays_deterministic(self):
        payload = {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.longform-planning.word-budget.prepare.v1",
            "command": "python -m literary_engineering_studio_engine word-budget <project> --target-words 30000",
        }
        from literary_engineering_studio.contracts import HumanGate, _derive_execution_policy

        self.assertEqual(_derive_execution_policy(payload, HumanGate(False, (), "test")), "deterministic")

    def test_rejects_path_traversal(self):
        for value in ("../secret", "C:/secret", "/absolute/path"):
            with self.assertRaises(ValueError):
                normalize_relative_path(value)

    def test_loads_valid_task(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task_dir = root / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            markdown = task_dir / "demo.agent_tasks.md"
            markdown.write_text("# task\n", encoding="utf-8")
            payload = {
                "schema": "literary-engineering-workbench/agent-task/v1",
                "task_id": "demo",
                "status": "opened",
                "route": "scene-development",
                "current_state": "prose-generation",
                "task_type": "platform-agent-prose",
                "prompt_asset_id": "route.scene-development.prose.generate.v1",
                "required_reading": [],
                "source_paths": ["scenes/scene_0001.yaml"],
                "expected_outputs": ["drafts/candidates/scene_0001.md"],
                "submission_command": "lew task-submit",
                "completion_command": "lew task-complete",
                "validation_gates": [],
                "forbidden_shortcuts": [],
                "task_markdown": "workflow/tasks/demo.agent_tasks.md",
            }
            task_json = task_dir / "demo.task.json"
            task_json.write_text(json.dumps(payload), encoding="utf-8")
            task = load_task_package(root, task_json)
            self.assertEqual(task.task_id, "demo")
            self.assertEqual(task.expected_outputs, ("drafts/candidates/scene_0001.md",))
            contract = task.execution_contract
            self.assertEqual(contract.execution_policy, "agent-required")
            self.assertEqual(contract.agent_role, "main-creative-agent")
            self.assertEqual(contract.writeback_policy, "preview-required")
            self.assertTrue(contract.compatibility_derived)

    def test_prefers_explicit_execution_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task_dir = root / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            (task_dir / "explicit.agent_tasks.md").write_text("# task\n", encoding="utf-8")
            payload = {
                "schema": "literary-engineering-workbench/agent-task/v1",
                "task_id": "explicit",
                "route": "canon-evolve",
                "current_state": "canon-apply",
                "task_type": "human-choice",
                "required_reading": [],
                "source_paths": [],
                "expected_outputs": ["canon/patches/scene_0001.json"],
                "validation_gates": [],
                "forbidden_shortcuts": [],
                "task_markdown": "workflow/tasks/explicit.agent_tasks.md",
                "execution_policy": "human-required",
                "agent_role": "human-decision",
                "human_gate": {"required": True, "reasons": ["canon-apply"]},
                "runtime_capabilities_required": [],
                "output_contracts": [
                    {
                        "path": "canon/patches/scene_0001.json",
                        "kind": "human-approval",
                        "writeback_policy": "approval-required",
                    }
                ],
            }
            task_json = task_dir / "explicit.task.json"
            task_json.write_text(json.dumps(payload), encoding="utf-8")
            task = load_task_package(root, task_json)
            self.assertFalse(task.execution_contract.compatibility_derived)
            self.assertTrue(task.human_gate.required)
            self.assertEqual(task.execution_contract.writeback_policy, "approval-required")


if __name__ == "__main__":
    unittest.main()
