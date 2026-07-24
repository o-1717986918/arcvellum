import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.contracts import load_task_package
from literary_engineering_studio.sandbox import (
    apply_expected_outputs,
    capture_core_managed_outputs,
    changed_agent_outputs,
    import_expected_outputs,
    inspect_expected_outputs,
    materialize_agent_workspace,
    rollback_expected_outputs,
    sandbox_change_issues,
    restore_core_managed_outputs,
    stage_task,
)
from literary_engineering_studio_engine.task_registry import _enrich_task_payload
from literary_engineering_studio.runtime.task_program import build_task_context, render_worker_program
from literary_engineering_studio.task_preflight import validate_task_outputs


class SandboxTests(unittest.TestCase):
    def _task(self, root: Path):
        (root / "project.yaml").write_text("title: Demo\n", encoding="utf-8")
        source = root / "scenes" / "scene_0001.yaml"
        source.parent.mkdir(parents=True)
        source.write_text("scene_id: scene_0001\n", encoding="utf-8")
        task_dir = root / "workflow" / "tasks"
        task_dir.mkdir(parents=True)
        markdown = task_dir / "demo.agent_tasks.md"
        markdown.write_text("# Demo task\n", encoding="utf-8")
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
        return load_task_package(root, task_json)

    def test_imports_only_expected_output(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as runs:
            task = self._task(Path(temporary))
            sandbox = stage_task(task, Path(runs), runtime="host-agent", run_id="run-good")
            output = sandbox.workspace / "drafts" / "candidates" / "scene_0001.md"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("正文。\n", encoding="utf-8")
            imported = import_expected_outputs(task, sandbox)
            self.assertEqual(imported, ("drafts/candidates/scene_0001.md",))
            self.assertEqual((task.project_root / imported[0]).read_text(encoding="utf-8"), "正文。\n")

    def test_reports_only_fresh_substantive_agent_outputs_for_recovery(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as runs:
            task = self._task(Path(temporary))
            sandbox = stage_task(task, Path(runs), runtime="host-agent", run_id="run-recovery-freshness")
            self.assertEqual(changed_agent_outputs(sandbox), ())

            output = sandbox.workspace / "drafts" / "candidates" / "scene_0001.md"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("本次 Agent 实际写出的新正文。\n", encoding="utf-8")
            self.assertEqual(changed_agent_outputs(sandbox), ("drafts/candidates/scene_0001.md",))

    def test_rejects_source_modification(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as runs:
            task = self._task(Path(temporary))
            sandbox = stage_task(task, Path(runs), runtime="host-agent", run_id="run-bad")
            source = sandbox.workspace / "scenes" / "scene_0001.yaml"
            source.write_text("scene_id: changed\n", encoding="utf-8")
            output = sandbox.workspace / "drafts" / "candidates" / "scene_0001.md"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("正文。\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                import_expected_outputs(task, sandbox)

    def test_preview_precedes_writeback_and_detects_stale_target(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as runs:
            task = self._task(Path(temporary))
            target = task.project_root / "drafts" / "candidates" / "scene_0001.md"
            target.parent.mkdir(parents=True)
            target.write_text("旧正文。\n", encoding="utf-8")
            sandbox = stage_task(task, Path(runs), runtime="host-agent", run_id="run-preview")
            output = sandbox.workspace / "drafts" / "candidates" / "scene_0001.md"
            output.write_text("新正文。\n", encoding="utf-8")
            preview = inspect_expected_outputs(task, sandbox)
            self.assertEqual(preview.policy, "preview-required")
            self.assertIn("-旧正文。", str(preview.changes[0]["diff"]))
            self.assertEqual(target.read_text(encoding="utf-8"), "旧正文。\n")
            target.write_text("项目后来被修改。\n", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                apply_expected_outputs(task, sandbox, preview)

    def test_rollback_restores_preexisting_output(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as runs:
            task = self._task(Path(temporary))
            target = task.project_root / "drafts" / "candidates" / "scene_0001.md"
            target.parent.mkdir(parents=True)
            target.write_text("旧正文。\n", encoding="utf-8")
            sandbox = stage_task(task, Path(runs), runtime="host-agent", run_id="run-rollback")
            output = sandbox.workspace / "drafts" / "candidates" / "scene_0001.md"
            output.write_text("新正文。\n", encoding="utf-8")
            preview = inspect_expected_outputs(task, sandbox)
            imported = apply_expected_outputs(task, sandbox, preview)
            rollback_expected_outputs(task, sandbox, imported)
            self.assertEqual(target.read_text(encoding="utf-8"), "旧正文。\n")

    def test_mid_writeback_failure_restores_every_preexisting_output(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as runs:
            root = Path(temporary)
            task = self._task(root)
            payload = json.loads(task.task_json_path.read_text(encoding="utf-8"))
            payload["expected_outputs"] = [
                "drafts/candidates/scene_0001.md",
                "drafts/candidates/scene_0001.json",
            ]
            task.task_json_path.write_text(json.dumps(_enrich_task_payload(payload)), encoding="utf-8")
            task = load_task_package(root, task.task_json_path)
            first = root / "drafts/candidates/scene_0001.md"
            second = root / "drafts/candidates/scene_0001.json"
            first.parent.mkdir(parents=True)
            first.write_text("旧正文。\n", encoding="utf-8")
            second.write_text('{"old": true}\n', encoding="utf-8")
            sandbox = stage_task(task, Path(runs), runtime="host-agent", run_id="run-atomic-failure")
            (sandbox.workspace / "drafts/candidates/scene_0001.md").write_text("新正文。\n", encoding="utf-8")
            (sandbox.workspace / "drafts/candidates/scene_0001.json").write_text('{"new": true}\n', encoding="utf-8")
            preview = inspect_expected_outputs(task, sandbox)

            from literary_engineering_studio import sandbox as sandbox_module

            original = sandbox_module._copy_path_atomically
            calls = 0

            def fail_second(source, target):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("simulated second output failure")
                return original(source, target)

            with patch("literary_engineering_studio.sandbox._copy_path_atomically", side_effect=fail_second):
                with self.assertRaises(OSError):
                    apply_expected_outputs(task, sandbox, preview)

            self.assertEqual(first.read_text(encoding="utf-8"), "旧正文。\n")
            self.assertEqual(second.read_text(encoding="utf-8"), '{"old": true}\n')

    def test_exact_prompt_omits_host_manuals_but_keeps_domain_references(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as runs:
            root = Path(temporary)
            task = self._task(root)
            payload = json.loads(task.task_json_path.read_text(encoding="utf-8"))
            payload["required_reading"] = [
                "SKILL.md",
                "references/workflows.md",
                "docs/modules/domain-guide.md",
            ]
            payload.pop("prompt_asset", None)
            payload = _enrich_task_payload(payload)
            task.task_json_path.write_text(json.dumps(payload), encoding="utf-8")
            (root / "SKILL.md").write_text("host manual", encoding="utf-8")
            (root / "references").mkdir()
            (root / "references/workflows.md").write_text("large workflow map", encoding="utf-8")
            (root / "docs/modules").mkdir(parents=True)
            (root / "docs/modules/domain-guide.md").write_text("domain constraints", encoding="utf-8")

            compact_task = load_task_package(root, task.task_json_path)
            sandbox = stage_task(compact_task, Path(runs), runtime="opencode", run_id="run-compact")
            manifest = json.loads(sandbox.manifest_path.read_text(encoding="utf-8"))
            context = json.loads((sandbox.workspace / "TASK_CONTEXT.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["reference_paths"], ["docs/modules/domain-guide.md"])
            self.assertEqual(context["reference_paths"], ["docs/modules/domain-guide.md"])
            self.assertFalse((sandbox.workspace / "SKILL.md").exists())
            self.assertFalse((sandbox.workspace / "references/workflows.md").exists())
            self.assertTrue((sandbox.workspace / "docs/modules/domain-guide.md").is_file())

    def test_worker_program_shows_curated_agent_sources_not_cli_dependency_folders(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = self._task(root)
            payload = json.loads(task.task_json_path.read_text(encoding="utf-8"))
            payload["source_paths"] = ["scenes/scene_0001.yaml", "canon", "characters", "style"]
            payload["agent_source_paths"] = ["scenes/scene_0001.yaml", "memory/context_packets/scene_0001.md"]
            task.task_json_path.write_text(json.dumps(_enrich_task_payload(payload)), encoding="utf-8")
            task = load_task_package(root, task.task_json_path)

            context = build_task_context(task)
            program = render_worker_program(task)

            self.assertEqual(context["source_paths"], ["scenes/scene_0001.yaml", "memory/context_packets/scene_0001.md"])
            self.assertEqual(context["workspace_dependency_paths"], ["scenes/scene_0001.yaml", "canon", "characters", "style"])
            source_section = program.split("## Reference Material", 1)[0]
            self.assertNotIn("`canon`", source_section)
            self.assertIn("workspace_dependency_paths", program)

    def test_agent_sandbox_stages_only_curated_sources(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as runs:
            root = Path(temporary)
            task = self._task(root)
            (root / "canon").mkdir()
            (root / "canon" / "world_rules.yaml").write_text("rules: []\n", encoding="utf-8")
            payload = json.loads(task.task_json_path.read_text(encoding="utf-8"))
            payload["source_paths"] = ["scenes/scene_0001.yaml", "canon"]
            payload["agent_source_paths"] = ["scenes/scene_0001.yaml"]
            task.task_json_path.write_text(json.dumps(_enrich_task_payload(payload)), encoding="utf-8")
            task = load_task_package(root, task.task_json_path)

            sandbox = stage_task(task, Path(runs), runtime="opencode", run_id="run-curated-staging")

            self.assertTrue((sandbox.workspace / "scenes" / "scene_0001.yaml").is_file())
            self.assertFalse((sandbox.workspace / "canon").exists())

    def test_control_workspace_keeps_cli_dependencies_outside_agent_boundary(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as runs:
            root = Path(temporary)
            task = self._task(root)
            (root / "canon").mkdir()
            (root / "canon" / "world_rules.yaml").write_text("rules: []\n", encoding="utf-8")
            payload = json.loads(task.task_json_path.read_text(encoding="utf-8"))
            payload["command"] = "python -m core-command <project>"
            payload["source_paths"] = ["scenes", "canon"]
            payload["agent_source_paths"] = ["scenes/scene_0001.yaml"]
            task.task_json_path.write_text(json.dumps(_enrich_task_payload(payload)), encoding="utf-8")
            task = load_task_package(root, task.task_json_path)

            sandbox = stage_task(task, Path(runs), runtime="opencode", run_id="run-core-boundary")
            self.assertFalse((sandbox.workspace / "canon").exists())
            self.assertTrue((sandbox.control_workspace / "canon" / "world_rules.yaml").is_file())
            (sandbox.control_workspace / "memory").mkdir()
            (sandbox.control_workspace / "memory" / "command-cache.json").write_text("{}\n", encoding="utf-8")
            materialize_agent_workspace(task, sandbox)

            self.assertFalse((sandbox.workspace / "canon").exists())
            self.assertTrue((sandbox.workspace / "scenes" / "scene_0001.yaml").is_file())
            self.assertFalse((sandbox.workspace / "memory").exists())
            self.assertTrue((sandbox.control_workspace / "memory" / "command-cache.json").is_file())
            self.assertEqual(sandbox_change_issues(sandbox), [])
            (sandbox.workspace / "scenes" / "scene_0001.yaml").write_text("scene_id: changed\n", encoding="utf-8")
            self.assertTrue(sandbox_change_issues(sandbox))

    def test_preflight_does_not_assign_worker_completion_receipts_to_agent(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as runs:
            root = Path(temporary)
            task = self._task(root)
            payload = json.loads(task.task_json_path.read_text(encoding="utf-8"))
            payload["current_state"] = "bounded-agent-output"
            payload["task_type"] = "platform-agent-judgment"
            payload["prompt_asset_id"] = "route.scene-development.agent-review.v1"
            payload["expected_outputs"] = [
                "reviews/agent/scene_0001_scene_review.md",
                "reviews/agent/scene_0001_scene_review.agent_completion.json",
            ]
            task.task_json_path.write_text(json.dumps(_enrich_task_payload(payload)), encoding="utf-8")
            task = load_task_package(root, task.task_json_path)
            sandbox = stage_task(task, Path(runs), runtime="opencode", run_id="run-receipt-boundary")
            review = sandbox.workspace / "reviews" / "agent" / "scene_0001_scene_review.md"
            review.parent.mkdir(parents=True, exist_ok=True)
            review.write_text("- 审查结论： revise_required\n", encoding="utf-8")

            result = validate_task_outputs(task, sandbox)

            missing = {issue.path for issue in result.issues if issue.code == "missing-output"}
            self.assertNotIn("reviews/agent/scene_0001_scene_review.agent_completion.json", missing)

    def test_composition_review_program_exposes_terminal_json_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = self._task(root)
            composition_dir = root / "drafts" / "compositions"
            composition_dir.mkdir(parents=True)
            (composition_dir / "scene_0001_composition.json").write_text('{"scene_id":"scene_0001"}\n', encoding="utf-8")
            review = composition_dir / "scene_0001_composition_review.json"
            review.write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/composition-review/v1",
                        "scene_id": "scene_0001",
                        "status": "pending_agent_judgment",
                        "source_artifact": "drafts/compositions/scene_0001_composition.json",
                        "composition_sha256": "digest-from-cli",
                        "evidence_paths": [],
                        "verdict": "pending",
                        "findings": [],
                        "required_changes": [],
                        "ready_for_generation": False,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            payload = json.loads(task.task_json_path.read_text(encoding="utf-8"))
            payload.update(
                {
                    "current_state": "composition-agent-task",
                    "task_type": "platform-agent-judgment",
                    "prompt_asset_id": "route.scene-development.composition.review.execute.v1",
                    "source_paths": [
                        "scenes/scene_0001.yaml",
                        "drafts/compositions/scene_0001_composition.json",
                        "drafts/compositions/scene_0001_composition_review.json",
                    ],
                    "expected_outputs": [
                        "drafts/compositions/scene_0001_composition_review.json",
                        "drafts/compositions/scene_0001_composition.agent_completion.json",
                    ],
                    "semantic_artifact": {
                        "path": "drafts/compositions/scene_0001_composition_review.json",
                        "kind": "composition-review",
                        "schema_name": "composition_review.v1",
                        "consumed_by": "candidate-generation-provenance",
                        "writeback_policy": "preview-required",
                    },
                }
            )
            task.task_json_path.write_text(json.dumps(_enrich_task_payload(payload)), encoding="utf-8")
            composition_task = load_task_package(root, task.task_json_path)

            context = build_task_context(composition_task)
            program = render_worker_program(composition_task)

            self.assertEqual(context["semantic_output_contract"]["pass_requirements"]["status"], "complete")
            self.assertEqual(context["semantic_output_contract"]["pass_requirements"]["verdict"], "pass")
            self.assertIn("pending 初始模板", program)
            self.assertIn("`status`: `complete`", program)
            self.assertIn("`verdict`: `pass`", program)
            self.assertIn("Studio 会在语义成果通过预检后自动写入执行回执", program)
            allowed = program.split("## Semantic Evidence", 1)[0]
            self.assertIn("scene_0001_composition_review.json", allowed)
            self.assertNotIn("scene_0001_composition.agent_completion.json", allowed)

    def test_continuity_ledger_program_exposes_delta_completion_requirements(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = self._task(root)
            ledger = root / "plot" / "ledger_deltas" / "scene_0001.json"
            ledger.parent.mkdir(parents=True)
            ledger.write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/continuity-ledger-delta/v1",
                        "status": "pending_agent_judgment",
                        "scene_id": "scene_0001",
                        "source_draft": "drafts/scenes/scene_0001.md",
                        "source_draft_sha256": "",
                        "writer_session_id": "",
                        "evidence_paths": [],
                        "reader_question_changes": [],
                        "promise_changes": [],
                        "no_change_reason": "",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            payload = json.loads(task.task_json_path.read_text(encoding="utf-8"))
            payload.update(
                {
                    "current_state": "continuity-ledger-agent-task",
                    "scene_id": "scene_0001",
                    "task_type": "platform-agent-judgment",
                    "prompt_asset_id": "route.scene-development.continuity-ledger.v1",
                    "source_paths": ["scenes/scene_0001.yaml", "plot/ledger_deltas/scene_0001.json"],
                    "expected_outputs": [
                        "plot/ledger_deltas/scene_0001.json",
                        "plot/ledger_deltas/scene_0001.agent_completion.json",
                    ],
                }
            )
            task.task_json_path.write_text(json.dumps(_enrich_task_payload(payload)), encoding="utf-8")
            ledger_task = load_task_package(root, task.task_json_path)

            context = build_task_context(ledger_task)
            program = render_worker_program(ledger_task)

            self.assertEqual(context["semantic_output_contract"]["continuity_kind"], "delta")
            self.assertIn("pending_agent_judgment", program)
            self.assertIn("no_change_reason", program)
            self.assertIn("不要编辑 `plot/reader_questions/ledger.json`", program)
            allowed = program.split("## Semantic Evidence", 1)[0]
            self.assertIn("scene_0001.json", allowed)
            self.assertNotIn("scene_0001.agent_completion.json", allowed)

    def test_state_review_program_exposes_terminal_json_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = self._task(root)
            state_dir = root / "characters" / "state_patches"
            state_dir.mkdir(parents=True)
            (state_dir / "scene_0001_state_patch.json").write_text('{"scene_id":"scene_0001"}\n', encoding="utf-8")
            review = state_dir / "scene_0001_state_patch_review.json"
            review.write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/state-patch-review/v1",
                        "scene_id": "scene_0001",
                        "status": "pending_agent_judgment",
                        "source_artifact": "characters/state_patches/scene_0001_state_patch.json",
                        "state_patch_sha256": "digest-from-cli",
                        "evidence_paths": [],
                        "verdict": "pending",
                        "findings": [],
                        "approval_recommendation": "hold",
                        "required_changes": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            payload = json.loads(task.task_json_path.read_text(encoding="utf-8"))
            payload.update(
                {
                    "current_state": "state-agent-task",
                    "task_type": "platform-agent-review",
                    "prompt_asset_id": "route.scene-development.state-evolve.execute.v1",
                    "source_paths": [
                        "scenes/scene_0001.yaml",
                        "characters/state_patches/scene_0001_state_patch.json",
                        "characters/state_patches/scene_0001_state_patch_review.json",
                    ],
                    "expected_outputs": [
                        "characters/state_patches/scene_0001_state_patch_review.json",
                        "characters/state_patches/scene_0001_state_patch.agent_completion.json",
                    ],
                    "semantic_artifact": {
                        "path": "characters/state_patches/scene_0001_state_patch_review.json",
                        "kind": "state-patch-review",
                        "schema_name": "state_patch_review.v1",
                        "consumed_by": "canon-patch-json",
                        "writeback_policy": "preview-required",
                    },
                }
            )
            task.task_json_path.write_text(json.dumps(_enrich_task_payload(payload)), encoding="utf-8")
            state_task = load_task_package(root, task.task_json_path)

            context = build_task_context(state_task)
            program = render_worker_program(state_task)

            self.assertEqual(context["prompt_asset"]["resolved_id"], "route.scene-development.state-evolve.execute.v1")
            self.assertEqual(context["semantic_output_contract"]["pass_requirements"]["status"], "complete")
            self.assertEqual(context["semantic_output_contract"]["pass_requirements"]["verdict"], "pass")
            self.assertEqual(context["semantic_output_contract"]["pass_requirements"]["approval_recommendation"], "approve")
            self.assertIn("`approval_recommendation`: `approve`", program)
            self.assertIn("Do not create or edit an agent_completion marker.", program)
            allowed = program.split("## Semantic Evidence", 1)[0]
            self.assertIn("scene_0001_state_patch_review.json", allowed)
            self.assertNotIn("scene_0001_state_patch.agent_completion.json", allowed)

    def test_restores_cli_managed_outputs_after_agent_mutation(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as runs:
            root = Path(temporary)
            task = self._task(root)
            payload = json.loads(task.task_json_path.read_text(encoding="utf-8"))
            payload["expected_outputs"] = [
                "drafts/candidates/scene_0001.md",
                "drafts/candidates/scene_0001.prompt.json",
            ]
            payload["core_managed_outputs"] = ["drafts/candidates/scene_0001.prompt.json"]
            task.task_json_path.write_text(json.dumps(_enrich_task_payload(payload)), encoding="utf-8")
            task = load_task_package(root, task.task_json_path)
            sandbox = stage_task(task, Path(runs), runtime="opencode", run_id="run-protected")
            core_protected = sandbox.control_workspace / "drafts" / "candidates" / "scene_0001.prompt.json"
            core_protected.parent.mkdir(parents=True, exist_ok=True)
            core_protected.write_text('{"source":"cli"}\n', encoding="utf-8")

            self.assertEqual(capture_core_managed_outputs(task, sandbox), ("drafts/candidates/scene_0001.prompt.json",))
            materialize_agent_workspace(task, sandbox)
            protected = sandbox.workspace / "drafts" / "candidates" / "scene_0001.prompt.json"
            protected.write_text('{"source":"agent"}\n', encoding="utf-8")

            self.assertEqual(restore_core_managed_outputs(sandbox), ("drafts/candidates/scene_0001.prompt.json",))
            self.assertEqual(protected.read_text(encoding="utf-8"), '{"source":"cli"}\n')


if __name__ == "__main__":
    unittest.main()
