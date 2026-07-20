from pathlib import Path
import json
import re
import tempfile
import unittest

from literary_engineering_studio.contracts import load_task_package
import literary_engineering_studio_engine.task_registry as task_registry
from literary_engineering_studio_engine.task_registry import _enrich_task_payload, _render_task_markdown


class TaskContractTransportTests(unittest.TestCase):
    def test_every_declared_task_type_has_an_exact_execution_contract(self):
        source = Path(task_registry.__file__).read_text(encoding="utf-8")
        declared = set(re.findall(r'"task_type"\s*:\s*"([^"]+)"', source))
        self.assertTrue(declared)
        self.assertEqual(declared - set(task_registry.TASK_TYPE_EXECUTION), set())

    def test_exact_prompt_metadata_and_explicit_contract_reach_agent_prompt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = _enrich_task_payload(
                {
                    "schema": "literary-engineering-workbench/agent-task/v1",
                    "task_id": "scene-development-scene_0001-candidate-generation-provenance",
                    "status": "issued",
                    "route": "scene-development",
                    "scene_id": "scene_0001",
                    "current_state": "candidate-generation-provenance",
                    "task_type": "main-platform-agent-prose",
                    "prompt_asset_id": "route.scene-development.prose.generate.v1",
                    "command": "",
                    "required_reading": [],
                    "source_paths": ["scenes/scene_0001.yaml"],
                    "expected_outputs": [
                        "drafts/candidates/scene_0001-platform-agent.md",
                        "drafts/candidates/scene_0001-platform-agent.agent_completion.json",
                    ],
                    "hard_constraints": [],
                    "style_constraints": [],
                    "validation_gates": [],
                    "forbidden_shortcuts": [],
                    "submission_command": "lew task-submit",
                    "completion_command": "lew task-complete",
                }
            )

            prompt_asset = task["prompt_asset"]
            self.assertEqual(prompt_asset["resolved_id"], "route.scene-development.prose.generate.v1")
            self.assertTrue(prompt_asset["exact"])
            self.assertTrue(prompt_asset["required_inputs"])
            self.assertTrue(prompt_asset["hard_constraints"])
            self.assertTrue(prompt_asset["review_requirements"])
            self.assertTrue(prompt_asset["forbidden_shortcuts"])
            self.assertTrue(prompt_asset["body"])
            self.assertEqual(task["execution_policy"], "agent-required")
            self.assertEqual(task["agent_role"], "main-creative-agent")
            self.assertEqual(task["human_gate"]["source"], "task-registry")
            self.assertEqual(
                task["runtime_capabilities_required"],
                ["read-task-sources", "write-expected-outputs"],
            )
            self.assertEqual(task["output_contracts"][0]["writeback_policy"], "preview-required")
            self.assertEqual(task["output_contracts"][1]["kind"], "completion-evidence")

            task_dir = root / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            task_json = task_dir / f"{task['task_id']}.task.json"
            task_markdown = task_dir / f"{task['task_id']}.agent_tasks.md"
            task["task_markdown"] = task_markdown.relative_to(root).as_posix()
            task_json.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
            task_markdown.write_text(_render_task_markdown(task, root), encoding="utf-8")

            rendered = task_markdown.read_text(encoding="utf-8")
            for heading in (
                "### Prompt Required Inputs",
                "### Prompt Context Groups",
                "### Prompt Hard Constraints",
                "### Prompt Style Constraints",
                "### Prompt Output Contract",
                "### Prompt Review Requirements",
                "### Prompt Forbidden Shortcuts",
                "### Prompt Body",
            ):
                self.assertIn(heading, rendered)
            loaded = load_task_package(root, task_json)
            self.assertFalse(loaded.execution_contract.compatibility_derived)
            self.assertEqual(loaded.execution_contract.agent_role, "main-creative-agent")

    def test_human_boundary_is_explicit_and_has_no_runtime_capabilities(self):
        task = _enrich_task_payload(
            {
                "task_id": "export-release-chapter_0001-release-approval",
                "route": "export-and-release",
                "scene_id": "chapter_0001",
                "current_state": "release-approval",
                "task_type": "human-approval-boundary",
                "prompt_asset_id": "route.export-release.approval.v1",
                "expected_outputs": ["workflow/approvals/index.jsonl"],
            }
        )
        self.assertEqual(task["execution_policy"], "human-required")
        self.assertEqual(task["agent_role"], "human-decision")
        self.assertEqual(task["human_gate"]["reasons"], ["release-approval"])
        self.assertEqual(task["runtime_capabilities_required"], [])
        self.assertEqual(task["output_contracts"][0]["writeback_policy"], "approval-required")

    def test_reopening_an_explicit_future_task_preserves_its_contract(self):
        task = _enrich_task_payload(
            {
                "task_id": "future-explicit-task",
                "route": "scene-development",
                "current_state": "future-state",
                "task_type": "future-task-type",
                "prompt_asset_id": "route.scene-development.prose.generate.v1",
                "expected_outputs": [],
                "execution_policy": "agent-required",
                "agent_role": "future-agent-role",
                "human_gate": {"required": False, "reasons": [], "source": "future-registry"},
                "runtime_capabilities_required": ["read-task-sources"],
                "output_contracts": [],
            }
        )
        self.assertEqual(task["agent_role"], "future-agent-role")
        self.assertEqual(task["human_gate"]["source"], "future-registry")


if __name__ == "__main__":
    unittest.main()
