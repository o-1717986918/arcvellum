from pathlib import Path
import hashlib
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.contracts import TASK_SCHEMA, TaskPackage, load_task_package
from literary_engineering_studio.sandbox import SandboxManifest, stage_task
from literary_engineering_studio.preflight.scene_manifest_metadata import canonicalize_scene_revision_manifest
from literary_engineering_studio.task_preflight import COMPLETION_SCHEMA, canonicalize_task_outputs, validate_task_outputs
import literary_engineering_studio_engine.task_registry as task_registry
from literary_engineering_studio_engine.candidate_promotion import _candidate_review_content_match, _human_decision_notes, _unresolved_review_notes
from literary_engineering_studio_engine.review_ci import review_scene_draft
from literary_engineering_studio_engine.literary.style.anti_ai import AIStyleIssue
from literary_engineering_studio_engine.scene_revision import _prompt_manifest
from literary_engineering_studio_engine.literary.scene.promotion.revision_contract import revision_manifest_errors
from literary_engineering_studio_engine.literary.review.resolution import review_semantic_consistency_issues
from literary_engineering_studio_engine.workflow_state import _current_scene_candidate, _static_review_step
from literary_engineering_studio_engine.workflow_state import _review_step


class SceneReviewRevisionLoopTests(unittest.TestCase):
    def test_revision_canonicalizer_removes_only_misclassified_word_budget_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "workspace"
            candidate_rel = "drafts/revisions/scene_0001_revision.md"
            manifest_rel = "drafts/revisions/scene_0001_revision.json"
            candidate = workspace / candidate_rel
            manifest = workspace / manifest_rel
            candidate.parent.mkdir(parents=True)
            candidate.write_text("他先把磨痕当成检修。他认得那个批次。", encoding="utf-8")
            valid_row = {
                "issue": "机械对照直接替读者下判断",
                "source_excerpt": "本该先报故障。可他认得那个批次。",
                "revised_excerpt": "他先把磨痕当成检修。他认得那个批次。",
                "verdict": "resolved",
            }
            manifest.write_text(
                json.dumps(
                    {
                        "anti_evasion_rows": [
                            valid_row,
                            {
                                **valid_row,
                                "issue": "同一对照证据的重复说明",
                            },
                            {
                                "issue": "二节末重复谓语需要删除",
                                "source_excerpt": "停下来又停下来",
                                "revised_excerpt": "停在原处",
                                "verdict": "resolved",
                            },
                            {
                                "issue": "candidate-word-budget-invalid：4027 中文字符净增量不足",
                                "source_excerpt": "正文 4027 中文字符，低于下限",
                                "revised_excerpt": "正文已扩充至目标范围",
                                "verdict": "resolved",
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            task = TaskPackage(
                project_root=workspace,
                task_json_path=workspace / "task.json",
                task_markdown_path=workspace / "task.md",
                payload={
                    "task_id": "scene-development-scene-0001-static-revision",
                    "route": "scene-development",
                    "scene_id": "scene_0001",
                    "current_state": "static-revision",
                    "candidate": candidate_rel,
                    "revision_source": "drafts/scenes/scene_0001.md",
                    "expected_outputs": [candidate_rel, manifest_rel],
                },
            )
            sandbox = SandboxManifest(
                run_id="run-1",
                run_root=workspace.parent,
                workspace=workspace,
                prompt_path=workspace / "prompt.md",
                manifest_path=workspace / "sandbox.json",
                baseline_path=workspace / "baseline.json",
                expected_outputs=task.expected_outputs,
            )

            changes = canonicalize_scene_revision_manifest(
                task,
                sandbox,
                read_object=lambda path: json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None,
                session_identity=lambda _task, role: f"studio:{role}:session",
            )

            normalized = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(normalized["anti_evasion_rows"], [valid_row])
            self.assertTrue(any(item.get("field") == "anti_evasion_rows" for item in changes))

    def test_revision_canonicalizer_normalizes_boolean_transport_and_empty_reason(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "workspace"
            candidate_rel = "drafts/revisions/scene_0001_revision.md"
            manifest_rel = "drafts/revisions/scene_0001_revision.json"
            prompt_rel = "drafts/revisions/scene_0001_revision.prompt.json"
            candidate = workspace / candidate_rel
            manifest = workspace / manifest_rel
            prompt = workspace / prompt_rel
            candidate.parent.mkdir(parents=True)
            candidate.write_text("他把记录放回桌上。", encoding="utf-8")
            manifest.write_text(
                json.dumps(
                    {
                        "anti_evasion_rows": [
                            {
                                "issue": "机械转折被动作链替代",
                                "still_uses_explicit_transition": "no",
                                "suspected_rephrase": "false",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            prompt.write_text(
                json.dumps({"generation_standards": {"anti_evasion_rows_required": False}}),
                encoding="utf-8",
            )
            task = TaskPackage(
                project_root=workspace,
                task_json_path=workspace / "task.json",
                task_markdown_path=workspace / "task.md",
                payload={
                    "task_id": "revision",
                    "current_state": "static-revision",
                    "scene_id": "scene_0001",
                    "candidate": candidate_rel,
                    "expected_outputs": [candidate_rel, manifest_rel, prompt_rel],
                },
            )
            sandbox = SandboxManifest(
                run_id="run-1",
                run_root=workspace.parent,
                workspace=workspace,
                prompt_path=workspace / "prompt.md",
                manifest_path=workspace / "sandbox.json",
                baseline_path=workspace / "baseline.json",
                expected_outputs=task.expected_outputs,
            )

            canonicalize_scene_revision_manifest(
                task,
                sandbox,
                read_object=lambda path: json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None,
                session_identity=lambda _task, role: f"studio:{role}:session",
            )

            normalized = json.loads(manifest.read_text(encoding="utf-8"))
            row = normalized["anti_evasion_rows"][0]
            self.assertIs(row["still_uses_explicit_transition"], False)
            self.assertIs(row["suspected_rephrase"], False)

            normalized["anti_evasion_rows"] = []
            normalized.pop("anti_evasion_not_applicable_reason", None)
            manifest.write_text(json.dumps(normalized), encoding="utf-8")
            canonicalize_scene_revision_manifest(
                task,
                sandbox,
                read_object=lambda path: json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None,
                session_identity=lambda _task, role: f"studio:{role}:session",
            )
            normalized = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertTrue(normalized["anti_evasion_not_applicable_reason"])

    def test_revision_canonicalizer_removes_generic_rows_when_protected_lint_requires_none(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "workspace"
            candidate_rel = "drafts/revisions/scene_0003_revision_03.md"
            manifest_rel = "drafts/revisions/scene_0003_revision_03.json"
            prompt_rel = "drafts/revisions/scene_0003_revision_03.prompt.json"
            source_rel = "drafts/scenes/scene_0003.md"
            source_body = "他核对燃料表，又检查了姿态线路。"
            candidate_body = "他核对燃料表，又检查了姿态线路。接地读数在第三次复测后稳定下来。"
            source = workspace / source_rel
            candidate = workspace / candidate_rel
            manifest = workspace / manifest_rel
            prompt = workspace / prompt_rel
            source.parent.mkdir(parents=True)
            candidate.parent.mkdir(parents=True)
            source.write_text(source_body, encoding="utf-8")
            candidate.write_text(candidate_body, encoding="utf-8")
            manifest.write_text(
                json.dumps(
                    {
                        "revision_actions_applied": ["补足场景的因果与设备伏笔"],
                        "warnings_addressed": [],
                        "style_notes_addressed": [],
                        "style_adherence_addressed": [],
                        "anti_evasion_rows": [
                            {
                                "issue": "候选以动作推进与信息差代替结论复述",
                                "source_excerpt": source_body,
                                "revised_excerpt": candidate_body,
                                "still_uses_explicit_transition": False,
                                "suspected_rephrase": False,
                                "verdict": "resolved",
                            },
                            {
                                "issue": "关键选择段展开因果代价并兑现改道承诺",
                                "source_excerpt": source_body,
                                "revised_excerpt": candidate_body,
                                "still_uses_explicit_transition": False,
                                "suspected_rephrase": False,
                                "verdict": "resolved",
                            },
                            {
                                "issue": "设备故障伏笔通过接地读数与重布线路埋设",
                                "source_excerpt": source_body,
                                "revised_excerpt": candidate_body,
                                "still_uses_explicit_transition": False,
                                "suspected_rephrase": False,
                                "verdict": "resolved",
                            },
                        ],
                        "retained_transition_proofs": [],
                        "evasion_risks_unresolved": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            prompt.write_text(
                json.dumps(
                    {"generation_standards": {"anti_evasion_rows_required": False}},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
            task = TaskPackage(
                project_root=workspace,
                task_json_path=workspace / "task.json",
                task_markdown_path=workspace / "task.md",
                payload={
                    "task_id": "scene-development-scene-0003-target-length-revision",
                    "current_state": "target-length-revision",
                    "scene_id": "scene_0003",
                    "candidate": candidate_rel,
                    "revision_source": source_rel,
                    "candidate_sha256_before_revision": source_sha256,
                    "expected_outputs": [candidate_rel, manifest_rel, prompt_rel],
                },
            )
            sandbox = SandboxManifest(
                run_id="run-1",
                run_root=workspace.parent,
                workspace=workspace,
                prompt_path=workspace / "prompt.md",
                manifest_path=workspace / "sandbox.json",
                baseline_path=workspace / "baseline.json",
                expected_outputs=task.expected_outputs,
            )

            canonicalize_scene_revision_manifest(
                task,
                sandbox,
                read_object=lambda path: json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None,
                session_identity=lambda _task, role: f"studio:{role}:session",
            )

            normalized = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(normalized["anti_evasion_rows"], [])
            self.assertTrue(normalized["anti_evasion_not_applicable_reason"])
            self.assertEqual(
                revision_manifest_errors(
                    normalized,
                    scene_id="scene_0003",
                    source_rel=source_rel,
                    source_sha256=source_sha256,
                    source_body=source_body,
                    candidate_rel=candidate_rel,
                    candidate_sha256=hashlib.sha256(candidate.read_bytes()).hexdigest(),
                    candidate_body=candidate_body,
                    anti_evasion_rows_required=False,
                ),
                [],
            )

            normalized["anti_evasion_rows"] = [
                {
                    "issue": "机械转折可能只是换皮成动作总结",
                    "source_excerpt": source_body,
                    "revised_excerpt": candidate_body,
                    "still_uses_explicit_transition": False,
                    "suspected_rephrase": False,
                    "verdict": "resolved",
                }
            ]
            normalized.pop("anti_evasion_not_applicable_reason", None)
            manifest.write_text(json.dumps(normalized, ensure_ascii=False), encoding="utf-8")
            canonicalize_scene_revision_manifest(
                task,
                sandbox,
                read_object=lambda path: json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None,
                session_identity=lambda _task, role: f"studio:{role}:session",
            )
            explicit = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(len(explicit["anti_evasion_rows"]), 1)
            self.assertIn(
                "anti_evasion_rows[0].critical_objection is missing",
                revision_manifest_errors(
                    explicit,
                    scene_id="scene_0003",
                    source_rel=source_rel,
                    source_sha256=source_sha256,
                    source_body=source_body,
                    candidate_rel=candidate_rel,
                    candidate_sha256=hashlib.sha256(candidate.read_bytes()).hexdigest(),
                    candidate_body=candidate_body,
                    anti_evasion_rows_required=False,
                ),
            )

    def test_static_review_keeps_below_threshold_style_findings_nonblocking(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            draft = root / "drafts" / "scenes" / "scene_0001.md"
            draft.parent.mkdir(parents=True)
            body = "他沿着舱壁检查线路。" * 30
            draft.write_text(
                "## 正文草稿\n\n"
                + body
                + "\n\n## 状态变化\n\n"
                "Canon、人物档案和时间线是硬约束。\n\n"
                "风格约束已挂载。\n\n"
                "### 新增事实候选\n- 无。\n"
                "### 人物状态变化\n- 无。\n"
                "### 伏笔变化\n- 无。\n"
                "### 需要人工确认\n- 无。\n",
                encoding="utf-8",
            )
            note = AIStyleIssue("dash-prohibited-in-plain-narration", "low", "低于阈值。")
            with patch(
                "literary_engineering_studio_engine.literary.review.ci.lint_ai_style",
                return_value=[note],
            ), patch(
                "literary_engineering_studio_engine.literary.review.ci.is_style_lint_blocking",
                return_value=False,
            ), patch(
                "literary_engineering_studio_engine.literary.review.ci.lint_punctuation",
                return_value=[],
            ):
                result = review_scene_draft(root, draft)

            self.assertEqual(result.conclusion, "pass")
            report = result.report_path.read_text(encoding="utf-8")
            self.assertIn("结果：notes（不阻塞）", report)

    def test_nonpass_static_review_routes_to_revision_and_stale_review_reopens(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            draft = root / "drafts" / "scenes" / "scene_0001.md"
            draft.parent.mkdir(parents=True)
            draft.write_text("## 正文草稿\n\n太短。\n", encoding="utf-8")
            result = review_scene_draft(root, draft)
            step = _static_review_step(root, "scene_0001")
            self.assertNotEqual(result.conclusion, "pass")
            self.assertEqual(step["key"], "static-revision")

            draft.write_text("## 正文草稿\n\n已经改变的正文。\n", encoding="utf-8")
            stale = _static_review_step(root, "scene_0001")
            self.assertEqual(stale["key"], "static-review")
            self.assertEqual(stale["status"], "stale")

    def test_newer_revision_candidate_supersedes_prior_promotion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = root / "drafts" / "candidates" / "scene_0001-platform-agent.md"
            original.parent.mkdir(parents=True)
            original.write_text("旧候选。\n", encoding="utf-8")
            promotion = root / "drafts" / "promotions" / "scene_0001_promotion.json"
            promotion.parent.mkdir(parents=True)
            promotion.write_text(
                json.dumps({"candidate": "drafts/candidates/scene_0001-platform-agent.md"}), encoding="utf-8"
            )
            revision = root / "drafts" / "revisions" / "scene_0001_revision.md"
            revision.parent.mkdir(parents=True)
            revision.write_text("新修订候选。\n", encoding="utf-8")
            future = promotion.stat().st_mtime_ns + 10_000_000
            os.utime(revision, ns=(future, future))

            self.assertEqual(_current_scene_candidate(root, "scene_0001"), revision)

    def test_scene_review_is_bound_to_exact_candidate_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "scene_0001.md"
            candidate.write_text("第一版正文。\n", encoding="utf-8")
            digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            self.assertTrue(_candidate_review_content_match({"candidate_sha256": digest}, candidate))
            candidate.write_text("第二版正文。\n", encoding="utf-8")
            self.assertFalse(_candidate_review_content_match({"candidate_sha256": digest}, candidate))

    def test_workflow_routes_semantic_failure_to_revision_but_infrastructure_failure_to_review(self):
        candidate = Path("C:/project/drafts/candidates/scene_0001-platform-agent.md")
        with patch("literary_engineering_studio_engine.workflow_state_scene.candidate_review_gate", return_value={"status": "style_lint_failed", "review": "reviews/agent/scene_0001_scene_review.json", "message": "lint"}):
            revision = _review_step(Path("C:/project"), "scene_0001", candidate)
        with patch("literary_engineering_studio_engine.workflow_state_scene.candidate_review_gate", return_value={"status": "task_incomplete", "review": "reviews/agent/scene_0001_scene_review.json", "message": "marker"}):
            review = _review_step(Path("C:/project"), "scene_0001", candidate)

        self.assertEqual(revision["key"], "candidate-revision")
        self.assertEqual(review["key"], "candidate-review")

    def test_review_artifact_integrity_failure_routes_to_review_not_prose_revision(self):
        candidate = Path("C:/project/drafts/revisions/scene_0001_revision.md")
        with patch(
            "literary_engineering_studio_engine.workflow_state_scene.candidate_review_gate",
            return_value={
                "status": "revision_integrity_review_failed",
                "review": "reviews/agent/scene_0001_scene_review.json",
                "message": "anti_evasion_checked must be true",
            },
        ):
            step = _review_step(Path("C:/project"), "scene_0001", candidate)

        self.assertEqual(step["key"], "candidate-review")
        self.assertIn("agent-review-scene", step["next_action"])

    def test_cross_asset_review_finding_stops_for_exact_candidate_decision(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "drafts" / "candidates" / "scene_0001-platform-agent.md"
            candidate.parent.mkdir(parents=True)
            candidate.write_text("正文。\n", encoding="utf-8")
            digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            gate = {
                "status": "human_decision_required",
                "review": "reviews/agent/scene_0001_scene_review.json",
                "message": "formal age conflict",
                "candidate_sha256": digest,
            }
            with patch("literary_engineering_studio_engine.workflow_state_scene.candidate_review_gate", return_value=gate):
                pending = _review_step(root, "scene_0001", candidate)
            self.assertEqual(pending["key"], "candidate-human-decision")
            self.assertEqual(pending["status"], "human_required")

            choices = root / "workflow" / "human_choices"
            choices.mkdir(parents=True)
            (choices / "index.jsonl").write_text(
                json.dumps(
                    {
                        "decision_type": "cross_asset_alignment",
                        "selected": "align_prose_to_formal_asset",
                        "target": {"scene_id": "scene_0001", "candidate_sha256": digest},
                    }
                ) + "\n",
                encoding="utf-8",
            )
            with patch("literary_engineering_studio_engine.workflow_state_scene.candidate_review_gate", return_value=gate):
                routed = _review_step(root, "scene_0001", candidate)
            self.assertEqual(routed["key"], "candidate-revision")
            self.assertEqual(routed["status"], "needs_revision")

    def test_human_review_resolution_is_not_treated_as_normal_style_note(self):
        notes = _human_decision_notes(
            {
                "warnings": [
                    {"id": "W-001", "description": "formal age conflict", "resolution": "needs_human_review", "blocks_pass": True},
                    {"id": "W-002", "description": "ordinary warning", "resolution": "external_dependency", "blocks_pass": False},
                ]
            }
        )
        self.assertEqual(notes, ["W-001: formal age conflict"])

    def test_passing_style_evidence_does_not_reopen_candidate_revision(self):
        notes = _unresolved_review_notes(
            {
                "conclusion": "pass",
                "blocking_issues": [],
                "warnings": [{"severity": "low", "message": "低于阈值，不作为阻塞问题。", "blocks_pass": False}],
                "revision_actions": [],
                "style_notes": ["保留一处明喻，承担场景核心意象功能，密度在阈值内。"],
                "style_adherence": {"status": "pass", "deviations": [], "revision_actions": []},
                "canon_writeback": {"status": "not_required", "canon_change": False, "no_canon_change_reason": "本场不新增正式世界规则。"},
                "revision_integrity": {"status": "not_applicable", "anti_evasion_checked": True, "evasion_risks_unresolved": []},
            }
        )
        self.assertEqual(notes, [])

    def test_unclassified_warning_remains_a_revision_gate(self):
        notes = _unresolved_review_notes(
            {
                "conclusion": "pass",
                "blocking_issues": [],
                "warnings": [{"severity": "low", "message": "这一处可能需要再看。"}],
                "revision_actions": [],
                "style_adherence": {"status": "pass", "deviations": [], "revision_actions": []},
                "canon_writeback": {"status": "not_required", "canon_change": False, "no_canon_change_reason": "本场不新增正式世界规则。"},
                "revision_integrity": {"status": "not_applicable", "anti_evasion_checked": True, "evasion_risks_unresolved": []},
            }
        )
        self.assertEqual(notes, ["warnings"])

    def test_below_threshold_observations_cannot_manufacture_pass_with_notes(self):
        payload = {
            "conclusion": "pass_with_notes",
            "blocking_issues": [],
            "warnings": [
                {
                    "severity": "low",
                    "message": "密度低于阈值，仅作诊断记录。",
                    "blocks_pass": False,
                }
            ],
            "revision_actions": [],
            "style_notes": [{"severity": "neutral", "message": "保留观察。"}],
            "style_adherence": {
                "status": "pass",
                "deviations": [
                    {
                        "severity": "low",
                        "blocks_pass": False,
                        "detail": "低于阈值。",
                    }
                ],
                "revision_actions": [],
            },
            "revision_integrity": {
                "status": "not_applicable",
                "anti_evasion_checked": True,
                "evasion_risks_unresolved": [],
            },
        }

        issues = review_semantic_consistency_issues(payload)
        self.assertEqual(len(issues), 1)
        self.assertIn("no actionable finding", issues[0])

    def test_revision_action_cannot_claim_it_does_not_block_pass(self):
        issues = review_semantic_consistency_issues(
            {
                "conclusion": "pass_with_notes",
                "blocking_issues": [],
                "warnings": [],
                "revision_actions": [
                    {"id": "RA1", "action": "optional polish", "blocks_pass": False}
                ],
                "style_adherence": {"status": "pass", "deviations": []},
                "revision_integrity": {
                    "status": "not_applicable",
                    "anti_evasion_checked": True,
                    "evasion_risks_unresolved": [],
                },
            }
        )

        self.assertTrue(any("blocks_pass=false" in issue for issue in issues))

    def test_review_integrity_requires_explicit_anti_evasion_check(self):
        issues = review_semantic_consistency_issues(
            {
                "conclusion": "pass",
                "blocking_issues": [],
                "warnings": [],
                "revision_actions": [],
                "style_adherence": {"status": "pass", "deviations": []},
                "revision_integrity": {
                    "status": "pass",
                    "source_sha256_match": True,
                },
            }
        )

        self.assertIn("revision_integrity.anti_evasion_checked must be true", issues)

    def test_non_pass_scene_review_is_recordable_for_revision_routing(self):
        with patch("literary_engineering_studio_engine.scene_route_gates.candidate_review_gate", return_value={"status": "notes_unresolved", "message": "revise"}):
            errors = task_registry._candidate_review_gate_errors(Path("C:/project"), {"scene_id": "scene_0001"}, Path("candidate.md"), require_pass=False)
            promotion_errors = task_registry._candidate_review_gate_errors(Path("C:/project"), {"scene_id": "scene_0001"}, Path("candidate.md"), require_pass=True)

        self.assertEqual(errors, [])
        self.assertTrue(promotion_errors)

    def test_revision_preflight_rejects_unchanged_prose_and_accepts_real_revision(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            source_rel = "drafts/candidates/scene_0001-platform-agent.md"
            candidate_rel = "drafts/revisions/scene_0001_revision_02.md"
            source = project / source_rel
            source.parent.mkdir(parents=True)
            source.write_text("## 正文候选\n\n她停在门口。\n", encoding="utf-8")
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            expected = [
                candidate_rel,
                "drafts/revisions/scene_0001_revision_02_report.md",
                "drafts/revisions/scene_0001_revision_02.json",
                "drafts/revisions/scene_0001_revision_02.prompt.json",
                "drafts/revisions/scene_0001_revision_02.agent_tasks.md",
                "drafts/revisions/scene_0001_revision_02.agent_completion.json",
            ]
            task_dir = project / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            task_md = task_dir / "revision.agent_tasks.md"
            task_md.write_text("# revision\n", encoding="utf-8")
            task_json = task_dir / "revision.json"
            task_json.write_text(
                json.dumps(
                    {
                        "schema": TASK_SCHEMA,
                        "task_id": "scene-revision",
                        "route": "scene-development",
                        "scene_id": "scene_0001",
                        "scene": "scenes/scene_0001.yaml",
                        "current_state": "candidate-revision",
                        "task_type": "platform-agent-revision",
                        "candidate": candidate_rel,
                        "revision_source": source_rel,
                        "candidate_sha256_before_revision": before,
                        "task_markdown": "workflow/tasks/revision.agent_tasks.md",
                        "required_reading": [],
                        "source_paths": [source_rel],
                        "expected_outputs": expected,
                        "validation_gates": ["revision candidate differs"],
                        "forbidden_shortcuts": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            task = load_task_package(project, task_json)
            sandbox = stage_task(task, root / "runs", runtime="opencode")
            for relative in expected:
                path = sandbox.workspace / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                if relative == candidate_rel:
                    path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
                elif relative == "drafts/revisions/scene_0001_revision_02.json":
                    path.write_text(json.dumps({
                        "revision_actions_applied": ["修正动作"],
                        "warnings_addressed": [],
                        "style_notes_addressed": [],
                        "style_adherence_addressed": [],
                        "anti_evasion_rows": [],
                        "anti_evasion_not_applicable_reason": "源正文未检出机械对照或换皮转折。",
                        "retained_transition_proofs": [],
                        "evasion_risks_unresolved": [],
                        "new_character_register": {
                            "schema": "literary-engineering-workbench/new-character-register/v0.1",
                            "status": "none",
                            "introduced": [],
                            "ephemeral_waivers": [],
                            "blocking_issues": [],
                        },
                        "waivers": [],
                    }, ensure_ascii=False), encoding="utf-8")
                elif relative.endswith("agent_completion.json"):
                    path.write_text(json.dumps({"schema": COMPLETION_SCHEMA, "source_task": "drafts/revisions/scene_0001_revision_02.agent_tasks.md", "status": "complete", "handled_by": "main-agent", "completed_at": "2026-07-21T00:00:00Z", "expected_artifacts_checked": True, "notes": []}, ensure_ascii=False), encoding="utf-8")
                elif relative.endswith(".json"):
                    path.write_text("{}\n", encoding="utf-8")
                else:
                    path.write_text("# artifact\n", encoding="utf-8")

            rejected = validate_task_outputs(task, sandbox)
            self.assertFalse(rejected.passed)
            self.assertTrue(any(issue.code == "scene-revision-invalid" for issue in rejected.issues))

            revised = sandbox.workspace / candidate_rel
            revised.write_text("## 修订正文候选\n\n她没有停。门已经从里面打开。\n", encoding="utf-8")
            changes = canonicalize_task_outputs(task, sandbox)
            self.assertTrue(any(change.get("field") == "candidate_sha256" for change in changes))
            revision_manifest = sandbox.workspace / "drafts/revisions/scene_0001_revision_02.json"
            revision_payload = json.loads(revision_manifest.read_text(encoding="utf-8"))
            self.assertEqual(revision_payload["schema"], "literary-engineering-workbench/scene-revision/v0.1")
            self.assertEqual(revision_payload["source_candidate_sha256"], before)
            self.assertEqual(revision_payload["candidate_sha256"], hashlib.sha256(revised.read_bytes()).hexdigest())
            self.assertIs(revision_payload["anti_evasion_protocol_applied"], True)
            self.assertIs(revision_payload["ready_for_review"], False)
            accepted = validate_task_outputs(task, sandbox)
            self.assertTrue(accepted.passed, accepted.as_dict())

    def test_revision_manifest_requires_bound_anti_evasion_rows_for_contrast_source(self):
        source_body = "这不是警告，是最后通牒。"
        candidate_body = "他把日志推到桌上。对方终于抬头。"
        base = {
            "schema": "literary-engineering-workbench/scene-revision/v0.1",
            "scene_id": "scene_0001",
            "source_candidate": "drafts/candidates/scene_0001.md",
            "source_candidate_sha256": "source-digest",
            "candidate": "drafts/revisions/scene_0001_revision.md",
            "candidate_sha256": "candidate-digest",
            "revision_actions_applied": ["把显式对照改为动作和事实顺序"],
            "anti_evasion_protocol_applied": True,
            "evasion_risks_unresolved": [],
            "ready_for_review": False,
        }
        kwargs = {
            "scene_id": "scene_0001",
            "source_rel": "drafts/candidates/scene_0001.md",
            "source_sha256": "source-digest",
            "source_body": source_body,
            "candidate_rel": "drafts/revisions/scene_0001_revision.md",
            "candidate_sha256": "candidate-digest",
            "candidate_body": candidate_body,
            "anti_evasion_rows_required": True,
        }

        missing = revision_manifest_errors(base, **kwargs)
        self.assertIn("revision manifest requires anti_evasion_rows for detected contrast/evasion risks", missing)

        base["anti_evasion_rows"] = [
            {
                "source_excerpt": source_body,
                "issue": "机械对照直接替读者下判断",
                "revised_excerpt": candidate_body,
                "still_uses_explicit_transition": False,
                "suspected_rephrase": False,
                "critical_objection": "动作是否真正传达威胁，而非仅删除句式？当前物证和对方反应共同承担该功能。",
                "verdict": "resolved",
            }
        ]
        self.assertEqual(revision_manifest_errors(base, **kwargs), [])

    def test_revision_prompt_and_manifest_preserve_reader_and_rhythm_contracts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text("scene_id: scene_0001\nchapter_id: chapter_0001\n", encoding="utf-8")
            draft = root / "drafts" / "candidates" / "scene_0001-platform-agent.md"
            draft.parent.mkdir(parents=True)
            draft.write_text("## 正文候选\n\n她推开了门。\n", encoding="utf-8")
            context = root / "memory" / "context_packets" / "scene_0001.md"
            context.parent.mkdir(parents=True)
            context.write_text("# context\n", encoding="utf-8")
            trace = context.with_suffix(".trace.json")
            trace.write_text("{}\n", encoding="utf-8")
            review = root / "reviews" / "agent" / "scene_0001_scene_review.json"
            review.parent.mkdir(parents=True)
            review.write_text(json.dumps({"conclusion": "pass_with_notes"}), encoding="utf-8")
            candidate = root / "drafts" / "revisions" / "scene_0001_revision.md"
            report = candidate.with_name("scene_0001_revision_report.md")
            manifest = candidate.with_suffix(".json")

            prompt = _prompt_manifest(
                root, "scene_0001", scene, draft, context, trace, review,
                [scene, draft, context, trace, review], candidate, report, manifest,
            )
            standards = prompt["generation_standards"]
            self.assertEqual(prompt["source_candidate_sha256"], hashlib.sha256(draft.read_bytes()).hexdigest())
            self.assertIn("reader_experience_contract", standards)
            self.assertIs(standards["anti_evasion_rows_required"], False)
            self.assertIn("narrative_rhythm_contract", standards)
            self.assertIn(standards["reader_experience_contract"]["status"], {"not_required", "pass", "blocked", "incomplete"})
            self.assertIn(standards["narrative_rhythm_contract"]["status"], {"defaulted", "pass", "incomplete"})


if __name__ == "__main__":
    unittest.main()
