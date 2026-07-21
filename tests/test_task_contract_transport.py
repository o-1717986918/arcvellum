from pathlib import Path
import json
import re
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.contracts import load_task_package
from literary_engineering_studio_engine.agent_task_status import build_agent_task_status, build_route_audit
import literary_engineering_studio_engine.task_registry as task_registry
from literary_engineering_studio_engine.platform_agent_tasks import write_project_seed_asset_tasks
from literary_engineering_studio_engine.task_registry import _enrich_task_payload, _render_task_markdown, complete_task, submit_task


class TaskContractTransportTests(unittest.TestCase):
    def test_project_asset_intake_is_a_concrete_deterministic_command(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
            results = write_project_seed_asset_tasks(root)

            self.assertEqual(len(results), 2)
            self.assertTrue((root / "canon/candidates/world_rules/world-foundation.agent_tasks.md").is_file())
            self.assertTrue((root / "characters/candidates/protagonist-foundation.agent_tasks.md").is_file())
            blueprint = task_registry._asset_blueprint_for_state(
                root,
                "asset-intake",
                "",
                "",
                "asset-intake",
                "",
            )
            self.assertEqual(
                blueprint["command"],
                "python -m literary_engineering_studio_engine seed-project-assets <project>",
            )
            self.assertNotIn("<type>", blueprint["command"])
            self.assertEqual(len(blueprint["expected_outputs"]), 2)

    def test_asset_promotion_declares_the_formal_asset_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "characters/candidates/protagonist-foundation.json"
            candidate.parent.mkdir(parents=True)
            candidate.write_text(
                json.dumps(
                    {
                        "candidate_id": "protagonist-foundation",
                        "asset_type": "character",
                        "character_id": "protagonist-foundation",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            blueprint = task_registry._asset_blueprint_for_state(
                root,
                "protagonist-foundation",
                "character",
                candidate.relative_to(root).as_posix(),
                "asset-promotion",
                "",
            )
            self.assertIn("characters/protagonist-foundation.yaml", blueprint["expected_outputs"])

    def test_export_and_publish_declare_every_deterministic_delivery_write(self):
        root = Path(".").resolve()
        export = task_registry._export_release_blueprint_for_state(
            root,
            "chapter_0001",
            "export-package",
            "",
        )
        self.assertEqual(len(export["expected_outputs"]), 13)
        self.assertIn("exports/chapter_0001/chapter_0001_novel.docx", export["expected_outputs"])
        self.assertIn("exports/chapter_0001/chapter_0001_novel.layout.json", export["expected_outputs"])
        self.assertIn("exports/chapter_0001/chapter_0001_novel.inspection.json", export["expected_outputs"])

        publish = task_registry._export_release_blueprint_for_state(
            root,
            "chapter_0001",
            "publish-release",
            "",
        )
        self.assertIn("releases/chapter_0001/formal-release/chapter_0001_novel.md", publish["expected_outputs"])
        self.assertIn("releases/chapter_0001/formal-release/chapter_0001_novel.docx", publish["expected_outputs"])
        self.assertIn("reviews/canon_lint.json", publish["expected_outputs"])

    def test_fresh_scene_blueprint_does_not_require_future_review_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text(
                "scene_id: scene_0001\nchapter_id: chapter_0001\n",
                encoding="utf-8",
            )

            blueprint = task_registry._blueprint_for_state(
                root,
                "scene_0001",
                "scenes/scene_0001.yaml",
                "context-packet",
                "",
            )

            self.assertEqual(blueprint["task_type"], "deterministic-cli")
            self.assertIn("memory/context_packets/scene_0001.md", blueprint["expected_outputs"])
            self.assertIn("memory/index.json", blueprint["expected_outputs"])

    def test_candidate_generation_transports_declared_missing_character_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("project:\n  title: 潮线\n", encoding="utf-8")
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text(
                "scene_id: scene_0001\nchapter_id: chapter_0001\nparticipants: [林昭, 林正]\n",
                encoding="utf-8",
            )
            (root / "characters").mkdir()
            (root / "characters" / "hero.yaml").write_text("name: 林昭\n", encoding="utf-8")

            blueprint = task_registry._blueprint_for_state(
                root, "scene_0001", "scenes/scene_0001.yaml", "candidate-generation-provenance", ""
            )

            self.assertIn("characters/candidates/scene-0001-林正.json", blueprint["expected_outputs"])
            self.assertEqual(blueprint["scene_character_assets"][0]["name"], "林正")
            payload = task_registry._build_task_payload(
                root,
                "scene-development",
                {
                    "scene_id": "scene_0001",
                    "scene": "scenes/scene_0001.yaml",
                    "current_step": "candidate-generation-provenance",
                },
            )
            self.assertIn(
                "drafts/candidates/scene_0001-platform-agent.prompt.json",
                payload["core_managed_outputs"],
            )
            self.assertIn(
                "characters/candidates/scene-0001-林正.agent_tasks.md",
                payload["core_managed_outputs"],
            )

    def test_candidate_review_transports_its_schema_and_protects_the_cli_sidecar(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("project:\n  title: 潮线\n", encoding="utf-8")
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text("scene_id: scene_0001\nchapter_id: chapter_0001\n", encoding="utf-8")

            blueprint = task_registry._blueprint_for_state(
                root, "scene_0001", "scenes/scene_0001.yaml", "candidate-review", ""
            )

            self.assertEqual(blueprint["candidate"], "drafts/candidates/scene_0001-platform-agent.md")
            self.assertIn("--materialization-scope scene", blueprint["command"])
            self.assertIn("schemas/agent_outputs/scene_review.v1.schema.json", blueprint["source_paths"])
            self.assertIn(
                "reviews/agent/scene_0001_scene_review.agent_tasks.md",
                blueprint["core_managed_outputs"],
            )

            revision = task_registry._blueprint_for_state(
                root, "scene_0001", "scenes/scene_0001.yaml", "candidate-revision", ""
            )
            self.assertIn("drafts/revisions/scene_0001_revision.prompt.json", revision["core_managed_outputs"])
            self.assertIn("drafts/revisions/scene_0001_revision.agent_tasks.md", revision["core_managed_outputs"])
            self.assertIn("plot/chapter_obligations/chapter_0001.json", revision["source_paths"])
            self.assertIn("plot/rhythm_plan.json", revision["source_paths"])

            decision = task_registry._blueprint_for_state(
                root, "scene_0001", "scenes/scene_0001.yaml", "candidate-human-decision", ""
            )
            self.assertEqual(decision["task_type"], "human-approval-boundary")
            self.assertEqual(decision["expected_outputs"], [])
            self.assertIn("candidate_sha256", " ".join(decision["hard_constraints"]))

    def test_scene_deterministic_handoffs_transport_upstream_completion_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("project:\n  title: 潮线\n", encoding="utf-8")
            (root / "workflow").mkdir(parents=True)
            (root / "workflow" / "longform_materialization.json").write_text(
                '{"status": "materialized", "scene_count": 1}\n', encoding="utf-8"
            )
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text(
                "scene_id: scene_0001\nchapter_id: chapter_0001\n",
                encoding="utf-8",
            )

            branch = task_registry._blueprint_for_state(
                root, "scene_0001", "scenes/scene_0001.yaml", "branch-manifest", ""
            )
            self.assertIn(
                "branches/scene_0001/roleplay_simulation.agent_tasks.md",
                branch["source_paths"],
            )
            self.assertIn(
                "branches/scene_0001/roleplay_simulation.agent_completion.json",
                branch["source_paths"],
            )
            self.assertIn(
                "branches/scene_0001/branch_selection.md",
                branch["expected_outputs"],
            )

            composition = task_registry._blueprint_for_state(
                root, "scene_0001", "scenes/scene_0001.yaml", "composition-json", ""
            )
            self.assertIn(
                "branches/scene_0001/branch_manifest.agent_completion.json",
                composition["source_paths"],
            )
            self.assertIn("project.yaml", composition["source_paths"])

            rhythm = task_registry._blueprint_for_state(
                root, "scene_0001", "scenes/scene_0001.yaml", "scene-rhythm-contract", ""
            )
            self.assertEqual(rhythm["expected_outputs"], ["scenes/scene_0001.yaml"])
            self.assertIn("narrative rhythm/bridge contract passes", rhythm["validation_gates"])

            generation = task_registry._blueprint_for_state(
                root,
                "scene_0001",
                "scenes/scene_0001.yaml",
                "candidate-generation-provenance",
                "",
            )
            self.assertIn("--materialization-scope scene", generation["command"])
            for relative in (
                "branches/scene_0001/roleplay_simulation.agent_completion.json",
                "branches/scene_0001/branch_manifest.agent_completion.json",
                "drafts/compositions/scene_0001_composition.agent_completion.json",
                "workflow/longform_materialization.json",
                "plot/word_budget/word_budget.agent_tasks.md",
                "plot/word_budget/word_budget.agent_completion.json",
                "reviews/word_budget/word_budget_review.md",
            ):
                self.assertIn(relative, generation["source_paths"])

    def test_composition_gate_reads_ready_flag_from_flow_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            composition = root / "drafts" / "compositions" / "scene_0001_composition.json"
            composition.parent.mkdir(parents=True)
            composition.write_text(
                json.dumps(
                    {
                        "selection_source": "selection",
                        "selected_branch": "branch_a",
                        "flow_gate": {"ready_for_generation": True},
                        "formal_cli_provenance": {
                            "created_by": "compose-scene",
                            "agent_tasks_requested": True,
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            self.assertEqual(task_registry._composition_gate_errors(root, "scene_0001"), [])

    def test_revision_promotion_targets_exact_current_candidate_and_overwrites_formal_draft(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text(
                "scene_id: scene_0001\nchapter_id: chapter_0001\n",
                encoding="utf-8",
            )
            revision = root / "drafts" / "revisions" / "scene_0001_revision.md"
            revision.parent.mkdir(parents=True)
            revision.write_text("## 正文候选\n\n修订正文。\n", encoding="utf-8")
            draft = root / "drafts" / "scenes" / "scene_0001.md"
            draft.parent.mkdir(parents=True)
            draft.write_text("## 正文草稿\n\n旧正文。\n", encoding="utf-8")

            blueprint = task_registry._blueprint_for_state(
                root, "scene_0001", "scenes/scene_0001.yaml", "promotion-manifest", ""
            )

            self.assertIn("--candidate drafts/revisions/scene_0001_revision.md", blueprint["command"])
            self.assertIn("--overwrite", blueprint["command"])
            self.assertIn("drafts/revisions/scene_0001_revision.agent_completion.json", blueprint["source_paths"])

    def test_scene_task_selection_uses_incremental_state_instead_of_full_route_scan(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
            scenes = root / "scenes"
            scenes.mkdir()
            for index in range(1, 4):
                (scenes / f"scene_{index:04d}.yaml").write_text(
                    f"scene_id: scene_{index:04d}\nchapter_id: chapter_0001\n",
                    encoding="utf-8",
                )

            with patch.object(task_registry, "build_workflow_state", side_effect=AssertionError("full scan used")):
                result = task_registry.issue_next_task(root, route="scene-development")

            self.assertEqual(result.scene_id, "scene_0001")
            self.assertEqual(result.current_state, "context-packet")

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
        self.assertEqual(task["submission_command"], "")
        self.assertEqual(task["completion_command"], "")

    def test_human_boundary_markdown_never_instructs_an_agent_to_submit_or_complete(self):
        task = _enrich_task_payload(
            {
                "task_id": "scene-development-scene_0001-candidate-human-decision",
                "route": "scene-development",
                "scene_id": "scene_0001",
                "current_state": "candidate-human-decision",
                "task_type": "human-approval-boundary",
                "prompt_asset_id": "route.scene-development.cross-asset-alignment.v1",
                "expected_outputs": [],
            }
        )
        rendered = _render_task_markdown(task, Path("."))
        self.assertIn("## Human Decision Boundary", rendered)
        self.assertNotIn("## Agent Execution", rendered)
        self.assertNotIn("task-submit", rendered)
        self.assertNotIn("task-complete", rendered)
        self.assertNotIn(".agent_completion.json", rendered)

    def test_human_decision_task_is_not_counted_as_an_unfinished_agent_sidecar(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task_dir = root / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            human_task = task_dir / "scene-human-decision.agent_tasks.md"
            human_task.write_text("- execution_policy: `human-required`\n", encoding="utf-8")
            (task_dir / "scene-human-decision.task.json").write_text(
                json.dumps({"execution_policy": "human-required"}), encoding="utf-8"
            )
            agent_task = task_dir / "scene-agent.agent_tasks.md"
            agent_task.write_text(
                "- route: `scene-development`\n- 创建或覆盖 `drafts/candidates/scene_0001.md`\n",
                encoding="utf-8",
            )
            (task_dir / "scene-agent.task.json").write_text(
                json.dumps({"route": "scene-development", "execution_policy": "agent-required"}), encoding="utf-8"
            )

            result = build_agent_task_status(root)
            payload = json.loads(result.json_path.read_text(encoding="utf-8"))
            self.assertEqual(result.task_count, 1)
            self.assertEqual(result.pending_count, 1)
            self.assertEqual(len(payload["tasks"]), 1)
            self.assertEqual(payload["tasks"][0]["path"], "workflow/tasks/scene-agent.agent_tasks.md")
            self.assertEqual(payload["tasks"][0]["route"], "scene-development")

    def test_submit_and_complete_require_exact_declared_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task_dir = root / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            output = root / "drafts" / "candidates" / "scene_0001.md"
            output.parent.mkdir(parents=True)
            output.write_text("正文。\n", encoding="utf-8")
            undeclared = root / "workflow" / "tasks" / "other.md"
            undeclared.write_text("not declared\n", encoding="utf-8")
            task_id = "scene-development-scene_0001-prose"
            (task_dir / f"{task_id}.task.json").write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/agent-task/v1",
                        "task_id": task_id,
                        "route": "scene-development",
                        "scene_id": "scene_0001",
                        "scene": "scenes/scene_0001.yaml",
                        "status": "opened",
                        "expected_outputs": ["drafts/candidates/scene_0001.md"],
                        "execution_policy": "agent-required",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "prior exact task-submit"):
                complete_task(root, task_id)
            with self.assertRaisesRegex(ValueError, "not declared"):
                submit_task(root, task_id, [output, undeclared])
            submitted = submit_task(root, task_id, [output])
            self.assertEqual(submitted.status, "submitted")

    def test_scene_route_audit_excludes_not_started_planned_scenes_from_failures(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: Audit Scope\n", encoding="utf-8")
            scenes = root / "scenes"
            scenes.mkdir()
            (scenes / "scene_0001.yaml").write_text("scene_id: scene_0001\n", encoding="utf-8")
            (scenes / "scene_0002.yaml").write_text("scene_id: scene_0002\n", encoding="utf-8")
            context = root / "memory" / "context_packets" / "scene_0001.md"
            context.parent.mkdir(parents=True)
            context.write_text("# started\n", encoding="utf-8")

            result = build_route_audit(root, route="scene-development")
            payload = json.loads(result.json_path.read_text(encoding="utf-8"))
            keys = [str(item["key"]) for item in payload["gates"]]
            self.assertIn("scene_0001:context-packet", keys)
            self.assertNotIn("scene_0002:context-packet", keys)
            self.assertEqual(payload["summary"]["scene_scope"]["started_scene_count"], 1)
            self.assertEqual(payload["summary"]["scene_scope"]["planned_scene_count"], 1)

    def test_scene_route_audit_marks_later_stages_as_waiting_not_parallel_failures(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: Audit Stages\n", encoding="utf-8")
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text("scene_id: scene_0001\n", encoding="utf-8")
            context = root / "memory" / "context_packets" / "scene_0001.md"
            context.parent.mkdir(parents=True)
            context.write_text("# started\n", encoding="utf-8")

            result = build_route_audit(root, route="scene-development")
            payload = json.loads(result.json_path.read_text(encoding="utf-8"))
            gates = {str(item["key"]): item for item in payload["gates"]}

            self.assertEqual(gates["scene_0001:context-trace"]["status"], "fail")
            self.assertEqual(gates["scene_0001:context-trace"]["severity"], "blocking")
            self.assertEqual(gates["scene_0001:roleplay-simulation"]["status"], "waiting")
            self.assertEqual(gates["scene_0001:roleplay-simulation"]["severity"], "info")
            self.assertEqual(gates["scene_0001:promotion-manifest"]["status"], "waiting")
            self.assertGreater(payload["summary"]["waiting_count"], 0)

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

    def test_active_task_auto_refreshes_when_executable_contract_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
            first = task_registry.issue_next_task(root, route="character-and-world-assets")
            self.assertEqual(first.status, "issued")
            payload = json.loads(first.task_json_path.read_text(encoding="utf-8"))
            payload["status"] = "opened"
            payload["expected_outputs"] = ["obsolete/output.json"]
            first.task_json_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            refreshed = task_registry.issue_next_task(root, route="character-and-world-assets")
            current = json.loads(refreshed.task_json_path.read_text(encoding="utf-8"))
            self.assertEqual(refreshed.status, "issued")
            self.assertEqual(current["refreshed_from_status"], "opened")
            self.assertNotIn("obsolete/output.json", current["expected_outputs"])


if __name__ == "__main__":
    unittest.main()
