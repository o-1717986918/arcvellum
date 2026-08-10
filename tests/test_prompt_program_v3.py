from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.runtime.context_budget import resolve_task_context_budget
from literary_engineering_studio.runtime.prompt_program import (
    OnDemandEvidence,
    PromptProgram,
    resolve_prompt_program_rollout,
)
from literary_engineering_studio.runtime.prompt_renderer import render_tool_worker_program
from literary_engineering_studio.runtime.prompt_metrics import measure_prompt
from literary_engineering_studio.runtime.sandbox import stage_task


class PromptProgramV3Tests(unittest.TestCase):
    def test_tool_renderer_requires_exact_paths_instead_of_evidence_ids(self):
        program = PromptProgram(
            schema="arcvellum/prompt-program/v3",
            recipe_id="prompt-v3/structured/v1",
            task_identity={"task_id": "one", "route": "route", "current_state": "state", "agent_role": "agent"},
            objective="完成任务。",
            decisions=(),
            constraints=(),
            output_contract={"outputs": []},
            evidence=(),
            exact_on_demand=(
                OnDemandEvidence("D001", "exact.md", "digest", "recovery", "按需读取"),
            ),
            stop_contract=("完成后停止。",),
            compile_metrics={},
            digest="digest",
        )

        rendered = render_tool_worker_program(program)

        self.assertIn("`Dxxx` 仅为标签", rendered)
        self.assertIn("`read_authorized_source.path`", rendered)
        self.assertIn("`D001` `exact.md`", rendered)

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

        state_scoped = resolve_prompt_program_rollout(
            {
                "mode": "enforced",
                "enforcement": {
                    "enabled": True,
                    "runtimes": ["pi-worker"],
                    "routes": ["scene-development"],
                    "states": ["candidate-review"],
                    "task_kinds": ["review"],
                },
            },
            runtime_id="pi-worker",
            task_kind="review",
            route="scene-development",
            current_state="candidate-review",
        )
        self.assertEqual(state_scoped["formal_version"], "v3")
        wrong_state = resolve_prompt_program_rollout(
            {
                "mode": "enforced",
                "enforcement": {
                    "enabled": True,
                    "states": ["candidate-review"],
                },
            },
            runtime_id="pi-worker",
            task_kind="review",
            route="scene-development",
            current_state="canon-review-agent-task",
        )
        self.assertEqual(wrong_state["formal_version"], "v2")

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
            self.assertEqual(measure_prompt(shadow).exact_on_demand_count, 1)

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

    def test_uncontracted_recovery_material_is_demoted_but_machine_schema_remains(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("project:\n  title: 测试\n", encoding="utf-8")
            (root / "source.md").write_text("首轮正式证据。\n", encoding="utf-8")
            (root / "source-copy.md").write_text("不同的正式证据。\n", encoding="utf-8")
            (root / "exact.md").write_text("按需证据。\n", encoding="utf-8")
            sidecar_body = "这是一份不应进入首轮的完整恢复说明。"
            (root / "creation.agent_tasks.md").write_text(sidecar_body, encoding="utf-8")
            task = _task(root)
            task.payload["source_paths"].append("creation.agent_tasks.md")
            task.payload["agent_source_paths"].append("creation.agent_tasks.md")
            task.payload["context_must_inline_paths"].append("creation.agent_tasks.md")
            task.payload["system_owned_fields"] = {
                "candidate": {"schema": "candidate/v1", "path": "output.json"},
                "lifecycle": {"status": "complete"},
            }
            budget = resolve_task_context_budget(task, {"context_budget": {"mode": "shadow"}})

            sandbox = stage_task(
                task,
                root / "runs",
                runtime="pi-worker",
                run_id="recovery-demotion",
                context_budget=budget,
                prompt_program_config={"mode": "shadow", "fallback": "v2"},
            )
            shadow = (sandbox.run_root / "prompt-v3-shadow.md").read_text(encoding="utf-8")
            projection = json.loads(sandbox.manifest_path.read_text(encoding="utf-8"))["prompt_program"]["shadow"]

            self.assertNotIn(sidecar_body, shadow)
            self.assertIn("`creation.agent_tasks.md`", shadow)
            self.assertIn('"schema":"candidate/v1"', shadow)
            self.assertNotIn('"lifecycle"', shadow)
            self.assertEqual(projection["program"]["compile_metrics"]["demoted_recovery_count"], 1)
            self.assertEqual(projection["metrics"]["exact_on_demand_count"], 2)

    def test_enforced_v3_persists_compiled_prompt_access_for_demoted_recovery(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("project:\n  title: 测试\n", encoding="utf-8")
            (root / "source.md").write_text("首轮正式证据。\n", encoding="utf-8")
            (root / "source-copy.md").write_text("另一份首轮证据。\n", encoding="utf-8")
            (root / "exact.md").write_text("原始按需证据。\n", encoding="utf-8")
            (root / "creation.agent_tasks.md").write_text("恢复说明。\n", encoding="utf-8")
            task = _task(root)
            task.payload["source_paths"].append("creation.agent_tasks.md")
            task.payload["agent_source_paths"].append("creation.agent_tasks.md")
            task.payload["context_must_inline_paths"].append("creation.agent_tasks.md")
            budget = resolve_task_context_budget(task, {"context_budget": {"mode": "shadow"}})

            sandbox = stage_task(
                task,
                root / "runs",
                runtime="pi-worker",
                run_id="compiled-prompt-access",
                context_budget=budget,
                execution_profile={"runtime_id": "pi-worker"},
                prompt_program_config={
                    "mode": "enforced",
                    "fallback": "v2",
                    "enforcement": {
                        "enabled": True,
                        "runtimes": ["pi-worker"],
                        "states": ["asset-creation-agent-task"],
                    },
                },
            )
            context = json.loads(
                (sandbox.workspace / "TASK_CONTEXT.json").read_text(encoding="utf-8")
            )
            access = context["prompt_access"]

            self.assertEqual(access["formal_version"], "v3")
            self.assertEqual(access["renderer"], "tool-worker")
            self.assertIn("source.md", access["inline"])
            self.assertIn("creation.agent_tasks.md", access["exact_on_demand"])
            self.assertNotIn("creation.agent_tasks.md", access["inline"])
            self.assertIn(
                "creation.agent_tasks.md",
                context["controlled_capabilities"]["readable_paths"],
            )
            self.assertEqual(len(access["digest"]), 64)


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
