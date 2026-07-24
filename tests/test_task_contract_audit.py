from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine import task_registry
from literary_engineering_studio_engine.task_contract_audit import build_task_contract_audit
from literary_engineering_studio_engine.tasking.package_contract import TASK_TYPE_EXECUTION, enrich_task_payload


class TaskContractAuditTests(unittest.TestCase):
    def test_audit_accepts_current_semantic_task_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: Audit\n", encoding="utf-8")
            (root / "scenes").mkdir()
            (root / "scenes" / "scene_0001.yaml").write_text("scene_id: scene_0001\n", encoding="utf-8")
            task = task_registry._enrich_task_payload(
                task_registry._build_task_payload(
                    root,
                    "scene-development",
                    {"scene_id": "scene_0001", "scene": "scenes/scene_0001.yaml", "current_step": "roleplay-agent-task", "next_action": ""},
                )
            )
            task_dir = root / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            path = task_dir / f"{task['task_id']}.task.json"
            path.write_text(json.dumps(task), encoding="utf-8")
            result = build_task_contract_audit(root)
            self.assertEqual(result.error_count, 0)
            self.assertIn("lifecycle", task["system_owned_fields"])
            self.assertIn("semantic", task["system_owned_fields"])

            task["output_contracts"][0].pop("consumed_by", None)
            path.write_text(json.dumps(task), encoding="utf-8")
            result = build_task_contract_audit(root)
            self.assertGreater(result.error_count, 0)

    def test_audit_rejects_agent_task_without_machine_owned_completion_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: Audit\n", encoding="utf-8")
            (root / "scenes").mkdir()
            (root / "scenes" / "scene_0001.yaml").write_text("scene_id: scene_0001\n", encoding="utf-8")
            task = task_registry._enrich_task_payload(
                task_registry._build_task_payload(
                    root,
                    "scene-development",
                    {"scene_id": "scene_0001", "scene": "scenes/scene_0001.yaml", "current_step": "roleplay-agent-task", "next_action": ""},
                )
            )
            task["system_owned_fields"]["lifecycle"]["completion_receipts"] = []
            task_dir = root / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            (task_dir / f"{task['task_id']}.task.json").write_text(json.dumps(task), encoding="utf-8")

            result = build_task_contract_audit(root)

            self.assertGreater(result.error_count, 0)

    def test_every_agent_task_type_receives_a_machine_owned_lifecycle_contract(self):
        for task_type, (policy, _role) in TASK_TYPE_EXECUTION.items():
            if policy != "agent-required":
                continue
            with self.subTest(task_type=task_type):
                task = enrich_task_payload(
                    {
                        "schema": "literary-engineering-workbench/agent-task/v1",
                        "task_id": f"contract-{task_type}",
                        "route": "scene-development",
                        "scene_id": "scene_0001",
                        "current_state": "contract-check",
                        "task_type": task_type,
                        "prompt_asset_id": "route.scene-development.repair.v1",
                        "command": "",
                        "required_reading": [],
                        "source_paths": [],
                        "expected_outputs": ["workflow/contracts/result.md", "workflow/contracts/result.agent_completion.json"],
                        "hard_constraints": [],
                        "style_constraints": [],
                        "validation_gates": [],
                        "forbidden_shortcuts": [],
                    }
                )
                lifecycle = task["system_owned_fields"]["lifecycle"]
                self.assertEqual(lifecycle["task_identity"]["task_id"], task["task_id"])
                self.assertEqual(lifecycle["completion_receipts"][0]["path"], "workflow/contracts/result.agent_completion.json")
                self.assertEqual(lifecycle["completion_receipts"][0]["status"], "complete")


if __name__ == "__main__":
    unittest.main()
