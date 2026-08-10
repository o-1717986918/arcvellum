from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.runtime.context_budget import resolve_task_context_budget
from literary_engineering_studio.runtime.prompt_program import resolve_prompt_program_rollout
from literary_engineering_studio.runtime.sandbox import stage_task


class PromptProgramV3Tests(unittest.TestCase):
    def test_rollout_requires_explicit_enforcement_match(self):
        shadow = resolve_prompt_program_rollout(
            {"mode": "shadow"}, runtime_id="pi-worker", task_kind="structured"
        )
        self.assertEqual(shadow["formal_version"], "v2")
        self.assertTrue(shadow["emit_shadow"])

        enforced = resolve_prompt_program_rollout(
            {
                "mode": "enforced",
                "enforcement": {
                    "enabled": True,
                    "runtimes": ["pi-worker"],
                    "task_kinds": ["structured"],
                },
            },
            runtime_id="pi-worker",
            task_kind="structured",
        )
        self.assertEqual(enforced["formal_version"], "v3")
        self.assertFalse(enforced["emit_shadow"])

    def test_shadow_materialization_preserves_v2_and_keeps_exact_body_out(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("project:\n  title: 测试\n", encoding="utf-8")
            (root / "source.md").write_text("首轮正式证据。\n", encoding="utf-8")
            (root / "source-copy.md").write_text("首轮正式证据。\n", encoding="utf-8")
            exact_body = "只有遇到证据冲突时才读取的完整恢复材料。"
            (root / "exact.md").write_text(exact_body, encoding="utf-8")
            task = _task(root)
            budget = resolve_task_context_budget(task, {"context_budget": {"mode": "shadow"}})

            sandbox = stage_task(
                task,
                root / "runs",
                runtime="pi-worker",
                run_id="prompt-v3-shadow",
                context_budget=budget,
                prompt_program_config={"mode": "shadow", "fallback": "v2"},
            )

            formal = sandbox.prompt_path.read_text(encoding="utf-8")
            shadow_path = sandbox.run_root / "prompt-v3-shadow.md"
            shadow = shadow_path.read_text(encoding="utf-8")
            manifest = json.loads(sandbox.manifest_path.read_text(encoding="utf-8"))
            projection = manifest["prompt_program"]

            self.assertIn("ArcVellum Studio Worker Program", formal)
            self.assertNotIn("Prompt Program v3", formal)
            self.assertIn("Prompt Program v3", shadow)
            self.assertIn("`source.md`", shadow)
            self.assertIn("`exact.md`", shadow)
            self.assertNotIn(exact_body, shadow)
            self.assertEqual(projection["rollout"]["formal_version"], "v2")
            self.assertEqual(projection["shadow_path"], "prompt-v3-shadow.md")
            self.assertEqual(projection["shadow"]["metrics"]["unique_source_count"], 1)
            self.assertGreater(projection["shadow"]["metrics"]["evidence_characters"], 0)
            self.assertEqual(projection["shadow"]["program"]["evidence"][0]["source_ref"], "source.md")
            self.assertEqual(projection["shadow"]["program"]["compile_metrics"]["dropped_digest_count"], 1)
            self.assertNotIn("body", projection["shadow"]["program"]["evidence"][0])
            self.assertEqual(len(projection["shadow"]["program"]["digest"]), 64)

            repeated = stage_task(
                task,
                root / "runs",
                runtime="pi-worker",
                run_id="prompt-v3-shadow-repeat",
                context_budget=budget,
                prompt_program_config={"mode": "shadow", "fallback": "v2"},
            )
            repeated_manifest = json.loads(repeated.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(
                projection["shadow"]["program"]["digest"],
                repeated_manifest["prompt_program"]["shadow"]["program"]["digest"],
            )


def _task(root: Path) -> TaskPackage:
    payload = {
        "task_id": "structured-shadow",
        "route": "character-and-world-assets",
        "current_state": "asset-creation-agent-task",
        "task_type": "platform-agent-asset",
        "required_reading": [],
        "source_paths": ["source.md", "source-copy.md", "exact.md"],
        "agent_source_paths": ["source.md", "source-copy.md", "exact.md"],
        "expected_outputs": ["output.json"],
        "core_managed_outputs": [],
        "context_must_inline_paths": ["source.md", "source-copy.md"],
        "context_exact_on_demand_paths": ["exact.md"],
        "context_contract_status": "shadow-ready",
        "validation_gates": ["输出必须通过 JSON 预检"],
        "hard_constraints": ["不得改写正式输入"],
        "forbidden_shortcuts": [],
        "prompt_asset": {
            "resolved_id": "asset.structured.v1",
            "version": "1",
            "exact": True,
            "body": "生成一个结构化候选资产。",
            "output_contract": ["输出合法 JSON"],
            "review_requirements": ["检查事实来源"],
            "hard_constraints": [],
            "style_constraints": [],
            "forbidden_shortcuts": [],
        },
    }
    task_json = root / "task.json"
    task_markdown = root / "task.md"
    task_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    task_markdown.write_text("# Structured shadow task\n", encoding="utf-8")
    return TaskPackage(
        project_root=root,
        task_json_path=task_json,
        task_markdown_path=task_markdown,
        payload=payload,
    )


if __name__ == "__main__":
    unittest.main()
