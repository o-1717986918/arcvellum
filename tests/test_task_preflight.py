from pathlib import Path
import hashlib
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.contracts import TASK_SCHEMA, TaskPackage, load_task_package
from literary_engineering_studio.sandbox import SandboxManifest, stage_task
from literary_engineering_studio.task_preflight import (
    COMPLETION_SCHEMA,
    _semantic_artifact_repair_instruction,
    canonicalize_task_outputs,
    validate_task_outputs,
)


class TaskPreflightTests(unittest.TestCase):
    def test_continuity_delta_pending_template_is_repaired_before_core_writeback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            draft = workspace / "drafts" / "scenes" / "scene_0001.md"
            draft.parent.mkdir(parents=True)
            draft.write_text("已晋升正文。", encoding="utf-8")
            delta = workspace / "plot" / "ledger_deltas" / "scene_0001.json"
            delta.parent.mkdir(parents=True)
            delta.write_text(
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
            task = TaskPackage(
                project_root=root,
                task_json_path=root / "task.json",
                task_markdown_path=root / "task.md",
                payload={
                    "task_id": "scene-development-scene-0001-continuity-ledger-agent-task",
                    "route": "scene-development",
                    "scene_id": "scene_0001",
                    "current_state": "continuity-ledger-agent-task",
                    "task_type": "platform-agent-judgment",
                    "execution_policy": "agent-required",
                    "expected_outputs": ["plot/ledger_deltas/scene_0001.json"],
                },
            )
            sandbox = SandboxManifest(
                run_id="test",
                run_root=root,
                workspace=workspace,
                prompt_path=root / "prompt.md",
                manifest_path=root / "manifest.json",
                baseline_path=root / "baseline.json",
                expected_outputs=task.expected_outputs,
            )
            sandbox.baseline_path.write_text(
                json.dumps(
                    {"drafts/scenes/scene_0001.md": hashlib.sha256(draft.read_bytes()).hexdigest()}
                ),
                encoding="utf-8",
            )

            canonicalize_task_outputs(task, sandbox)
            failed = validate_task_outputs(task, sandbox)
            self.assertFalse(failed.passed)
            issue = next(item for item in failed.issues if item.code == "continuity-ledger-contract")
            self.assertIn("incomplete", issue.message)
            self.assertIn("no_change_reason", issue.repair)

            payload = json.loads(delta.read_text(encoding="utf-8"))
            payload.update({"status": "complete", "no_change_reason": "本场没有新增或改变读者责任。"})
            delta.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            canonicalize_task_outputs(task, sandbox)
            self.assertTrue(validate_task_outputs(task, sandbox).passed)

    def test_state_semantic_repair_instruction_names_every_terminal_field(self):
        instruction = _semantic_artifact_repair_instruction(
            "state-agent-task",
            "characters/state_patches/scene_0001_state_patch_review.json",
        )
        self.assertIn('status="complete"', instruction)
        self.assertIn('verdict="pass"', instruction)
        self.assertIn('approval_recommendation="approve"', instruction)
        self.assertIn("不要自行创建 completion marker", instruction)

    def test_roleplay_completed_status_alias_is_normalized_before_gate_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            workspace.mkdir()
            roleplay = workspace / "branches" / "scene_0001" / "roleplay_result.json"
            roleplay.parent.mkdir(parents=True)
            roleplay.write_text(
                json.dumps(
                    {
                        "schema": "wrong",
                        "scene_id": "wrong-scene",
                        "status": "completed",
                        "source_artifact": "wrong.md",
                        "evidence_paths": ["scenes/scene_0001.yaml"],
                        "character_actions": [{"action": "test"}],
                        "world_consequences": [{"impact": "test"}],
                        "branch_pressures": [{"pressure": "test"}],
                        "canon_risks": [],
                        "writeback_candidates": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            task = TaskPackage(
                project_root=root,
                task_json_path=root / "task.json",
                task_markdown_path=root / "task.md",
                payload={
                    "task_id": "scene-development-scene-0001-roleplay-agent-task",
                    "route": "scene-development",
                    "current_state": "roleplay-agent-task",
                    "scene_id": "scene_0001",
                    "expected_outputs": ["branches/scene_0001/roleplay_result.json"],
                },
            )
            sandbox = SandboxManifest(
                run_id="test",
                run_root=root,
                workspace=workspace,
                prompt_path=root / "prompt.md",
                manifest_path=root / "manifest.json",
                baseline_path=root / "baseline.json",
                expected_outputs=task.expected_outputs,
            )

            changes = canonicalize_task_outputs(task, sandbox)

            normalized = json.loads(roleplay.read_text(encoding="utf-8"))
            self.assertEqual(normalized["schema"], "literary-engineering-workbench/roleplay-result/v1")
            self.assertEqual(normalized["scene_id"], "scene_0001")
            self.assertEqual(normalized["status"], "complete")
            self.assertEqual(normalized["source_artifact"], "branches/scene_0001/roleplay_simulation.md")
            self.assertTrue(changes)

    def test_roleplay_single_writeback_candidate_is_wrapped_without_content_rewrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            workspace.mkdir()
            roleplay = workspace / "branches" / "scene_0001" / "roleplay_result.json"
            roleplay.parent.mkdir(parents=True)
            roleplay.write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/roleplay-result/v1",
                        "scene_id": "scene_0001",
                        "status": "complete",
                        "source_artifact": "branches/scene_0001/roleplay_simulation.md",
                        "evidence_paths": ["scenes/scene_0001.yaml"],
                        "character_actions": [{"action": "test"}],
                        "world_consequences": [{"impact": "test"}],
                        "branch_pressures": [{"pressure": "test"}],
                        "canon_risks": [],
                        "writeback_candidates": {"kind": "state", "value": "kept exactly"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            task = TaskPackage(
                project_root=root,
                task_json_path=root / "task.json",
                task_markdown_path=root / "task.md",
                payload={
                    "task_id": "scene-development-scene-0001-roleplay-agent-task",
                    "route": "scene-development",
                    "current_state": "roleplay-agent-task",
                    "scene_id": "scene_0001",
                    "expected_outputs": ["branches/scene_0001/roleplay_result.json"],
                },
            )
            sandbox = SandboxManifest(
                run_id="test",
                run_root=root,
                workspace=workspace,
                prompt_path=root / "prompt.md",
                manifest_path=root / "manifest.json",
                baseline_path=root / "baseline.json",
                expected_outputs=task.expected_outputs,
            )

            changes = canonicalize_task_outputs(task, sandbox)

            normalized = json.loads(roleplay.read_text(encoding="utf-8"))
            self.assertEqual(normalized["writeback_candidates"], [{"kind": "state", "value": "kept exactly"}])
            self.assertTrue(any(item["field"] == "writeback_candidates" for item in changes))

    def test_semantic_contract_failure_reaches_worker_preflight_repair_loop(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            workspace.mkdir()
            roleplay = workspace / "branches" / "scene_0001" / "roleplay_result.json"
            roleplay.parent.mkdir(parents=True)
            roleplay.write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/roleplay-result/v1",
                        "scene_id": "scene_0001",
                        "status": "pending_agent_judgment",
                        "source_artifact": "branches/scene_0001/roleplay_simulation.md",
                        "evidence_paths": ["scenes/scene_0001.yaml"],
                        "character_actions": [],
                        "world_consequences": [],
                        "branch_pressures": [],
                        "canon_risks": [],
                        "writeback_candidates": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            task = TaskPackage(
                project_root=root,
                task_json_path=root / "task.json",
                task_markdown_path=root / "task.md",
                payload={
                    "task_id": "scene-development-scene-0001-roleplay-agent-task",
                    "route": "scene-development",
                    "current_state": "roleplay-agent-task",
                    "scene_id": "scene_0001",
                    "expected_outputs": ["branches/scene_0001/roleplay_result.json"],
                },
            )
            sandbox = SandboxManifest(
                run_id="test",
                run_root=root,
                workspace=workspace,
                prompt_path=root / "prompt.md",
                manifest_path=root / "manifest.json",
                baseline_path=root / "baseline.json",
                expected_outputs=task.expected_outputs,
            )
            sandbox.baseline_path.write_text("{}", encoding="utf-8")

            result = validate_task_outputs(task, sandbox)

            self.assertFalse(result.passed)
            self.assertTrue(any(issue.code == "semantic-contract" for issue in result.issues))
            self.assertIn("pending", result.repair_prompt(1, 2))

    def test_composition_semantic_review_normalizes_lifecycle_vocabulary_without_changing_judgment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            composition = workspace / "drafts" / "compositions" / "scene_0001_composition.json"
            composition.parent.mkdir(parents=True)
            composition.write_text('{"scene_id":"scene_0001"}', encoding="utf-8")
            review = workspace / "drafts" / "compositions" / "scene_0001_composition_review.json"
            review.write_text(
                json.dumps(
                    {
                        "schema": "wrong",
                        "scene_id": "wrong-scene",
                        "status": "pass",
                        "source_artifact": "wrong.json",
                        "composition_sha256": "wrong",
                        "evidence_paths": ["drafts/compositions/scene_0001_composition.json"],
                        "findings": ["composition is coherent"],
                        "verdict": "complete",
                        "required_changes": [],
                        "ready_for_generation": True,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            task = TaskPackage(
                project_root=root,
                task_json_path=root / "task.json",
                task_markdown_path=root / "task.md",
                payload={
                    "task_id": "scene-development-scene-0001-composition-agent-task",
                    "route": "scene-development",
                    "current_state": "composition-agent-task",
                    "scene_id": "scene_0001",
                    "expected_outputs": ["drafts/compositions/scene_0001_composition_review.json"],
                },
            )
            sandbox = SandboxManifest(
                run_id="test",
                run_root=root,
                workspace=workspace,
                prompt_path=root / "prompt.md",
                manifest_path=root / "manifest.json",
                baseline_path=root / "baseline.json",
                expected_outputs=task.expected_outputs,
            )

            canonicalize_task_outputs(task, sandbox)

            normalized = json.loads(review.read_text(encoding="utf-8"))
            self.assertEqual(normalized["schema"], "literary-engineering-workbench/composition-review/v1")
            self.assertEqual(normalized["scene_id"], "scene_0001")
            self.assertEqual(normalized["status"], "complete")
            self.assertEqual(normalized["verdict"], "pass")

    def test_asset_review_bare_field_action_is_bound_to_the_current_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            candidate_rel = "characters/candidates/archivist.json"
            review_rel = "reviews/assets/archivist_review.json"
            review = workspace / review_rel
            review.parent.mkdir(parents=True)
            review.write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/candidate-asset-review/v0.1",
                        "candidate": candidate_rel,
                        "candidate_id": "archivist",
                        "asset_type": "character",
                        "status": "revise_required",
                        "blocking_issues": [],
                        "warnings": [],
                        "revision_actions": [{"id": "RA01", "target": "psychology.secret", "description": "Use a list."}],
                        "promotion_risks": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            task = TaskPackage(
                project_root=root,
                task_json_path=root / "task.json",
                task_markdown_path=root / "task.md",
                payload={
                    "task_id": "character-and-world-assets-archivist-asset-review-agent-task",
                    "route": "character-and-world-assets",
                    "task_type": "platform-agent-asset-review",
                    "current_state": "asset-review-agent-task",
                    "candidate": candidate_rel,
                    "candidate_id": "archivist",
                    "asset_type": "character",
                    "expected_outputs": [review_rel],
                },
            )
            sandbox = SandboxManifest(
                run_id="test",
                run_root=root,
                workspace=workspace,
                prompt_path=root / "prompt.md",
                manifest_path=root / "manifest.json",
                baseline_path=root / "baseline.json",
                expected_outputs=task.expected_outputs,
            )

            canonicalize_task_outputs(task, sandbox)

            normalized = json.loads(review.read_text(encoding="utf-8"))
            self.assertEqual(normalized["revision_actions"][0]["target"], candidate_rel + "#psychology.secret")

    def test_branch_completion_marker_is_worker_owned_after_selection_exists(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            selection = workspace / "branches" / "scene_0001" / "branch_selection.md"
            selection.parent.mkdir(parents=True)
            selection.write_text("decision: selected\nselected_branch: A\n", encoding="utf-8")
            task = TaskPackage(
                project_root=root,
                task_json_path=root / "task.json",
                task_markdown_path=root / "task.md",
                payload={
                    "task_id": "scene-development-scene-0001-branch-agent-task",
                    "route": "scene-development",
                    "current_state": "branch-agent-task",
                    "scene_id": "scene_0001",
                    "expected_outputs": [
                        "branches/scene_0001/branch_selection.md",
                        "branches/scene_0001/branch_manifest.agent_completion.json",
                    ],
                },
            )
            sandbox = SandboxManifest(
                run_id="test",
                run_root=root,
                workspace=workspace,
                prompt_path=root / "prompt.md",
                manifest_path=root / "manifest.json",
                baseline_path=root / "baseline.json",
                expected_outputs=task.expected_outputs,
            )

            canonicalize_task_outputs(task, sandbox)

            marker = json.loads(
                (workspace / "branches" / "scene_0001" / "branch_manifest.agent_completion.json").read_text(encoding="utf-8")
            )
            self.assertEqual(marker["status"], "complete")
            self.assertEqual(marker["handled_by"], "studio-worker")
    def test_rejects_format_shortcuts_then_accepts_exact_review_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            task_dir = project / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            (project / "project.yaml").write_text("title: fixture\n", encoding="utf-8")
            task_markdown = task_dir / "review.agent_tasks.md"
            task_markdown.write_text("# Review task\n", encoding="utf-8")
            task_json = task_dir / "review.json"
            task_json.write_text(
                json.dumps(
                    {
                        "schema": TASK_SCHEMA,
                        "task_id": "review",
                        "route": "review-and-audit",
                        "current_state": "agent-review",
                        "task_type": "platform-agent-review",
                        "task_markdown": "workflow/tasks/review.agent_tasks.md",
                        "required_reading": [],
                        "source_paths": [],
                        "expected_outputs": [
                            "reviews/scene.agent_review.md",
                            "workflow/tasks/review.agent_tasks.agent_completion.json",
                        ],
                        "validation_gates": ["review conclusion is pass"],
                        "forbidden_shortcuts": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            task = load_task_package(project, task_json)
            sandbox = stage_task(task, root / "runs", runtime="opencode")
            review = sandbox.workspace / "reviews" / "scene.agent_review.md"
            completion = sandbox.workspace / "workflow" / "tasks" / "review.agent_tasks.agent_completion.json"
            review.parent.mkdir(parents=True, exist_ok=True)
            completion.parent.mkdir(parents=True, exist_ok=True)
            review.write_text("## 结论： pass\n", encoding="utf-8")
            completion.write_text(
                json.dumps(
                    {
                        "schema": COMPLETION_SCHEMA,
                        "status": "complete",
                        "expected_artifacts_checked": False,
                        "source_task": "wrong.md",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            failed = validate_task_outputs(task, sandbox)
            self.assertFalse(failed.passed)
            self.assertEqual(
                {item.code for item in failed.issues},
                {"invalid-completion-evidence", "missing-machine-conclusion"},
            )
            self.assertIn("只修复下列明确问题", failed.repair_prompt(1, 2))

            changes = canonicalize_task_outputs(task, sandbox)
            self.assertIn({"path": "reviews/scene.agent_review.md", "verdict": "pass"}, changes)
            self.assertTrue(any(item.get("field") == "completion" for item in changes))
            self.assertTrue(validate_task_outputs(task, sandbox).passed)

            review.write_text("# 审查报告\n\n- 结论： pass\n", encoding="utf-8")
            completion.write_text(
                json.dumps(
                    {
                        "schema": COMPLETION_SCHEMA,
                        "status": "complete",
                        "expected_artifacts_checked": True,
                        "source_task": "workflow/tasks/review.agent_tasks.md",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            passed = validate_task_outputs(task, sandbox)
            self.assertTrue(passed.passed, passed.as_dict())

    def test_completion_receipt_is_refreshed_after_its_sidecar_is_reissued(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            review_dir = workspace / "reviews" / "agent"
            review_dir.mkdir(parents=True)
            sidecar = review_dir / "scene_0001_scene_review.agent_tasks.md"
            sidecar.write_text("# Fresh review task\n", encoding="utf-8")
            report = review_dir / "scene_0001_scene_review.md"
            report.write_text("# Review\n", encoding="utf-8")
            review_json = review_dir / "scene_0001_scene_review.json"
            review_json.write_text("{}\n", encoding="utf-8")
            marker = review_dir / "scene_0001_scene_review.agent_completion.json"
            marker.write_text(
                json.dumps(
                    {
                        "schema": COMPLETION_SCHEMA,
                        "source_task": "reviews/agent/scene_0001_scene_review.agent_tasks.md",
                        "status": "complete",
                        "handled_by": "studio-worker",
                        "expected_artifacts_checked": True,
                        "notes": ["Machine-owned completion receipt; route gates validate the Agent-authored result separately."],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            stale_time = 1_700_000_000
            os.utime(marker, (stale_time, stale_time))
            os.utime(sidecar, (stale_time + 10, stale_time + 10))
            task = TaskPackage(
                project_root=root,
                task_json_path=root / "task.json",
                task_markdown_path=root / "task.md",
                payload={
                    "task_id": "scene-development-scene-0001-candidate-review",
                    "route": "scene-development",
                    "current_state": "candidate-review",
                    "task_type": "platform-agent-review",
                    "expected_outputs": [
                        "reviews/agent/scene_0001_scene_review.json",
                        "reviews/agent/scene_0001_scene_review.md",
                        "reviews/agent/scene_0001_scene_review.agent_tasks.md",
                        "reviews/agent/scene_0001_scene_review.agent_completion.json",
                    ],
                },
            )
            sandbox = SandboxManifest(
                run_id="test",
                run_root=root,
                workspace=workspace,
                prompt_path=root / "prompt.md",
                manifest_path=root / "manifest.json",
                baseline_path=root / "baseline.json",
                expected_outputs=task.expected_outputs,
            )

            changes = canonicalize_task_outputs(task, sandbox)

            self.assertTrue(any(item.get("field") == "completion" for item in changes))
            self.assertGreaterEqual(marker.stat().st_mtime_ns, sidecar.stat().st_mtime_ns)

    def test_scene_review_contract_is_checked_before_writeback_and_task_metadata_is_normalized(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            task_dir = project / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            candidate = project / "drafts" / "candidates" / "scene_0001-platform-agent.md"
            candidate.parent.mkdir(parents=True)
            candidate.write_text("## 正文候选\n\n她推开了门。\n", encoding="utf-8")
            (project / "project.yaml").write_text("title: fixture\n", encoding="utf-8")
            task_markdown = task_dir / "candidate-review.agent_tasks.md"
            task_markdown.write_text("# Candidate review\n", encoding="utf-8")
            task_json = task_dir / "candidate-review.json"
            task_json.write_text(
                json.dumps(
                    {
                        "schema": TASK_SCHEMA,
                        "task_id": "scene-development-scene_0001-candidate-review",
                        "route": "scene-development",
                        "scene_id": "scene_0001",
                        "current_state": "candidate-review",
                        "task_type": "platform-agent-review",
                        "candidate": "drafts/candidates/scene_0001-platform-agent.md",
                        "task_markdown": "workflow/tasks/candidate-review.agent_tasks.md",
                        "required_reading": [],
                        "source_paths": ["drafts/candidates/scene_0001-platform-agent.md"],
                        "expected_outputs": ["reviews/agent/scene_0001_scene_review.json"],
                        "validation_gates": ["scene_review.v1 JSON exists"],
                        "forbidden_shortcuts": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            task = load_task_package(project, task_json)
            sandbox = stage_task(task, root / "runs", runtime="opencode")
            self.assertEqual(
                (sandbox.workspace / "project.yaml").read_text(encoding="utf-8"),
                "title: fixture\n",
            )
            review = sandbox.workspace / "reviews" / "agent" / "scene_0001_scene_review.json"
            review.parent.mkdir(parents=True, exist_ok=True)
            review.write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/scene-review/v1",
                        "scene_id": "wrong-scene",
                        "candidate_sha256": "example",
                        "conclusion": "pass_with_notes",
                        "summary": "Review evidence exists, but the contract is incomplete.",
                    }
                ),
                encoding="utf-8",
            )

            failed = validate_task_outputs(task, sandbox)
            codes = {item.code for item in failed.issues}
            self.assertIn("scene-review-schema-invalid", codes)
            self.assertIn("scene-review-candidate-digest-mismatch", codes)
            self.assertIn("scene-review-candidate-source-missing", codes)

            changes = canonicalize_task_outputs(task, sandbox)
            self.assertTrue(changes)
            normalized = json.loads(review.read_text(encoding="utf-8"))
            self.assertEqual(normalized["schema"], "literary-engineering-workbench/scene-review-agent/v1")
            self.assertEqual(normalized["scene_id"], "scene_0001")
            self.assertIn("drafts/candidates/scene_0001-platform-agent.md", normalized["source_paths"])
            remaining = validate_task_outputs(task, sandbox)
            self.assertTrue(any(item.code == "scene-review-schema-invalid" for item in remaining.issues))
            self.assertFalse(any(item.code == "scene-review-candidate-digest-mismatch" for item in remaining.issues))
            self.assertIn("必须逐一读取", (sandbox.workspace / "AGENT_TASK.md").read_text(encoding="utf-8"))

    def test_asset_schema_is_rejected_before_writeback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            task_dir = project / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            (project / "project.yaml").write_text("title: fixture\n", encoding="utf-8")
            task_markdown = task_dir / "asset.agent_tasks.md"
            task_markdown.write_text("# Asset task\n", encoding="utf-8")
            task_json = task_dir / "asset.json"
            task_json.write_text(
                json.dumps(
                    {
                        "schema": TASK_SCHEMA,
                        "task_id": "asset",
                        "route": "character-and-world-assets",
                        "current_state": "asset-creation-agent-task",
                        "task_type": "platform-agent-asset-creation",
                        "asset_type": "character",
                        "candidate": "characters/candidates/protagonist.json",
                        "task_markdown": "workflow/tasks/asset.agent_tasks.md",
                        "required_reading": [],
                        "source_paths": [],
                        "expected_outputs": ["characters/candidates/protagonist.json"],
                        "validation_gates": ["candidate schema validates"],
                        "forbidden_shortcuts": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            task = load_task_package(project, task_json)
            sandbox = stage_task(task, root / "runs", runtime="opencode")
            candidate = sandbox.workspace / "characters" / "candidates" / "protagonist.json"
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_text(
                json.dumps(
                    {
                        "schema": "character_profile.v1",
                        "candidate_id": "protagonist",
                        "asset_type": "character",
                        "risks": [],
                        "source_paths": [],
                        "promotion_notes": {"action": "review"},
                        "characters": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = validate_task_outputs(task, sandbox)

            self.assertFalse(result.passed)
            self.assertIn("asset-schema-invalid", {item.code for item in result.issues})
            self.assertIn("asset-metadata-invalid", {item.code for item in result.issues})
            self.assertIn("character_id", result.repair_prompt(1, 2))

    def test_asset_machine_metadata_is_normalized_from_the_task_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            task_dir = project / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            (project / "project.yaml").write_text("title: fixture\n", encoding="utf-8")
            (task_dir / "asset.agent_tasks.md").write_text("# Asset task\n", encoding="utf-8")
            task_json = task_dir / "asset.json"
            task_json.write_text(
                json.dumps(
                    {
                        "schema": TASK_SCHEMA,
                        "task_id": "asset-create",
                        "route": "character-and-world-assets",
                        "current_state": "asset-creation-agent-task",
                        "task_type": "platform-agent-asset-creation",
                        "asset_type": "character",
                        "candidate_id": "protagonist-foundation",
                        "candidate": "characters/candidates/protagonist-foundation.json",
                        "task_markdown": "workflow/tasks/asset.agent_tasks.md",
                        "required_reading": [],
                        "source_paths": ["project.yaml"],
                        "expected_outputs": [
                            "characters/candidates/protagonist-foundation.json",
                            "characters/candidates/protagonist-foundation.md",
                            "characters/candidates/protagonist-foundation.agent_completion.json",
                        ],
                        "system_owned_fields": {
                            "candidate": {
                                "path": "characters/candidates/protagonist-foundation.json",
                                "candidate_id": "protagonist-foundation",
                                "asset_type": "character",
                                "schema": "literary-engineering-workbench/character-profile-candidate/v1",
                                "source_paths": ["project.yaml"],
                            },
                            "completion": {
                                "schema": COMPLETION_SCHEMA,
                                "status": "complete",
                                "expected_artifacts_checked": True,
                            },
                        },
                        "validation_gates": ["candidate schema validates"],
                        "forbidden_shortcuts": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            task = load_task_package(project, task_json)
            sandbox = stage_task(task, root / "runs", runtime="opencode")
            candidate = sandbox.workspace / "characters" / "candidates" / "protagonist-foundation.json"
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_text(
                json.dumps(
                    {
                        "schema": "wrong",
                        "candidate_id": "protagonist-foundation-v1",
                        "asset_type": "character_profile",
                        "source_paths": ["invented.md"],
                        "risks": [],
                        "promotion_notes": "ready",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            candidate.with_suffix(".md").write_text("# Candidate\n", encoding="utf-8")

            changes = canonicalize_task_outputs(task, sandbox)
            normalized = json.loads(candidate.read_text(encoding="utf-8"))
            completion = json.loads(candidate.with_suffix(".agent_completion.json").read_text(encoding="utf-8"))

            self.assertTrue(changes)
            self.assertEqual(normalized["schema"], "literary-engineering-workbench/character-profile-candidate/v1")
            self.assertEqual(normalized["candidate_id"], "protagonist-foundation")
            self.assertEqual(normalized["asset_type"], "character")
            self.assertEqual(normalized["source_paths"], ["project.yaml"])
            self.assertEqual(completion["source_task"], "characters/candidates/protagonist-foundation.agent_tasks.md")
            self.assertEqual(completion["status"], "complete")

    def test_asset_review_identity_is_not_left_to_the_agent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            task_dir = project / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            (project / "project.yaml").write_text("title: fixture\n", encoding="utf-8")
            candidate_source = project / "characters" / "candidates" / "protagonist-foundation.json"
            candidate_source.parent.mkdir(parents=True)
            candidate_source.write_text("{}\n", encoding="utf-8")
            (task_dir / "review.agent_tasks.md").write_text("# Review task\n", encoding="utf-8")
            task_json = task_dir / "review.json"
            task_json.write_text(
                json.dumps(
                    {
                        "schema": TASK_SCHEMA,
                        "task_id": "asset-review",
                        "route": "character-and-world-assets",
                        "current_state": "asset-review-agent-task",
                        "task_type": "platform-agent-asset-review",
                        "asset_type": "character",
                        "candidate_id": "protagonist-foundation",
                        "candidate": "characters/candidates/protagonist-foundation.json",
                        "task_markdown": "workflow/tasks/review.agent_tasks.md",
                        "required_reading": [],
                        "source_paths": ["characters/candidates/protagonist-foundation.json"],
                        "expected_outputs": [
                            "reviews/assets/protagonist-foundation_review.md",
                            "reviews/assets/protagonist-foundation_review.json",
                            "reviews/assets/protagonist-foundation_review.agent_completion.json",
                        ],
                        "system_owned_fields": {
                            "review": {
                                "path": "reviews/assets/protagonist-foundation_review.json",
                                "schema": "literary-engineering-workbench/candidate-asset-review/v0.1",
                                "candidate": "characters/candidates/protagonist-foundation.json",
                                "candidate_id": "protagonist-foundation",
                                "asset_type": "character",
                            },
                            "completion": {
                                "schema": COMPLETION_SCHEMA,
                                "status": "complete",
                                "expected_artifacts_checked": True,
                            },
                        },
                        "validation_gates": ["review JSON exists"],
                        "forbidden_shortcuts": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            task = load_task_package(project, task_json)
            sandbox = stage_task(task, root / "runs", runtime="opencode")
            review = sandbox.workspace / "reviews" / "assets" / "protagonist-foundation_review.json"
            review.parent.mkdir(parents=True, exist_ok=True)
            review.with_suffix(".md").write_text("# Review\n", encoding="utf-8")
            review.write_text(
                json.dumps(
                    {
                        "schema": "wrong",
                        "candidate": "characters/candidates/protagonist-foundation-v1.json",
                        "candidate_id": "protagonist-foundation-v1",
                        "asset_type": "character_profile",
                        "status": "pass",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            canonicalize_task_outputs(task, sandbox)
            normalized = json.loads(review.read_text(encoding="utf-8"))
            completion = json.loads(review.with_suffix(".agent_completion.json").read_text(encoding="utf-8"))

            self.assertEqual(normalized["schema"], "literary-engineering-workbench/candidate-asset-review/v0.1")
            self.assertEqual(normalized["candidate"], "characters/candidates/protagonist-foundation.json")
            self.assertEqual(normalized["candidate_id"], "protagonist-foundation")
            self.assertEqual(normalized["asset_type"], "character")
            self.assertTrue(completion["expected_artifacts_checked"])

    def test_candidate_provenance_gate_reaches_runner_repair_loop(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            task_dir = project / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            (project / "project.yaml").write_text("title: fixture\n", encoding="utf-8")
            task_markdown = task_dir / "candidate.agent_tasks.md"
            task_markdown.write_text("# Candidate task\n", encoding="utf-8")
            task_json = task_dir / "candidate.json"
            outputs = [
                "drafts/candidates/scene_0001-platform-agent.md",
                "drafts/candidates/scene_0001-platform-agent.json",
                "drafts/candidates/scene_0001-platform-agent.prompt.json",
                "drafts/candidates/scene_0001-platform-agent.agent_tasks.md",
                "drafts/candidates/scene_0001-platform-agent.agent_completion.json",
            ]
            task_json.write_text(
                json.dumps(
                    {
                        "schema": TASK_SCHEMA,
                        "task_id": "candidate",
                        "route": "scene-development",
                        "scene_id": "scene_0001",
                        "current_state": "candidate-generation-provenance",
                        "task_type": "main-platform-agent-prose",
                        "task_markdown": "workflow/tasks/candidate.agent_tasks.md",
                        "required_reading": [],
                        "source_paths": [],
                        "expected_outputs": outputs,
                        "validation_gates": [],
                        "forbidden_shortcuts": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            task = load_task_package(project, task_json)
            sandbox = stage_task(task, root / "runs", runtime="opencode")
            for relative in outputs:
                path = sandbox.workspace / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                if relative.endswith(".json"):
                    path.write_text("{}", encoding="utf-8")
                else:
                    path.write_text("正文。", encoding="utf-8")
            completion = sandbox.workspace / outputs[-1]
            completion.write_text(
                json.dumps(
                    {
                        "schema": COMPLETION_SCHEMA,
                        "status": "complete",
                        "expected_artifacts_checked": True,
                        "source_task": "drafts/candidates/scene_0001-platform-agent.agent_tasks.md",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with patch(
                "literary_engineering_studio_engine.candidate_promotion.candidate_generation_gate",
                return_value={"status": "invalid", "message": "provenance invalid", "invalid": ["new_character_register.blocking_issues is not empty"]},
            ):
                result = validate_task_outputs(task, sandbox)

            self.assertFalse(result.passed)
            self.assertIn("candidate-provenance-invalid", {item.code for item in result.issues})
            self.assertIn("new_character_register", result.repair_prompt(1, 2))

    def test_candidate_register_is_normalized_from_declared_scene_character_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            task_dir = project / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            (project / "project.yaml").write_text("title: fixture\n", encoding="utf-8")
            markdown = task_dir / "candidate.agent_tasks.md"
            markdown.write_text("# Candidate task\n", encoding="utf-8")
            payload = {
                "schema": TASK_SCHEMA,
                "task_id": "candidate",
                "route": "scene-development",
                "scene_id": "scene_0001",
                "current_state": "candidate-generation-provenance",
                "task_type": "main-platform-agent-prose",
                "task_markdown": "workflow/tasks/candidate.agent_tasks.md",
                "required_reading": [],
                "source_paths": [],
                "expected_outputs": ["drafts/candidates/scene_0001-platform-agent.md"],
                "scene_character_assets": [{
                    "name": "林正",
                    "candidate_id": "scene-0001-林正",
                    "candidate_path": "characters/candidates/scene-0001-林正.json",
                    "formal_character_path": "characters/scene-0001-林正.yaml",
                }],
                "validation_gates": [],
                "forbidden_shortcuts": [],
            }
            task_json = task_dir / "candidate.task.json"
            task_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            task = load_task_package(project, task_json)
            sandbox = stage_task(task, root / "runs", runtime="opencode")
            candidate = sandbox.workspace / "drafts" / "candidates" / "scene_0001-platform-agent.json"
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_text(json.dumps({"new_character_register": []}, ensure_ascii=False), encoding="utf-8")
            character = sandbox.workspace / "characters" / "candidates" / "scene-0001-林正.json"
            character.parent.mkdir(parents=True, exist_ok=True)
            character.write_text("{}\n", encoding="utf-8")

            changes = canonicalize_task_outputs(task, sandbox)
            normalized = json.loads(candidate.read_text(encoding="utf-8"))

            self.assertTrue(changes)
            self.assertEqual(normalized["new_character_register"]["status"], "candidates_ready")
            self.assertEqual(normalized["new_character_register"]["introduced"][0]["candidate_path"], "characters/candidates/scene-0001-林正.json")

    def test_longform_sessions_and_completion_receipt_are_worker_owned(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            candidate = workspace / "plot" / "story_architecture.candidate.json"
            candidate.parent.mkdir(parents=True)
            candidate.write_text(
                json.dumps(
                    {
                        "schema": "wrong",
                        "status": "done",
                        "writer_session_id": "guessed-by-agent",
                        "premise": "A premise",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            task = TaskPackage(
                project_root=root,
                task_json_path=root / "task.json",
                task_markdown_path=root / "task.md",
                payload={
                    "task_id": "longform-longform-story-architecture-agent-task",
                    "route": "longform-planning",
                    "current_state": "story-architecture-agent-task",
                    "task_type": "platform-agent-judgment",
                    "execution_policy": "agent-required",
                    "expected_outputs": [
                        "plot/story_architecture.candidate.json",
                        "plot/story_architecture.agent_completion.json",
                    ],
                    "system_owned_fields": {
                        "lifecycle": {
                            "completion_receipts": [{
                                "path": "plot/story_architecture.agent_completion.json",
                                "schema": COMPLETION_SCHEMA,
                                "source_task": "plot/story_architecture.agent_tasks.md",
                                "status": "complete",
                                "expected_artifacts_checked": True,
                            }],
                        },
                    },
                },
            )
            sandbox = SandboxManifest(
                run_id="test",
                run_root=root,
                workspace=workspace,
                prompt_path=root / "prompt.md",
                manifest_path=root / "manifest.json",
                baseline_path=root / "baseline.json",
                expected_outputs=task.expected_outputs,
            )

            canonicalize_task_outputs(task, sandbox)

            normalized = json.loads(candidate.read_text(encoding="utf-8"))
            receipt = json.loads((workspace / "plot" / "story_architecture.agent_completion.json").read_text(encoding="utf-8"))
            self.assertEqual(normalized["schema"], "literary-engineering-workbench/story-architecture/v1")
            self.assertEqual(normalized["status"], "complete")
            self.assertEqual(normalized["writer_session_id"], "studio:writer:longform-longform-story-architecture-agent-task")
            self.assertEqual(receipt["source_task"], "plot/story_architecture.agent_tasks.md")
            self.assertEqual(receipt["status"], "complete")

    def test_continuity_delta_normalizes_agent_status_alias_without_rewriting_judgment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            scene_id = "scene_0001"
            draft = workspace / "drafts" / "scenes" / f"{scene_id}.md"
            draft.parent.mkdir(parents=True)
            draft.write_text("已晋升正文。", encoding="utf-8")
            delta = workspace / "plot" / "ledger_deltas" / f"{scene_id}.json"
            delta.parent.mkdir(parents=True)
            delta.write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/continuity-ledger-delta/v1",
                        "status": "agent_judged",
                        "writer_session_id": "writer-provided-by-agent",
                        "reader_question_changes": [{"id": "question-1", "change": "opened"}],
                        "promise_changes": [],
                        "evidence_paths": [f"drafts/scenes/{scene_id}.md"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            task = TaskPackage(
                project_root=root,
                task_json_path=root / "task.json",
                task_markdown_path=root / "task.md",
                payload={
                    "task_id": "scene-development-scene-0001-continuity-ledger-agent-task",
                    "route": "scene-development",
                    "scene_id": scene_id,
                    "current_state": "continuity-ledger-agent-task",
                    "expected_outputs": [f"plot/ledger_deltas/{scene_id}.json"],
                },
            )
            sandbox = SandboxManifest(
                run_id="test",
                run_root=root,
                workspace=workspace,
                prompt_path=root / "prompt.md",
                manifest_path=root / "manifest.json",
                baseline_path=root / "baseline.json",
                expected_outputs=task.expected_outputs,
            )

            canonicalize_task_outputs(task, sandbox)

            normalized = json.loads(delta.read_text(encoding="utf-8"))
            self.assertEqual(normalized["status"], "complete")
            self.assertEqual(normalized["writer_session_id"], "studio:writer:scene-development-scene-0001-continuity-ledger-agent-task")
            self.assertEqual(normalized["reader_question_changes"], [{"id": "question-1", "change": "opened"}])

    def test_agent_completion_receipt_is_created_when_absent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            output = workspace / "plot" / "ledger_deltas" / "scene_0001.json"
            output.parent.mkdir(parents=True)
            output.write_text('{"ready": true}\n', encoding="utf-8")
            task = TaskPackage(
                project_root=root,
                task_json_path=root / "task.json",
                task_markdown_path=root / "task.md",
                payload={
                    "task_id": "scene-development-scene-0001-continuity-ledger-agent-task",
                    "route": "scene-development",
                    "scene_id": "scene_0001",
                    "current_state": "continuity-ledger-agent-task",
                    "task_type": "platform-agent-judgment",
                    "execution_policy": "agent-required",
                    "expected_outputs": [
                        "plot/ledger_deltas/scene_0001.json",
                        "plot/ledger_deltas/scene_0001.agent_completion.json",
                    ],
                },
            )
            sandbox = SandboxManifest(
                run_id="test",
                run_root=root,
                workspace=workspace,
                prompt_path=root / "prompt.md",
                manifest_path=root / "manifest.json",
                baseline_path=root / "baseline.json",
                expected_outputs=task.expected_outputs,
            )

            canonicalize_task_outputs(task, sandbox)

            receipt = json.loads((workspace / "plot" / "ledger_deltas" / "scene_0001.agent_completion.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["status"], "complete")
            self.assertEqual(receipt["handled_by"], "studio-worker")

    def test_continuity_review_binds_digest_and_reviewer_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            scene_id = "scene_0001"
            delta = workspace / "plot" / "ledger_deltas" / f"{scene_id}.json"
            delta.parent.mkdir(parents=True)
            delta.write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/continuity-ledger-delta/v1",
                        "status": "complete",
                        "writer_session_id": "studio:writer:original",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            review = workspace / "reviews" / "continuity" / f"{scene_id}_ledger_review.json"
            review.parent.mkdir(parents=True)
            review.write_text(
                json.dumps(
                    {
                        "schema": "wrong",
                        "scene_id": "wrong",
                        "delta_path": "wrong.json",
                        "delta_sha256": "wrong",
                        "writer_session_id": "wrong",
                        "reviewer_session_id": "wrong",
                        "status": "completed",
                        "verdict": "pass",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            task = TaskPackage(
                project_root=root,
                task_json_path=root / "task.json",
                task_markdown_path=root / "task.md",
                payload={
                    "task_id": "scene-development-scene-0001-continuity-ledger-review",
                    "route": "scene-development",
                    "scene_id": scene_id,
                    "current_state": "continuity-ledger-review",
                    "task_type": "platform-agent-review",
                    "execution_policy": "agent-required",
                    "expected_outputs": [
                        f"reviews/continuity/{scene_id}_ledger_review.json",
                        f"reviews/continuity/{scene_id}_ledger_review.agent_completion.json",
                    ],
                    "system_owned_fields": {
                        "lifecycle": {
                            "completion_receipts": [{
                                "path": f"reviews/continuity/{scene_id}_ledger_review.agent_completion.json",
                                "schema": COMPLETION_SCHEMA,
                                "source_task": f"reviews/continuity/{scene_id}_ledger_review.agent_tasks.md",
                                "status": "complete",
                                "expected_artifacts_checked": True,
                            }],
                        },
                    },
                },
            )
            sandbox = SandboxManifest(
                run_id="test",
                run_root=root,
                workspace=workspace,
                prompt_path=root / "prompt.md",
                manifest_path=root / "manifest.json",
                baseline_path=root / "baseline.json",
                expected_outputs=task.expected_outputs,
            )

            canonicalize_task_outputs(task, sandbox)

            normalized = json.loads(review.read_text(encoding="utf-8"))
            self.assertEqual(normalized["schema"], "literary-engineering-workbench/continuity-ledger-review/v1")
            self.assertEqual(normalized["scene_id"], scene_id)
            self.assertEqual(normalized["delta_path"], f"plot/ledger_deltas/{scene_id}.json")
            self.assertEqual(normalized["writer_session_id"], "studio:writer:original")
            self.assertEqual(normalized["reviewer_session_id"], "studio:reviewer:scene-development-scene-0001-continuity-ledger-review")
            self.assertEqual(normalized["status"], "complete")

    def test_branch_selection_contract_reaches_worker_preflight_repair_loop(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            selection = workspace / "branches" / "scene_0001" / "branch_selection.md"
            selection.parent.mkdir(parents=True)
            selection.write_text("# Decision\n\n**Selected**: `branch_a`\n", encoding="utf-8")
            (selection.parent / "branch_manifest.json").write_text(
                json.dumps({"branches": [{"branch_id": "branch_a"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            task = TaskPackage(
                project_root=root,
                task_json_path=root / "task.json",
                task_markdown_path=root / "task.md",
                payload={
                    "task_id": "scene-development-scene-0001-branch-selection",
                    "route": "scene-development",
                    "current_state": "branch-selection",
                    "scene_id": "scene_0001",
                    "expected_outputs": ["branches/scene_0001/branch_selection.md"],
                },
            )
            sandbox = SandboxManifest(
                run_id="test",
                run_root=root,
                workspace=workspace,
                prompt_path=root / "prompt.md",
                manifest_path=root / "manifest.json",
                baseline_path=root / "baseline.json",
                expected_outputs=task.expected_outputs,
            )
            sandbox.baseline_path.write_text("{}", encoding="utf-8")

            result = validate_task_outputs(task, sandbox)

            self.assertFalse(result.passed)
            self.assertIn("branch-selection-contract", {item.code for item in result.issues})
            self.assertIn("selected_branch", result.repair_prompt(1, 2))

    def test_branch_selection_contract_accepts_exact_manifest_branch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            selection = workspace / "branches" / "scene_0001" / "branch_selection.md"
            selection.parent.mkdir(parents=True)
            selection.write_text(
                "decision: selected\nselected_branch: branch_a\n\n# Rationale\n\nCausality first.\n",
                encoding="utf-8",
            )
            (selection.parent / "branch_manifest.json").write_text(
                json.dumps({"branches": [{"branch_id": "branch_a"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            task = TaskPackage(
                project_root=root,
                task_json_path=root / "task.json",
                task_markdown_path=root / "task.md",
                payload={
                    "task_id": "scene-development-scene-0001-branch-selection",
                    "route": "scene-development",
                    "current_state": "branch-selection",
                    "scene_id": "scene_0001",
                    "expected_outputs": ["branches/scene_0001/branch_selection.md"],
                },
            )
            sandbox = SandboxManifest(
                run_id="test",
                run_root=root,
                workspace=workspace,
                prompt_path=root / "prompt.md",
                manifest_path=root / "manifest.json",
                baseline_path=root / "baseline.json",
                expected_outputs=task.expected_outputs,
            )
            sandbox.baseline_path.write_text("{}", encoding="utf-8")

            result = validate_task_outputs(task, sandbox)

            self.assertNotIn("branch-selection-contract", {item.code for item in result.issues})
            self.assertNotIn("branch-selection-membership", {item.code for item in result.issues})


if __name__ == "__main__":
    unittest.main()
