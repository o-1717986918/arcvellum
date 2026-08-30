from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.runtime.context_budget import resolve_task_context_budget
from literary_engineering_studio.runtime.context_materialization import _legacy_user_direction
from literary_engineering_studio.runtime.context_selection import select_agent_context
from literary_engineering_studio.runtime.execution_context import (
    build_execution_context_envelope,
)
from literary_engineering_studio.runtime.prompt_context import build_prepared_prompt_context
from literary_engineering_studio.runtime.prompt_program import (
    OnDemandEvidence,
    PromptProgram,
    resolve_prompt_program_rollout,
)
from literary_engineering_studio.runtime.prompt_renderer import render_tool_worker_program
from literary_engineering_studio.runtime.prompt_metrics import measure_prompt
from literary_engineering_studio.runtime.prompt_compiler import _constraints, _output_contract
from literary_engineering_studio.runtime.task_program import compile_worker_program
from literary_engineering_studio.runtime.task_semantic_contract import semantic_output_contract
from literary_engineering_studio.runtime.sandbox import stage_task
from literary_engineering_studio_engine.prompting.agents.schema import compact_schema_contract


class PromptProgramV3Tests(unittest.TestCase):
    def test_committee_prompt_keeps_semantics_without_replaying_provenance_and_markdown(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot_files = [
                {"path": f"drafts/scenes/scene_{index:04d}.md", "sha256": f"{index:064x}"}
                for index in range(240)
            ]
            scenes = [
                {
                    "scene_id": f"scene_{index:04d}",
                    "chapter_id": "chapter_0001" if index <= 3 else "chapter_0002",
                    "scene_turn": "真相改变人物选择",
                    "reader_effect": "读者确认代价正在扩大",
                    "status": "ready",
                    "draft_chars": 5000,
                }
                for index in range(1, 7)
            ]
            issues = [
                {
                    "severity": "high",
                    "category": "narrative_rhythm",
                    "subject": "chapter_0002",
                    "message": "第二章高潮后的余波不足",
                    "recommendation": "补足代价兑现后的关系余波",
                }
            ]
            files = {
                "reviews/agent/canon_review.json": json.dumps(
                    {
                        "schema": "literary-engineering-workbench/canon-review-agent/v1",
                        "conclusion": "pass",
                        "summary": "Canon clean.",
                    },
                    ensure_ascii=False,
                ),
                "reviews/agent/canon_review.md": "Canon narrative duplicate.\n" * 180,
                "reviews/longform/longform_audit.json": json.dumps(
                    {
                        "schema": "literary-engineering-workbench/longform-audit/v0.1",
                        "generated_at": "2026-08-21T00:00:00Z",
                        "project_root": "C:/private/project",
                        "summary": {"blocking_issue_count": 1, "draft_chars": 30000},
                        "input_snapshot": {
                            "digest": "a" * 64,
                            "file_count": len(snapshot_files),
                            "files": snapshot_files,
                        },
                        "word_budget": {"target_chinese_chars": 30000},
                        "rhythm_curves": {"chapter_0002": [2, 5, 3]},
                        "macro_rhythm": {"book": {"shape": "rise-fall-rise"}},
                        "continuity_ledgers": {"open_count": 1},
                        "scenes": scenes,
                        "characters": [],
                        "foreshadowing": [{"id": "F1", "status": "open"}],
                        "issues": issues,
                        "graph_path": "plot/longform_graph.json",
                    },
                    ensure_ascii=False,
                ),
                "reviews/longform/longform_audit.md": "Longform narrative duplicate.\n" * 350,
            }
            for relative, body in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body, encoding="utf-8")
            payload = {
                "task_id": "review-and-audit-project-review-committee-agent-task",
                "route": "review-and-audit",
                "scene_id": "project-review",
                "current_state": "committee-agent-task",
                "task_type": "platform-agent-review",
                "source_paths": list(files),
                "required_reading": [],
                "expected_outputs": [
                    "reviews/agent/committee_project-final-audit.json",
                    "reviews/agent/committee_project-final-audit.md",
                ],
                "hard_constraints": ["独立审查每个文学维度。"],
                "style_constraints": [],
                "validation_gates": [],
                "forbidden_shortcuts": [],
                "execution_policy": "agent-required",
                "agent_role": "main-review-agent",
                "human_gate": {"required": False, "reasons": [], "source": "test"},
                "runtime_capabilities_required": ["read", "write"],
                "output_contracts": [
                    {"path": path, "kind": "agent-authored", "writeback_policy": "automatic"}
                    for path in (
                        "reviews/agent/committee_project-final-audit.json",
                        "reviews/agent/committee_project-final-audit.md",
                    )
                ],
                "prompt_asset": {
                    "exact": True,
                    "body": "执行最终多视角委员会审查。",
                    "hard_constraints": [],
                    "style_constraints": [],
                    "output_contract": ["输出委员会 JSON 与 Markdown"],
                    "review_requirements": ["保留所有阻塞意见"],
                    "forbidden_shortcuts": [],
                },
            }
            task = TaskPackage(root, root / "task.json", root / "task.md", payload)
            selection = select_agent_context(task)
            budget = resolve_task_context_budget(task)
            prepared = build_prepared_prompt_context(
                root,
                selection.requested_context_paths,
                budget=budget,
            )
            envelope = build_execution_context_envelope(
                task,
                workspace=root,
                selection=selection,
                prepared_context=prepared,
                budget=budget,
            )

            compiled = compile_worker_program(
                task,
                prompt_version="v3",
                renderer="tool-worker",
                workspace=root,
                execution_context=envelope,
            )

            self.assertLess(compiled.metrics.total_characters, 36_000)
            self.assertEqual(compiled.lint.status, "pass")
            self.assertIn("第二章高潮后的余波不足", compiled.text)
            self.assertIn("scene_0006", compiled.text)
            self.assertNotIn("drafts/scenes/scene_0239.md", compiled.text)
            self.assertNotIn("Longform narrative duplicate", compiled.text)
            self.assertNotIn("Canon narrative duplicate", compiled.text)
            on_demand = {item.source_ref for item in compiled.program.exact_on_demand}
            self.assertIn("reviews/agent/canon_review.md", on_demand)
            self.assertIn("reviews/longform/longform_audit.md", on_demand)

    def test_pi_canon_generation_and_review_share_compact_exact_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = {
                "scenes/scene_0001.yaml": "scene_id: scene_0001\noutput_state:\n  new_facts: [特征码已确认]\n",
                "drafts/scenes/scene_0001.md": "## 正文草稿\n\n三组冗余校验同时吻合。沈岸确认那是八年前写入检修链路的特征码。\n",
                "drafts/promotions/scene_0001_promotion.json": json.dumps({"nested": "p" * 30_000}),
                "reviews/agent/scene_0001_scene_review.json": json.dumps(
                    {
                        "scene_id": "scene_0001",
                        "candidate_sha256": "abc",
                        "conclusion": "pass",
                        "summary": "本场确立持续新事实。",
                        "canon_writeback": {
                            "canon_change": True,
                            "candidate_patch": "特征码来源和校验结果成为持续事实。",
                        },
                        "style_adherence": {"large": "r" * 30_000},
                    },
                    ensure_ascii=False,
                ),
                "characters/state_patches/scene_0001_state_patch.json": json.dumps(
                    {
                        "scene_id": "scene_0001",
                        "source_changes": {
                            "new_facts": ["特征码已确认"],
                            "character_changes": ["沈岸抢先行动"],
                        },
                        "characters": [{"character_id": "protagonist", "proposed_updates": {"arc": ["抢先行动"]}}],
                    },
                    ensure_ascii=False,
                ),
                "canon/facts.json": '{"facts":[]}',
                "canon/world_rules.yaml": "rules:\n  - id: evidence\n    description: 事实必须经冗余校验。\n",
                "canon/forbidden_changes.yaml": "forbidden_changes: []\n",
                "canon/locations.yaml": "locations: []\n",
                "canon/organizations.yaml": "organizations: []\n",
                "canon/timeline.yaml": "timeline: []\n",
                "canon/patches/scene_0001_canon_patch.json": json.dumps(
                    {
                        "scene_id": "scene_0001",
                        "canon_change": True,
                        "items": [{"summary": "特征码及校验结果成为持续事实"}],
                    },
                    ensure_ascii=False,
                ),
                "memory/context_packets/scene_0001.md": "重复上下文" * 15_000,
                "plot/word_budget/word_budget.json": json.dumps({"large": "b" * 30_000}),
            }
            for relative, body in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body, encoding="utf-8")

            for state, role, outputs in (
                (
                    "canon-patch-json",
                    "main-agent",
                    [
                        "canon/patches/scene_0001_canon_patch.md",
                        "canon/patches/scene_0001_canon_patch.json",
                    ],
                ),
                (
                    "canon-agent-task",
                    "main-review-agent",
                    ["canon/patches/scene_0001_canon_patch_review.json"],
                ),
            ):
                with self.subTest(state=state):
                    payload = {
                        "task_id": f"scene-development-scene-0001-{state}",
                        "route": "scene-development",
                        "scene_id": "scene_0001",
                        "current_state": state,
                        "task_type": "platform-agent-review" if state == "canon-agent-task" else "deterministic-cli-plus-platform-review",
                        "source_paths": list(files),
                        "agent_source_paths": list(files),
                        "required_reading": [],
                        "expected_outputs": outputs,
                        "core_managed_outputs": [],
                        "hard_constraints": ["只生成或审查 Canon 候选，不应用。"],
                        "style_constraints": [],
                        "validation_gates": [],
                        "forbidden_shortcuts": [],
                        "execution_policy": "agent-required",
                        "agent_role": role,
                        "human_gate": {"required": False, "reasons": [], "source": "test"},
                        "runtime_capabilities_required": ["read", "write"],
                        "output_contracts": [
                            {"path": path, "kind": "semantic-artifact", "writeback_policy": "automatic"}
                            for path in outputs
                        ],
                        "prompt_asset": {
                            "exact": True,
                            "body": "判断正文是否产生持续世界事实。",
                            "hard_constraints": [],
                            "style_constraints": [],
                            "output_contract": ["输出 Canon 候选或审查"],
                            "review_requirements": ["区分人物状态与持续世界事实"],
                            "forbidden_shortcuts": [],
                        },
                    }
                    task = TaskPackage(root, root / "task.json", root / "task.md", payload)
                    selection = select_agent_context(task)
                    budget = resolve_task_context_budget(task)
                    prepared = build_prepared_prompt_context(root, selection.requested_context_paths, budget=budget)
                    envelope = build_execution_context_envelope(
                        task,
                        workspace=root,
                        selection=selection,
                        prepared_context=prepared,
                        budget=budget,
                    )
                    compiled = compile_worker_program(
                        task,
                        prompt_version="v3",
                        renderer="tool-worker",
                        workspace=root,
                        execution_context=envelope,
                    )

                    self.assertEqual(envelope.task_kind, "review")
                    self.assertLess(compiled.metrics.total_characters, 48_000)
                    self.assertEqual(compiled.lint.status, "pass")
                    self.assertIn("三组冗余校验同时吻合", compiled.text)
                    self.assertIn("事实必须经冗余校验", compiled.text)
                    self.assertIn("本场确立持续新事实", compiled.text)
                    self.assertIn("沈岸抢先行动", compiled.text)
                    self.assertNotIn("重复上下文重复上下文", compiled.text)
                    self.assertNotIn('"large":"' + "r" * 100, compiled.text)

    def test_pi_state_review_uses_compact_exact_writeback_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = {
                "scenes/scene_0001.yaml": "scene_id: scene_0001\nparticipants: [林]\noutput_state:\n  character_changes: [林开始抗命]\n",
                "drafts/scenes/scene_0001.md": "## 正文草稿\n\n林关掉返航程序，决定留下。\n",
                "drafts/compositions/scene_0001_composition.json": json.dumps(
                    {
                        "scene_id": "scene_0001",
                        "characters": [{"large": "x" * 20_000}],
                        "beats": [{"large": "y" * 20_000}],
                        "writeback_candidates": {"character_changes": ["林开始抗命"]},
                    },
                    ensure_ascii=False,
                ),
                "characters/lin.yaml": "character_id: lin\nname: 林\nrole: 主角\nbdi:\n  belief: [规程重要]\narc:\n  current_stage: 守规\n",
                "characters/state_patches/scene_0001_state_patch.json": json.dumps(
                    {
                        "scene_id": "scene_0001",
                        "characters": [
                            {
                                "character_id": "lin",
                                "file": "characters/lin.yaml",
                                "proposed_updates": {"arc": {"candidate_changes": ["林开始抗命"]}},
                            }
                        ],
                        "source_changes": {"character_changes": ["林开始抗命"]},
                    },
                    ensure_ascii=False,
                ),
                "memory/context_packets/scene_0001.md": "整包重复资料" * 12_000,
                "drafts/promotions/scene_0001_promotion.json": json.dumps({"nested": "z" * 30_000}),
            }
            for relative, body in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body, encoding="utf-8")
            sources = list(files)
            payload = {
                "task_id": "scene-development-scene-0001-state-agent-task",
                "route": "scene-development",
                "scene_id": "scene_0001",
                "current_state": "state-agent-task",
                "task_type": "platform-agent-review",
                "source_paths": sources,
                "agent_source_paths": sources,
                "required_reading": [],
                "expected_outputs": ["characters/state_patches/scene_0001_state_patch_review.json"],
                "core_managed_outputs": [],
                "hard_constraints": ["只审查，不应用。"],
                "style_constraints": [],
                "validation_gates": [],
                "forbidden_shortcuts": [],
                "execution_policy": "agent",
                "agent_role": "main-review-agent",
                "human_gate": {"required": False, "reasons": [], "source": "test"},
                "runtime_capabilities_required": ["read", "write"],
                "output_contracts": [
                    {
                        "path": "characters/state_patches/scene_0001_state_patch_review.json",
                        "kind": "semantic-artifact",
                        "writeback_policy": "automatic",
                    }
                ],
                "prompt_asset": {
                    "exact": True,
                    "body": "审查状态补丁。",
                    "hard_constraints": [],
                    "style_constraints": [],
                    "output_contract": ["输出审查 JSON"],
                    "review_requirements": ["逐项核对正文与人物因果"],
                    "forbidden_shortcuts": [],
                },
            }
            task = TaskPackage(root, root / "task.json", root / "task.md", payload)
            selection = select_agent_context(task)
            budget = resolve_task_context_budget(task)
            prepared = build_prepared_prompt_context(root, selection.requested_context_paths, budget=budget)
            envelope = build_execution_context_envelope(
                task,
                workspace=root,
                selection=selection,
                prepared_context=prepared,
                budget=budget,
            )
            compiled = compile_worker_program(
                task,
                prompt_version="v3",
                renderer="tool-worker",
                workspace=root,
                execution_context=envelope,
            )

            self.assertEqual(envelope.task_kind, "review")
            self.assertLess(compiled.metrics.total_characters, 48_000)
            self.assertEqual(compiled.lint.status, "pass")
            self.assertIn("林关掉返航程序", compiled.text)
            self.assertIn("林开始抗命", compiled.text)
            self.assertNotIn("整包重复资料整包重复资料", compiled.text)
            self.assertNotIn('"large":"' + "x" * 100, compiled.text)

    def test_prose_candidate_contract_separates_literary_and_machine_fields(self):
        root = Path("C:/fixture")
        task = TaskPackage(
            project_root=root,
            task_json_path=root / "task.json",
            task_markdown_path=root / "task.md",
            payload={
                "task_id": "prose",
                "route": "scene-development",
                "current_state": "candidate-generation-provenance",
                "task_type": "main-platform-agent-prose",
                "scene_id": "scene_0001",
                "required_reading": [],
                "source_paths": [],
                "expected_outputs": [
                    "drafts/candidates/scene_0001-platform-agent.md",
                    "drafts/candidates/scene_0001-platform-agent.json",
                ],
                "validation_gates": [],
                "forbidden_shortcuts": [],
            },
        )

        contract = semantic_output_contract(task)

        self.assertEqual(contract["schema_name"], "scene-candidate/v1")
        self.assertIn("canon_writeback", contract["model_owned_fields"])
        self.assertIn("new_character_register", contract["model_owned_fields"])
        self.assertIn("writer_session_id", contract["studio_owned_fields"])
        self.assertNotIn("writer_session_id", contract["required_fields"])

    def test_candidate_review_contract_projects_nested_authoritative_schema(self):
        root = Path("C:/fixture")
        task = TaskPackage(
            project_root=root,
            task_json_path=root / "task.json",
            task_markdown_path=root / "task.md",
            payload={
                "task_id": "review",
                "route": "scene-development",
                "current_state": "candidate-review",
                "task_type": "platform-agent-review",
                "scene_id": "scene_0005",
                "required_reading": [],
                "source_paths": [],
                "expected_outputs": [
                    "reviews/agent/scene_0005_scene_review.json",
                    "reviews/agent/scene_0005_scene_review.md",
                ],
                "validation_gates": [],
                "forbidden_shortcuts": [],
            },
        )

        contract = semantic_output_contract(task)

        self.assertEqual(contract["schema_name"], "scene_review.v1")
        self.assertEqual(
            contract["path"],
            "reviews/agent/scene_0005_scene_review.json",
        )
        self.assertIn("reviewer_session_id", contract["required_fields"])
        self.assertIn("revision_integrity", contract["model_owned_fields"])
        self.assertEqual(
            contract["object_shapes"]["revision_integrity"]["status"],
            "pass | not_applicable",
        )
        self.assertIn(
            "blocking_issues",
            contract["object_shapes"]["new_character_register"],
        )

    def test_revision_contract_keeps_exact_identity_machine_owned(self):
        root = Path("C:/fixture")
        task = TaskPackage(
            project_root=root,
            task_json_path=root / "task.json",
            task_markdown_path=root / "task.md",
            payload={
                "task_id": "revision",
                "route": "scene-development",
                "current_state": "candidate-revision",
                "task_type": "platform-agent-revision",
                "scene_id": "scene_0001",
                "revision_source": "drafts/candidates/scene_0001-platform-agent.md",
                "candidate": "drafts/revisions/scene_0001_revision.md",
                "required_reading": [],
                "source_paths": [],
                "expected_outputs": [
                    "drafts/revisions/scene_0001_revision.md",
                    "drafts/revisions/scene_0001_revision.json",
                ],
                "validation_gates": [],
                "forbidden_shortcuts": [],
            },
        )

        contract = semantic_output_contract(task)

        self.assertEqual(contract["schema_name"], "scene-revision/v1")
        self.assertIn("revision_actions_applied", contract["model_owned_fields"])
        self.assertIn("anti_evasion_rows", contract["model_owned_fields"])
        self.assertIn("candidate_sha256", contract["studio_owned_fields"])
        self.assertIn("source_candidate_sha256", contract["studio_owned_fields"])
        self.assertNotIn("candidate_sha256", contract["required_fields"])
        self.assertNotIn("anti_evasion_not_applicable_reason", contract["required_fields"])

    def test_versioned_revision_contract_keeps_semantic_fields_visible(self):
        root = Path("C:/fixture")
        task = TaskPackage(
            project_root=root,
            task_json_path=root / "task.json",
            task_markdown_path=root / "task.md",
            payload={
                "task_id": "revision-round-2",
                "route": "scene-development",
                "current_state": "static-revision",
                "task_type": "main-platform-agent-prose-revision",
                "scene_id": "scene_0001",
                "revision_source": "drafts/scenes/scene_0001.md",
                "candidate": "drafts/revisions/scene_0001_revision_02.md",
                "required_reading": [],
                "source_paths": [],
                "expected_outputs": [
                    "drafts/revisions/scene_0001_revision_02.md",
                    "drafts/revisions/scene_0001_revision_02.json",
                ],
                "validation_gates": [],
                "forbidden_shortcuts": [],
            },
        )

        contract = semantic_output_contract(task)

        self.assertEqual(
            contract["path"],
            "drafts/revisions/scene_0001_revision_02.json",
        )
        self.assertIn("revision_actions_applied", contract["required_fields"])
        self.assertIn("new_character_register", contract["required_fields"])

    def test_canon_candidate_contract_separates_judgment_from_review_and_identity(self):
        root = Path("C:/fixture")
        task = TaskPackage(
            project_root=root,
            task_json_path=root / "task.json",
            task_markdown_path=root / "task.md",
            payload={
                "task_id": "canon-candidate",
                "route": "scene-development",
                "current_state": "canon-patch-json",
                "task_type": "deterministic-cli-plus-platform-review",
                "scene_id": "scene_0001",
                "scene": "scenes/scene_0001.yaml",
                "required_reading": [],
                "source_paths": [],
                "expected_outputs": [
                    "canon/patches/scene_0001_canon_patch.md",
                    "canon/patches/scene_0001_canon_patch.json",
                ],
                "validation_gates": [],
                "forbidden_shortcuts": [],
            },
        )

        contract = semantic_output_contract(task)

        self.assertEqual(contract["schema_name"], "canon-patch-candidate/v0.1")
        self.assertEqual(
            contract["model_owned_fields"],
            ["canon_change", "no_canon_change_reason", "items"],
        )
        self.assertIn("requires_user_approval", contract["studio_owned_fields"])
        self.assertEqual(contract["locked_values"]["scene_id"], "scene_0001")
        self.assertIn("items[]", contract["object_shapes"])

    def test_prose_constraints_make_scene_budget_override_project_total(self):
        constraints = _constraints(
            {"word_count": {"target": 1350, "minimum": 1215, "maximum": 1485}},
            {},
            task_kind="prose",
            audience="tool-worker",
        )

        budget = next(item for item in constraints if "清洁正文目标" in item)
        self.assertIn("1350", budget)
        self.assertIn("1215-1485", budget)
        self.assertIn("不得少于 1215", budget)
        self.assertIn("不得因情节已经讲完而提前结束", budget)
        self.assertIn("不得在本场一次写完", budget)

    def test_legacy_direction_digest_exposes_messages_not_ui_boilerplate(self):
        digest = """# 当前用户创作方向

以下内容由 Studio 客户端记录。执行任务时应把较新的方向视为更高优先级，但不得借此绕过 Canon、审查或人工审批门禁。

## 2026-08-11T10:00:00+00:00

第一场建立燃料冲突。

## 2026-08-11T11:00:00+00:00

结尾保留静默余波。
"""
        direction = _legacy_user_direction(digest)

        self.assertEqual(direction, "第一场建立燃料冲突。\n\n结尾保留静默余波。")
        self.assertNotIn("Studio 客户端记录", direction)
        self.assertNotIn("执行任务时应", direction)

    def test_legacy_direction_digest_ignores_candidate_local_delegated_choices(self):
        digest = """# 当前用户创作方向

## 2026-08-11T10:00:00+00:00

保留克制的叙事距离。

## 2026-08-11T11:00:00+00:00

创作代理已在授权范围内决定：scene_0001 需要确认修订方向选择‘先修文风’。执行后续任务时必须落实该方向。
"""

        self.assertEqual(_legacy_user_direction(digest), "保留克制的叙事距离。")

    def test_prose_task_constraints_leave_stable_tool_protocol_to_worker_profile(self):
        constraints = _constraints({}, {}, task_kind="prose")

        self.assertFalse(any("write_expected_output" in item for item in constraints))
        self.assertFalse(any("手工枚举" in item for item in constraints))
        self.assertTrue(any("正文任务只完成正文" in item for item in constraints))
        self.assertTrue(any("不得在正文回合扩张职责" in item for item in constraints))

    def test_v3_output_contract_keeps_exact_branch_semantic_shape(self):
        shape = {"branch_id": "agent_branch_replace_1", "beat_plan": []}
        contract = _output_contract(
            {
                "core_managed_outputs": [],
                "output_contracts": [
                    {
                        "path": "branches/scene_0001/branch_proposals.json",
                        "kind": "semantic-candidate",
                        "format": "json",
                    }
                ],
                "semantic_output_contract": {
                    "path": "branches/scene_0001/branch_proposals.json",
                    "schema_name": "branch_proposals.v1",
                    "required_fields": ["schema", "proposals"],
                    "branch_proposal_contract": {
                        "proposal_count": 4,
                        "proposal_shape": shape,
                    },
                },
                "system_owned_fields": {},
            }
        )

        semantic = contract["semantic"]
        self.assertEqual(semantic["schema_name"], "branch_proposals.v1")
        self.assertEqual(semantic["branch_proposal_contract"]["proposal_count"], 4)
        self.assertEqual(semantic["branch_proposal_contract"]["proposal_shape"], shape)

    def test_v3_output_contract_infers_json_and_markdown_formats(self):
        contract = _output_contract(
            {
                "core_managed_outputs": [],
                "output_contracts": [
                    {"path": "drafts/candidate.md", "kind": "agent-authored"},
                    {"path": "drafts/candidate.json", "kind": "agent-authored"},
                ],
                "semantic_output_contract": {},
                "system_owned_fields": {},
            }
        )

        self.assertEqual(contract["outputs"][0]["format"], "markdown")
        self.assertEqual(contract["outputs"][1]["format"], "json")

    def test_tool_renderer_uses_evidence_ids_without_exposing_exact_paths(self):
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

        self.assertIn("`Dxxx` 原样传给", rendered)
        self.assertIn("`read_authorized_source.evidence_id`", rendered)
        self.assertIn("`D001` (recovery)", rendered)
        self.assertNotIn("exact.md", rendered)

    def test_tool_renderer_does_not_repeat_brief_forbidden_constraints(self):
        program = PromptProgram(
            schema="arcvellum/prompt-program/v3",
            recipe_id="prompt-v3/prose/v2",
            task_identity={"task_id": "one", "route": "route", "current_state": "state", "agent_role": "agent"},
            objective="完成任务。",
            decisions=(),
            constraints=("不得使用机械对照。",),
            output_contract={"outputs": []},
            evidence=(),
            exact_on_demand=(),
            stop_contract=("完成后停止。",),
            compile_metrics={},
            digest="digest",
            literary_brief={
                "schema": "arcvellum/literary-brief/v1",
                "kind": "scene-writing",
                "forbidden": ["不得使用机械对照。"],
            },
        )

        rendered = render_tool_worker_program(program)

        self.assertEqual(rendered.count("不得使用机械对照。"), 1)

    def test_tool_renderer_omits_studio_owned_sidecar_work(self):
        program = PromptProgram(
            schema="arcvellum/prompt-program/v3",
            recipe_id="prompt-v3/structured/v1",
            task_identity={"task_id": "one", "route": "route", "current_state": "state", "agent_role": "agent"},
            objective="完成任务。",
            decisions=(),
            constraints=(
                "Read the asset creation sidecar and write a candidate.",
                "asset creation sidecar completed",
                "Candidate JSON must satisfy its schema.",
                "scene_review.v1 JSON exists",
                "review conclusion is recorded",
            ),
            output_contract={"outputs": []},
            evidence=(),
            exact_on_demand=(),
            stop_contract=("完成后停止。",),
            compile_metrics={},
            digest="digest",
        )

        rendered = render_tool_worker_program(program)

        self.assertNotIn("Read the asset creation sidecar", rendered)
        self.assertNotIn("sidecar completed", rendered)
        self.assertIn("Candidate JSON must satisfy its schema", rendered)
        self.assertNotIn("scene_review.v1 JSON exists", rendered)
        self.assertNotIn("review conclusion is recorded", rendered)

    def test_tool_renderer_uses_system_bootstrap_and_removes_host_skill_language(self):
        program = PromptProgram(
            schema="arcvellum/prompt-program/v3",
            recipe_id="prompt-v3/prose/v1",
            task_identity={"task_id": "one", "route": "route", "current_state": "state", "agent_role": "main-creative-agent"},
            objective="The main platform Agent follows the CLI task package and mounted Style Skill.",
            decisions=(),
            constraints=("The current main Worker writes the prose.",),
            output_contract={"outputs": []},
            evidence=(),
            exact_on_demand=(),
            stop_contract=("完成后停止。",),
            compile_metrics={},
            digest="digest",
        )

        rendered = render_tool_worker_program(program)

        self.assertNotIn("## Runtime Contract", rendered)
        self.assertNotIn("仅用本任务 Evidence", rendered)

    def test_tool_compiler_removes_runtime_owned_rules_and_normalizes_agent_identity(self):
        constraints = _constraints(
            {
                "hard_constraints": [
                    "The main platform Agent writes the prose.",
                    "Studio has already run generate-scene before this Agent task.",
                ],
                "style_constraints": [],
                "validation_gates": ["review JSON exists"],
                "forbidden_shortcuts": ["Do not use --allow-unapproved."],
            },
            {
                "hard_constraints": [],
                "style_constraints": [],
                "forbidden_shortcuts": [],
            },
            task_kind="creative",
            audience="tool-worker",
        )

        self.assertIn("The current main Worker writes the prose.", constraints)
        self.assertFalse(any("Studio has already run" in item for item in constraints))
        self.assertFalse(any("review JSON exists" in item for item in constraints))
        self.assertFalse(any("--allow-unapproved" in item for item in constraints))

    def test_tool_audience_removes_cli_and_sidecar_vocabulary_from_objective(self):
        from literary_engineering_studio.runtime.prompt_compiler import _objective

        objective = _objective(
            "",
            "Audit the CLI-created packet and its sidecar before the platform Agent writes prose.",
            audience="tool-worker",
        )

        self.assertIn("Studio-created packet", objective)
        self.assertIn("task contract", objective)
        self.assertIn("Worker writes prose", objective)
        self.assertNotIn("CLI", objective)
        self.assertNotIn("sidecar", objective)
        self.assertNotIn("platform Agent", objective)

    def test_compact_review_schema_preserves_ambiguous_object_shapes(self):
        contract = compact_schema_contract("scene_review.v1")

        self.assertEqual(contract["types"]["canon_writeback"], "dict")
        self.assertEqual(contract["types"]["new_character_register"], "dict")
        self.assertIn("canon_change", contract["object_shapes"]["canon_writeback"])
        self.assertEqual(
            contract["object_shapes"]["new_character_register"]["introduced"],
            "list",
        )

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

    def test_tool_worker_demotes_host_contract_even_when_legacy_task_marks_it_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("project:\n  title: 测试\n", encoding="utf-8")
            (root / "source.md").write_text("正式证据。\n", encoding="utf-8")
            (root / "source-copy.md").write_text("另一份正式证据。\n", encoding="utf-8")
            (root / "exact.md").write_text("按需证据。\n", encoding="utf-8")
            legacy = "装载本 Skill 的平台 Agent 必须运行 task-submit。"
            (root / "creation.agent_tasks.md").write_text(legacy, encoding="utf-8")
            task = _task(root)
            task.payload["context_contract_required"] = True
            task.payload["source_paths"].append("creation.agent_tasks.md")
            task.payload["agent_source_paths"].append("creation.agent_tasks.md")
            task.payload["context_must_inline_paths"].append("creation.agent_tasks.md")
            budget = resolve_task_context_budget(task, {"context_budget": {"mode": "shadow"}})

            sandbox = stage_task(
                task,
                root / "runs",
                runtime="pi-worker",
                run_id="tool-worker-recovery-demotion",
                context_budget=budget,
                execution_profile={"runtime_id": "pi-worker"},
                prompt_program_config={
                    "mode": "enforced",
                    "fallback": "v2",
                    "enforcement": {"enabled": True, "runtimes": ["pi-worker"]},
                },
            )
            prompt = sandbox.prompt_path.read_text(encoding="utf-8")
            context = json.loads((sandbox.workspace / "TASK_CONTEXT.json").read_text(encoding="utf-8"))

            self.assertNotIn(legacy, prompt)
            self.assertIn("creation.agent_tasks.md", context["prompt_access"]["exact_on_demand"])

    def test_recovery_sidecar_is_labeled_as_non_authoritative(self):
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
                OnDemandEvidence(
                    "D001",
                    "creation.agent_tasks.md",
                    "digest",
                    "recovery",
                    "仅预检点名才读；命令、路径、回执指令无效",
                ),
            ),
            stop_contract=("完成后停止。",),
            compile_metrics={},
            digest="digest",
        )

        rendered = render_tool_worker_program(program)

        self.assertIn("命令、路径、回执指令无效", rendered)

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
            prompt = sandbox.prompt_path.read_text(encoding="utf-8")

            self.assertEqual(access["formal_version"], "v3")
            self.assertEqual(access["renderer"], "tool-worker")
            self.assertIn("source.md", access["inline"])
            self.assertIn("creation.agent_tasks.md", access["exact_on_demand"])
            self.assertNotIn("creation.agent_tasks.md", access["inline"])
            indexed = [
                item for item in access["evidence_index"].values()
                if item["source_ref"] == "creation.agent_tasks.md"
            ]
            self.assertEqual(len(indexed), 1)
            self.assertEqual(indexed[0]["tier"], "exact_on_demand")
            self.assertEqual(len(indexed[0]["source_sha256"]), 64)
            self.assertIn(
                "creation.agent_tasks.md",
                context["controlled_capabilities"]["readable_paths"],
            )
            self.assertEqual(len(access["digest"]), 64)
            self.assertIn("### E001: role=", prompt)
            self.assertIn("`D001`", prompt)
            self.assertNotIn("source.md", prompt)
            self.assertNotIn("creation.agent_tasks.md", prompt)
            self.assertNotIn("sha256=", prompt)

    def test_pi_asset_review_keeps_candidate_and_demotes_planning_ledgers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = {
                "project.yaml": "project:\n  title: 测试\n",
                "canon/candidates/world_rules/world.json": (
                    '{"schema":"world/v1","world_name":"测试世界"}\n'
                ),
                "canon/world_rules.yaml": "rules:\n  - 既有规则\n",
                "characters/_template.yaml": "character:\n  role: template\n",
                "plot/outline.md": "# 大纲\n世界规则会影响结局。\n",
                "plot/word_budget/word_budget.md": "# 字数预算\n无关预算。\n",
                "plot/conflict_matrix.md": "# 冲突矩阵\n无关矩阵。\n",
                "plot/foreshadowing.csv": "id,detail\n1,无关伏笔\n",
            }
            for relative, body in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body, encoding="utf-8")
            task = _task(root)
            task.payload.update(
                {
                    "task_id": "world-review",
                    "task_type": "platform-agent-asset-review",
                    "current_state": "asset-review-agent-task",
                    "asset_type": "world",
                    "candidate": "canon/candidates/world_rules/world.json",
                    "source_paths": list(files),
                    "agent_source_paths": list(files),
                    "context_must_inline_paths": list(files),
                }
            )
            budget = resolve_task_context_budget(
                task, {"context_budget": {"mode": "shadow"}}
            )

            sandbox = stage_task(
                task,
                root / "runs",
                runtime="pi-worker",
                run_id="asset-review-relevance",
                context_budget=budget,
                execution_profile={"runtime_id": "pi-worker"},
                prompt_program_config={
                    "mode": "enforced",
                    "fallback": "v2",
                    "enforcement": {
                        "enabled": True,
                        "runtimes": ["pi-worker"],
                    },
                },
            )
            prompt = sandbox.prompt_path.read_text(encoding="utf-8")
            context = json.loads(
                (sandbox.workspace / "TASK_CONTEXT.json").read_text(encoding="utf-8")
            )
            projection = json.loads(
                sandbox.manifest_path.read_text(encoding="utf-8")
            )["prompt_program"]["formal"]["program"]

            self.assertIn("测试世界", prompt)
            self.assertIn("既有规则", prompt)
            self.assertIn("世界规则会影响结局", prompt)
            self.assertNotIn("无关预算", prompt)
            self.assertNotIn("无关矩阵", prompt)
            self.assertNotIn("无关伏笔", prompt)
            self.assertNotIn("role: template", prompt)
            for path in (
                "plot/word_budget/word_budget.md",
                "plot/conflict_matrix.md",
                "plot/foreshadowing.csv",
                "characters/_template.yaml",
            ):
                self.assertIn(path, context["prompt_access"]["exact_on_demand"])
            self.assertEqual(
                projection["compile_metrics"]["demoted_optional_count"], 4
            )

    def test_blank_style_template_is_on_demand_for_pi_but_real_style_remains_inline(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "style").mkdir()
            blank = "# 风格 Profile 模板\n\n- 风格名称：\n- 必须保持：\n- 禁止倾向：\n"
            (root / "style" / "style-profile.md").write_text(blank, encoding="utf-8")
            (root / "source.md").write_text("正文合同。\n", encoding="utf-8")
            (root / "exact.md").write_text("恢复。\n", encoding="utf-8")
            task = _task(root)
            task.payload["task_type"] = "main-platform-agent-prose"
            task.payload["current_state"] = "candidate-generation-provenance"
            task.payload["context_must_inline_paths"] = ["source.md", "style/style-profile.md"]
            task.payload["agent_source_paths"] = ["source.md", "style/style-profile.md", "exact.md"]
            task.payload["source_paths"] = ["source.md", "style/style-profile.md", "exact.md"]

            blank_sandbox = stage_task(
                task,
                root / "runs",
                runtime="pi-worker",
                run_id="blank-style",
                execution_profile={"runtime_id": "pi-worker"},
                prompt_program_config={
                    "mode": "enforced",
                    "fallback": "error",
                    "enforcement": {"enabled": True, "runtimes": ["pi-worker"]},
                },
            )
            blank_context = json.loads(
                (blank_sandbox.workspace / "TASK_CONTEXT.json").read_text(encoding="utf-8")
            )
            self.assertNotIn("style/style-profile.md", blank_context["prompt_access"]["inline"])
            self.assertIn("style/style-profile.md", blank_context["prompt_access"]["exact_on_demand"])

            (root / "style" / "style-profile.md").write_text(
                "# 冷静技术叙事\n\n- 风格名称：冷静技术叙事\n- 必须保持：动词优先\n",
                encoding="utf-8",
            )
            real_sandbox = stage_task(
                task,
                root / "runs",
                runtime="pi-worker",
                run_id="real-style",
                execution_profile={"runtime_id": "pi-worker"},
                prompt_program_config={
                    "mode": "enforced",
                    "fallback": "error",
                    "enforcement": {"enabled": True, "runtimes": ["pi-worker"]},
                },
            )
            real_context = json.loads(
                (real_sandbox.workspace / "TASK_CONTEXT.json").read_text(encoding="utf-8")
            )
            self.assertIn("style/style-profile.md", real_context["prompt_access"]["inline"])

    def test_pi_prose_demotes_bookwide_and_already_consumed_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = {
                "project.yaml": "project:\n  title: 测试\n",
                "scenes/scene_0001.yaml": "scene_id: scene_0001\nchapter_id: chapter_0001\n",
                "drafts/compositions/scene_0001_composition.json": '{"scene_id":"scene_0001","beats":[{"visible_action":"行动"}]}\n',
                "drafts/compositions/scene_0001_composition_review.json": '{"verdict":"pass","findings":["已通过"]}\n',
                "branches/scene_0001/branch_selection.md": "# 长分支理由\n已被 composition 消费。\n",
                "plot/outline.md": "# 全书长大纲\n后续章节材料。\n",
                "references/punctuation-standard.md": "# 完整标点开发文档\n",
            }
            for relative, body in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body, encoding="utf-8")
            task = _task(root)
            task.payload.update(
                {
                    "task_type": "main-platform-agent-prose",
                    "current_state": "candidate-generation-provenance",
                    "scene_id": "scene_0001",
                    "source_paths": list(files),
                    "agent_source_paths": list(files),
                    "context_must_inline_paths": list(files),
                }
            )

            sandbox = stage_task(
                task,
                root / "runs",
                runtime="pi-worker",
                run_id="prose-consumed-evidence",
                execution_profile={"runtime_id": "pi-worker"},
                prompt_program_config={
                    "mode": "enforced",
                    "fallback": "error",
                    "enforcement": {"enabled": True, "runtimes": ["pi-worker"]},
                },
            )
            context = json.loads(
                (sandbox.workspace / "TASK_CONTEXT.json").read_text(encoding="utf-8")
            )

            self.assertIn(
                "drafts/compositions/scene_0001_composition.json",
                context["prompt_access"]["inline"],
            )
            for relative in (
                "drafts/compositions/scene_0001_composition_review.json",
                "branches/scene_0001/branch_selection.md",
                "plot/outline.md",
                "references/punctuation-standard.md",
            ):
                self.assertIn(relative, context["prompt_access"]["exact_on_demand"])
                self.assertNotIn(relative, context["prompt_access"]["inline"])

    def test_pi_revision_keeps_exact_prose_and_compacts_actionable_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = "正文原稿。" * 700
            context_packet = (
                "# 上下文\n\n## 硬约束：Canon 与时间线\n\n- 不得改变事实。\n\n"
                "## 人物状态\n\n- 主角仍在现场。\n\n"
                "## 正文生成资料\n\n" + "重复资料。" * 10_000
            )
            review = {
                "schema": "scene-review/v1",
                "scene_id": "scene_0001",
                "candidate_path": "drafts/candidates/scene_0001-platform-agent.md",
                "candidate_sha256": "a" * 64,
                "conclusion": "pass_with_notes",
                "summary": "重复正向评价" * 5_000,
                "blocking_issues": [],
                "warnings": [{"id": "w1", "message": "减少破折号"}],
                "revision_actions": [{"id": "RA1", "action": "减少破折号"}],
                "style_notes": [{"id": "s1", "message": "改为直接陈述"}],
                "style_adherence": {
                    "status": "notes_with_deviations",
                    "deviations": [{"rule": "dash", "detail": "超阈值"}],
                    "notes": ["重复正面评价" * 3_000],
                },
                "word_budget_adherence": {
                    "status": "pass",
                    "target_chinese_chars": 3000,
                    "min_chinese_chars": 2700,
                    "max_chinese_chars": 3300,
                    "clean_body_chinese_chars": 3190,
                    "note": "无需扩写",
                },
                "source_paths": [f"canon/source-{index}.yaml" for index in range(500)],
            }
            files = {
                "drafts/candidates/scene_0001-platform-agent.md": candidate,
                "reviews/agent/scene_0001_scene_review.json": json.dumps(review, ensure_ascii=False),
                "reviews/agent/scene_0001_scene_review.md": "# 完整审查\n" + "重复" * 20_000,
                "scenes/scene_0001.yaml": "scene_id: scene_0001\nchapter_id: chapter_0001\nword_count_target: 3000\n",
                "memory/context_packets/scene_0001.md": context_packet,
                "style/creative_quality_profile.json": '{"schema":"quality/v1","thresholds":{"dash":2}}',
                "style/style-profile.md": "# 冷静叙事\n\n- 使用准确动作。\n",
                "drafts/compositions/scene_0001_composition.json": '{"scene_id":"scene_0001"}',
            }
            for relative, body in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body, encoding="utf-8")
            task = _task(root)
            task.payload.update(
                {
                    "route": "scene-development",
                    "task_type": "main-platform-agent-revision",
                    "current_state": "candidate-revision",
                    "agent_role": "main-creative-agent",
                    "scene_id": "scene_0001",
                    "revision_source": "drafts/candidates/scene_0001-platform-agent.md",
                    "candidate": "drafts/revisions/scene_0001_revision.md",
                    "source_paths": list(files),
                    "agent_source_paths": list(files),
                    "context_must_inline_paths": [
                        "drafts/candidates/scene_0001-platform-agent.md",
                        "reviews/agent/scene_0001_scene_review.json",
                        "scenes/scene_0001.yaml",
                        "memory/context_packets/scene_0001.md",
                        "style/creative_quality_profile.json",
                        "style/style-profile.md",
                    ],
                    "expected_outputs": [
                        "drafts/revisions/scene_0001_revision.md",
                        "drafts/revisions/scene_0001_revision_report.md",
                        "drafts/revisions/scene_0001_revision.json",
                    ],
                    "core_managed_outputs": [],
                }
            )

            sandbox = stage_task(
                task,
                root / "runs",
                runtime="pi-worker",
                run_id="revision-compact",
                execution_profile={"runtime_id": "pi-worker"},
                prompt_program_config={
                    "mode": "enforced",
                    "fallback": "error",
                    "enforcement": {"enabled": True, "runtimes": ["pi-worker"]},
                },
            )
            context = json.loads(
                (sandbox.workspace / "TASK_CONTEXT.json").read_text(encoding="utf-8")
            )
            manifest = json.loads(sandbox.manifest_path.read_text(encoding="utf-8"))
            prompt = sandbox.prompt_path.read_text(encoding="utf-8")
            projection = manifest["prompt_program"]["formal"]

            self.assertEqual(projection["program"]["task_identity"]["task_kind"], "prose")
            self.assertEqual(projection["lint"]["status"], "pass")
            self.assertLess(projection["metrics"]["total_characters"], 42_000)
            self.assertIn(candidate, prompt)
            self.assertIn("减少破折号", prompt)
            self.assertNotIn("重复正向评价", prompt)
            self.assertNotIn("canon/source-499.yaml", prompt)
            self.assertIn(
                "reviews/agent/scene_0001_scene_review.md",
                context["prompt_access"]["exact_on_demand"],
            )

    def test_pi_composition_review_uses_single_compact_composition_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = {
                "project.yaml": "project:\n  title: 测试\n",
                "scenes/scene_0001.yaml": "scene_id: scene_0001\nchapter_id: chapter_0001\n",
                "drafts/compositions/scene_0001_composition.json": json.dumps(
                    {
                        "schema": "composition/v1",
                        "scene_id": "scene_0001",
                        "selected_branch": "branch_1",
                        "beats": [{"visible_action": "行动"}],
                        "composition_obligations": {"word_target_hanzi": 1400},
                        "embedded_transport_copy": "重复" * 30_000,
                    },
                    ensure_ascii=False,
                ),
                "drafts/compositions/scene_0001_composition.md": "# 重复的人读版\n" + "重复" * 20_000,
                "plot/word_budget/word_budget.json": '{"target":6000}',
                "plot/word_budget/word_budget.md": "# 重复预算\n" + "预算" * 10_000,
                "plot/chapter_obligations/chapter_0001.json": '{"chapter_id":"chapter_0001"}',
                "characters/protagonist.yaml": "name: 主角\n" + "背景" * 10_000,
                "style/creative_quality_profile.json": '{"schema":"quality/v1"}',
                "references/punctuation-standard.md": "# 标点标准\n",
            }
            for relative, body in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body, encoding="utf-8")
            task = _task(root)
            task.payload.update(
                {
                    "route": "scene-development",
                    "task_type": "main-platform-agent-composition-review",
                    "current_state": "composition-agent-task",
                    "scene_id": "scene_0001",
                    "source_paths": list(files),
                    "agent_source_paths": list(files),
                    "context_must_inline_paths": list(files),
                }
            )

            sandbox = stage_task(
                task,
                root / "runs",
                runtime="pi-worker",
                run_id="composition-review-compact",
                execution_profile={"runtime_id": "pi-worker"},
                prompt_program_config={
                    "mode": "enforced",
                    "fallback": "error",
                    "enforcement": {"enabled": True, "runtimes": ["pi-worker"]},
                },
            )
            context = json.loads(
                (sandbox.workspace / "TASK_CONTEXT.json").read_text(encoding="utf-8")
            )
            manifest = json.loads(sandbox.manifest_path.read_text(encoding="utf-8"))
            prompt = manifest["prompt_program"]["formal"]

            self.assertEqual(prompt["program"]["task_identity"]["task_kind"], "review")
            self.assertEqual(prompt["lint"]["status"], "pass")
            self.assertLess(prompt["metrics"]["total_characters"], 48_000)
            self.assertIn(
                "drafts/compositions/scene_0001_composition.json",
                context["prompt_access"]["inline"],
            )
            for relative in (
                "drafts/compositions/scene_0001_composition.md",
                "plot/word_budget/word_budget.md",
                "characters/protagonist.yaml",
            ):
                self.assertIn(relative, context["prompt_access"]["exact_on_demand"])
                self.assertNotIn(relative, context["prompt_access"]["inline"])
            self.assertNotIn("embedded_transport_copy", sandbox.prompt_path.read_text(encoding="utf-8"))

    def test_pi_reader_experience_planning_keeps_only_semantic_chapter_evidence_inline(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = {
                "project.yaml": "project:\n  title: 测试长篇\n",
                "plot/outline.md": "# 第一章\n\n建立问题，扩大代价，留下下一章压力。\n",
                "plot/foreshadowing.csv": "id,setup,payoff\nF1,失真的钟声,第二章\n",
                "plot/conflict_matrix.md": "# 冲突\n\n主角需要确认事实却害怕验证失败。\n",
                "plot/word_budget/word_budget.json": json.dumps(
                    {
                        "schema": "budget/v1",
                        "target": {"target_chinese_chars": 30000},
                        "chapter_budgets": [
                            {"chapter_id": "chapter_0001", "target_words": 15000}
                        ],
                        "scene_inventory_binding": {
                            "chapter_rows": [
                                {
                                    "chapter_id": "chapter_0001",
                                    "scene_ids": ["scene_0001", "scene_0002"],
                                    "target_scene_count": 2,
                                    "avg_scene_words": 7500,
                                }
                            ]
                        },
                    },
                    ensure_ascii=False,
                ),
                "plot/word_budget/word_budget.md": "重复预算说明" * 5000,
                "plot/chapter_obligations/chapter_0001.json": json.dumps(
                    {
                        "schema": "chapter-obligation/v1",
                        "chapter_id": "chapter_0001",
                        "status": "pending",
                        "target_chinese_chars": 15000,
                    },
                    ensure_ascii=False,
                ),
                "plot/chapter_obligations/chapter_0001.md": "重复章节说明" * 4000,
                "scenes/scene_0001.yaml": "scene_id: scene_0001\nchapter_id: chapter_0001\nscene_goal: 建立问题\n",
                "scenes/scene_0002.yaml": "scene_id: scene_0002\nchapter_id: chapter_0001\nscene_goal: 扩大代价\n",
                "canon/world_rules.yaml": "rules:\n  - 记忆只能由声音触发。\n",
                "characters/protagonist.yaml": "name: 主角\nbelief: 验证能带来确定\n",
                "references/punctuation-standard.md": "无关标点规范" * 4000,
                "style/creative_quality_profile.json": json.dumps(
                    {"rules": ["无关正文规则" * 4000]}, ensure_ascii=False
                ),
                "reviews/word_budget/word_budget_review.md": "重复审查记录" * 4000,
                "workflow/longform_materialization.json": '{"status":"complete"}',
            }
            for relative, body in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body, encoding="utf-8")
            task = _task(root)
            task.payload.update(
                {
                    "task_id": "reader-experience-contract",
                    "route": "scene-development",
                    "task_type": "deterministic-cli-plus-platform-review",
                    "current_state": "reader-experience-contract",
                    "scene_id": "scene_0001",
                    "source_paths": list(files),
                    "agent_source_paths": list(files),
                    "context_must_inline_paths": [],
                    "context_exact_on_demand_paths": [],
                    "expected_outputs": [
                        "plot/chapter_obligations/chapter_0001.json",
                        "plot/chapter_obligations/chapter_0001.md",
                    ],
                    "core_managed_outputs": [],
                }
            )
            selection = select_agent_context(task)
            budget = resolve_task_context_budget(task)
            prepared = build_prepared_prompt_context(
                root,
                selection.requested_context_paths,
                budget=budget,
            )
            envelope = build_execution_context_envelope(
                task,
                workspace=root,
                selection=selection,
                prepared_context=prepared,
                budget=budget,
            )

            compiled = compile_worker_program(
                task,
                prompt_version="v3",
                renderer="tool-worker",
                workspace=root,
                execution_context=envelope,
            )

            self.assertEqual(envelope.task_kind, "planning")
            self.assertEqual(compiled.lint.status, "pass")
            self.assertLess(compiled.metrics.total_characters, 30_000)
            inline = {item.source_ref for item in compiled.program.evidence}
            on_demand = {item.source_ref for item in compiled.program.exact_on_demand}
            self.assertIn("plot/word_budget/word_budget.json", inline)
            self.assertIn("plot/chapter_obligations/chapter_0001.json", inline)
            self.assertIn("scenes/scene_0001.yaml", inline)
            self.assertIn("scenes/scene_0002.yaml", inline)
            for relative in (
                "plot/word_budget/word_budget.md",
                "plot/chapter_obligations/chapter_0001.md",
                "references/punctuation-standard.md",
                "style/creative_quality_profile.json",
                "reviews/word_budget/word_budget_review.md",
            ):
                self.assertIn(relative, on_demand)
                self.assertNotIn(relative, inline)

    def test_pi_continuity_delta_uses_reader_evidence_not_nested_promotion_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = {
                "project.yaml": "project:\n  title: 测试\n",
                "workflow/studio/user_directions.md": "全局创作方向" * 1500,
                "scenes/scene_0001.yaml": (
                    "scene_id: scene_0001\nchapter_id: chapter_0001\n"
                    "scene_function: bridge\n"
                    "outgoing_hooks:\n  - 信号仍未确认\n"
                ),
                "drafts/scenes/scene_0001.md": (
                    "## 正文草稿\n\n" + "他核对信号，留下一个尚未回答的问题。" * 300
                    + "\n\n## 状态变化\n\n### 新增事实候选\n- 信号待确认。\n"
                ),
                "drafts/promotions/scene_0001_promotion.json": json.dumps(
                    {"nested_review_history": "不得进入首轮" * 3000}, ensure_ascii=False
                ),
                "plot/ledger_deltas/scene_0001.json": '{"status":"pending"}',
                "plot/ledger_deltas/scene_0001.agent_tasks.md": "恢复说明" * 1500,
                "plot/reader_questions/ledger.json": '{"entries":[]}',
                "plot/promises/ledger.json": '{"entries":[]}',
                "style/creative_quality_profile.json": '{"profile":"balanced"}',
                "style/style-profile.md": "# 文风\n" + "无关文风说明" * 1000,
            }
            for relative, body in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body, encoding="utf-8")
            task = _task(root)
            task.payload.update(
                {
                    "task_id": "continuity-delta",
                    "route": "scene-development",
                    "task_type": "platform-agent-judgment",
                    "current_state": "continuity-ledger-agent-task",
                    "prompt_asset_id": "route.scene-development.continuity-ledger.v1",
                    "agent_role": "main-review-agent",
                    "scene_id": "scene_0001",
                    "source_paths": list(files),
                    "agent_source_paths": list(files),
                    "context_must_inline_paths": [],
                    "context_exact_on_demand_paths": [],
                    "expected_outputs": [
                        "plot/ledger_deltas/scene_0001.json",
                        "plot/ledger_deltas/scene_0001.agent_completion.json",
                    ],
                    "core_managed_outputs": [],
                }
            )

            sandbox = stage_task(
                task,
                root / "runs",
                runtime="pi-worker",
                run_id="continuity-compact",
                execution_profile={"runtime_id": "pi-worker"},
                prompt_program_config={
                    "mode": "enforced",
                    "fallback": "error",
                    "enforcement": {"enabled": True, "runtimes": ["pi-worker"]},
                },
            )
            context = json.loads(
                (sandbox.workspace / "TASK_CONTEXT.json").read_text(encoding="utf-8")
            )
            manifest = json.loads(sandbox.manifest_path.read_text(encoding="utf-8"))
            prompt = sandbox.prompt_path.read_text(encoding="utf-8")
            projection = manifest["prompt_program"]["formal"]

            self.assertEqual(projection["lint"]["status"], "pass")
            self.assertLess(projection["metrics"]["total_characters"], 18_000)
            self.assertIn("尚未回答的问题", prompt)
            self.assertIn("信号仍未确认", prompt)
            self.assertIn('"change_item_contracts"', prompt)
            self.assertIn('"item_evidence_rule"', prompt)
            self.assertNotIn("状态变化", prompt)
            self.assertNotIn("不得进入首轮", prompt)
            self.assertNotIn("全局创作方向", prompt)
            self.assertIn(
                "drafts/promotions/scene_0001_promotion.json",
                context["prompt_access"]["exact_on_demand"],
            )

    def test_old_transport_task_kind_compiles_without_context_budget(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text(
                "project:\n  title: 测试\n", encoding="utf-8"
            )
            (root / "source.md").write_text("候选。\n", encoding="utf-8")
            (root / "source-copy.md").write_text("证据。\n", encoding="utf-8")
            (root / "exact.md").write_text("恢复。\n", encoding="utf-8")
            task = _task(root)
            task.payload["task_type"] = "platform-agent-asset-review"
            task.payload["current_state"] = "asset-review-agent-task"

            sandbox = stage_task(
                task,
                root / "runs",
                runtime="pi-worker",
                run_id="legacy-kind",
                execution_profile={"runtime_id": "pi-worker"},
                prompt_program_config={
                    "mode": "enforced",
                    "fallback": "v2",
                    "enforcement": {
                        "enabled": True,
                        "runtimes": ["pi-worker"],
                    },
                },
            )

            self.assertIn(
                "Prompt Program v3",
                sandbox.prompt_path.read_text(encoding="utf-8"),
            )

    def test_exact_directory_is_one_machine_indexed_on_demand_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text(
                "project:\n  title: 测试\n", encoding="utf-8"
            )
            (root / "source.md").write_text("候选。\n", encoding="utf-8")
            (root / "source-copy.md").write_text("证据。\n", encoding="utf-8")
            canon = root / "canon"
            canon.mkdir()
            (canon / "world_rules.yaml").write_text(
                "rules:\n  - id: bounded\n", encoding="utf-8"
            )
            task = _task(root)
            task.payload["source_paths"] = ["source.md", "source-copy.md", "canon"]
            task.payload["agent_source_paths"] = ["source.md", "source-copy.md", "canon"]
            task.payload["context_exact_on_demand_paths"] = ["canon"]

            sandbox = stage_task(
                task,
                root / "runs",
                runtime="pi-worker",
                run_id="directory-evidence",
                execution_profile={"runtime_id": "pi-worker"},
                prompt_program_config={
                    "mode": "enforced",
                    "fallback": "v2",
                    "enforcement": {"enabled": True, "runtimes": ["pi-worker"]},
                },
            )
            context = json.loads(
                (sandbox.workspace / "TASK_CONTEXT.json").read_text(encoding="utf-8")
            )
            access = context["prompt_access"]

            self.assertEqual(access["exact_on_demand"], ["canon"])
            indexed = [
                item
                for item in access["evidence_index"].values()
                if item["tier"] == "exact_on_demand"
            ]
            self.assertEqual(len(indexed), 1)
            self.assertEqual(indexed[0]["source_ref"], "canon")

    def test_prose_prompt_manifest_is_recovery_evidence_not_inline_drafting_material(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text(
                "project:\n  title: 测试\n", encoding="utf-8"
            )
            (root / "source.md").write_text("候选。\n", encoding="utf-8")
            (root / "source-copy.md").write_text("证据。\n", encoding="utf-8")
            prompt = root / "drafts/candidates/scene_0001-platform-agent.prompt.json"
            prompt.parent.mkdir(parents=True)
            prompt.write_text('{"host":"transport"}', encoding="utf-8")
            task = _task(root)
            task.payload["task_type"] = "platform-agent-prose"
            task.payload["current_state"] = "candidate-generation-provenance"
            task.payload["scene_id"] = "scene_0001"
            task.payload["source_paths"].append(
                "drafts/candidates/scene_0001-platform-agent.prompt.json"
            )
            task.payload["agent_source_paths"] = list(task.payload["source_paths"])

            sandbox = stage_task(
                task,
                root / "runs",
                runtime="pi-worker",
                run_id="prompt-manifest-recovery",
                execution_profile={"runtime_id": "pi-worker"},
                prompt_program_config={
                    "mode": "enforced",
                    "fallback": "v2",
                    "enforcement": {"enabled": True, "runtimes": ["pi-worker"]},
                },
            )
            context = json.loads(
                (sandbox.workspace / "TASK_CONTEXT.json").read_text(encoding="utf-8")
            )
            indexed = context["prompt_access"]["evidence_index"]
            manifest_rows = [
                item
                for item in indexed.values()
                if item["source_ref"].endswith(".prompt.json")
            ]

            self.assertEqual(len(manifest_rows), 1)
            self.assertEqual(manifest_rows[0]["role"], "recovery")
            self.assertEqual(manifest_rows[0]["tier"], "exact_on_demand")


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
