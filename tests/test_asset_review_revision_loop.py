from pathlib import Path
import hashlib
import json
import tempfile
import unittest

from literary_engineering_studio.contracts import TASK_SCHEMA, load_task_package
from literary_engineering_studio.sandbox import stage_task
from literary_engineering_studio.task_preflight import COMPLETION_SCHEMA, validate_task_outputs
from literary_engineering_studio.preflight.canonicalization import canonicalize_task_outputs
from literary_engineering_studio_engine.agent_tasks import write_agent_completion_marker
from literary_engineering_studio_engine.approval import record_workflow_approval
from literary_engineering_studio_engine.asset_context import compact_asset_context_relpaths
import literary_engineering_studio_engine.asset_route as asset_route
from literary_engineering_studio_engine.asset_workshop import _dry_payload, promote_candidate_asset
from literary_engineering_studio_engine.workflow_state import _asset_state


def _candidate_payload() -> dict[str, object]:
    return {
        "schema": "literary-engineering-workbench/character-profile-candidate/v1",
        "candidate_id": "protagonist",
        "character_id": "protagonist",
        "asset_type": "character",
        "name": "林昭",
        "role": "主角",
        "identity": {"occupation": "档案修复员"},
        "background_story": {"hidden_cause": "曾因迟疑失去同伴"},
        "bdi": {"belief": "记录可以对抗遗忘", "desire": "找回真相", "intention": "核对异常档案"},
        "psychology": {"fear": "再次迟疑", "moral_line": "不伪造证据"},
        "relationships": [],
        "speech_style": {"register": "克制"},
        "arc": {"start": "回避承担", "direction": "主动承担"},
        "state": {"location": "档案馆"},
        "risks": ["背景因果仍需在场景中间接验证"],
        "source_paths": ["project.yaml"],
        "promotion_notes": "仅作为候选，等待独立审查与批准。",
    }


def _review_payload(status: str = "revise_required") -> dict[str, object]:
    return {
        "schema": "literary-engineering-workbench/candidate-asset-review/v0.1",
        "candidate": "characters/candidates/protagonist.json",
        "candidate_id": "protagonist",
        "asset_type": "character",
        "status": status,
        "blocking_issues": [],
        "warnings": [],
        "revision_actions": ["把主角的道德边界改写为可观察的选择约束"] if status != "pass" else [],
        "promotion_risks": [],
        "reviewed_at": "2026-07-21T00:00:00Z",
    }


class AssetReviewRevisionLoopTests(unittest.TestCase):
    def test_promotion_uses_candidate_path_as_the_canonical_machine_id(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "characters" / "candidates" / "protagonist-foundation.json"
            candidate.parent.mkdir(parents=True)
            payload = _dry_payload("character", "protagonist-foundation", root, "", "protagonist", None)
            payload["candidate_id"] = "protagonist-foundation-v1"
            payload["asset_type"] = "character_profile"
            candidate.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            review_dir = root / "reviews" / "assets"
            review_dir.mkdir(parents=True)
            review_task = review_dir / "protagonist-foundation_review.agent_tasks.md"
            review_task.write_text("# review\n", encoding="utf-8")
            review = _review_payload("pass")
            review.update(
                {
                    "candidate": "characters/candidates/protagonist-foundation.json",
                    "candidate_id": "protagonist-foundation",
                    "candidate_sha256": digest,
                }
            )
            (review_dir / "protagonist-foundation_review.json").write_text(
                json.dumps(review, ensure_ascii=False), encoding="utf-8"
            )
            (review_dir / "protagonist-foundation_review.md").write_text("# 审查通过\n", encoding="utf-8")
            write_agent_completion_marker(review_task, root=root, handled_by="reviewer")
            record_workflow_approval(root, "protagonist-foundation", "approve", subject_sha256=digest)

            result = promote_candidate_asset(root, candidate, group="character", approval_run_id="protagonist-foundation")
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

            self.assertEqual(result.manifest_path.name, "protagonist-foundation_promotion.json")
            self.assertEqual(manifest["candidate_id"], "protagonist-foundation")
            self.assertEqual(manifest["approval_run_id"], "protagonist-foundation")

    def test_approval_revise_routes_to_digest_bound_revision_task(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "characters" / "candidates" / "protagonist.json"
            candidate.parent.mkdir(parents=True)
            candidate.write_text(json.dumps(_candidate_payload(), ensure_ascii=False), encoding="utf-8")
            candidate.with_suffix(".md").write_text("# 候选人物\n", encoding="utf-8")
            creation_task = candidate.with_suffix(".agent_tasks.md")
            creation_task.write_text("# create\n", encoding="utf-8")
            write_agent_completion_marker(creation_task, root=root, handled_by="creator")
            review_dir = root / "reviews" / "assets"
            review_dir.mkdir(parents=True)
            review_task = review_dir / "protagonist_review.agent_tasks.md"
            review_task.write_text("# review\n", encoding="utf-8")
            (review_dir / "protagonist_review.json").write_text(
                json.dumps(_review_payload("pass"), ensure_ascii=False), encoding="utf-8"
            )
            (review_dir / "protagonist_review.md").write_text("# 审查通过\n", encoding="utf-8")
            write_agent_completion_marker(review_task, root=root, handled_by="reviewer")
            digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            record_workflow_approval(
                root,
                "protagonist",
                "revise",
                actor="creative-steward",
                notes="补强人物选择与世界规则之间的因果锚点。",
                subject_sha256=digest,
            )

            state = _asset_state(root, {"candidate": candidate, "asset_type": "character", "creation_task": creation_task})
            self.assertEqual(state["current_step"], "asset-approval-revision")
            payload = asset_route.build_task_payload(root, "character-and-world-assets", state)
            self.assertEqual(payload["current_state"], "asset-approval-revision")
            self.assertEqual(payload["candidate_sha256_before_revision"], digest)
            self.assertIn("workflow/approvals/index.jsonl", payload["source_paths"])
            self.assertIn("reviews/assets/protagonist_review.json", payload["core_managed_outputs"])
            constraints = "\n".join(payload["hard_constraints"])
            self.assertIn("Studio Worker", constraints)
            self.assertNotIn("再重写 review JSON", constraints)

    def test_asset_context_excludes_large_workflow_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative, content in (
                ("project.yaml", "title: 潮线\n"),
                ("canon/world_rules.yaml", "rules: []\n"),
                ("characters/_template.yaml", "name: ''\n"),
                ("plot/outline.md", "# 大纲\n"),
                ("plot/candidates/outlines/word_budget_expansion.md", "# 扩展大纲\n"),
                ("plot/candidates/scenes/word_budget_scene_inventory.md", "不应进入资产上下文\n"),
                ("plot/word_budget/word_budget.json", "{\"huge\": true}\n"),
                ("plot/word_budget/word_budget.md", "# 预算摘要\n"),
            ):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            paths = compact_asset_context_relpaths(root)

            self.assertIn("project.yaml", paths)
            self.assertNotIn("plot/candidates/outlines/word_budget_expansion.md", paths)
            self.assertNotIn("plot/candidates/scenes/word_budget_scene_inventory.md", paths)
            self.assertNotIn("plot/word_budget/word_budget.json", paths)
            self.assertNotIn("canon", paths)
            self.assertNotIn("plot", paths)

    def test_review_preflight_rejects_cross_task_revision_action(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            task_dir = project / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            candidate_rel = "characters/candidates/protagonist.json"
            review_rel = "reviews/assets/protagonist_review.json"
            review_report_rel = "reviews/assets/protagonist_review.md"
            completion_rel = "reviews/assets/protagonist_review.agent_completion.json"
            task_markdown = task_dir / "review.agent_tasks.md"
            task_markdown.write_text("# review\n", encoding="utf-8")
            task_json = task_dir / "review.json"
            task_json.write_text(
                json.dumps(
                    {
                        "schema": TASK_SCHEMA,
                        "task_id": "review",
                        "route": "character-and-world-assets",
                        "current_state": "asset-review-agent-task",
                        "task_type": "platform-agent-asset-review",
                        "candidate": candidate_rel,
                        "task_markdown": "workflow/tasks/review.agent_tasks.md",
                        "required_reading": [],
                        "source_paths": [],
                        "expected_outputs": [review_rel, review_report_rel, completion_rel],
                        "validation_gates": ["review status is recorded"],
                        "forbidden_shortcuts": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            task = load_task_package(project, task_json)
            sandbox = stage_task(task, root / "runs", runtime="opencode")
            review = _review_payload()
            review["revision_actions"] = [
                {
                    "target": "characters/candidates/secondary.json",
                    "action": "创建另一个人物候选",
                }
            ]
            (sandbox.workspace / review_rel).parent.mkdir(parents=True, exist_ok=True)
            (sandbox.workspace / review_rel).write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
            (sandbox.workspace / review_report_rel).write_text("# 审查\n", encoding="utf-8")
            (sandbox.workspace / completion_rel).write_text(
                json.dumps(
                    {
                        "schema": COMPLETION_SCHEMA,
                        "source_task": "reviews/assets/protagonist_review.agent_tasks.md",
                        "status": "complete",
                        "handled_by": "reviewer",
                        "completed_at": "2026-07-21T00:00:00Z",
                        "expected_artifacts_checked": True,
                        "notes": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = validate_task_outputs(task, sandbox)

            self.assertFalse(result.passed)
            self.assertTrue(any("跨任务目标" in issue.message for issue in result.issues))

    def test_non_pass_review_is_recordable_but_not_approvable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "characters" / "candidates" / "protagonist.json"
            candidate.parent.mkdir(parents=True)
            candidate.write_text(json.dumps(_candidate_payload(), ensure_ascii=False), encoding="utf-8")
            review_dir = root / "reviews" / "assets"
            review_dir.mkdir(parents=True)
            task_path = review_dir / "protagonist_review.agent_tasks.md"
            task_path.write_text("# review\n", encoding="utf-8")
            review_payload = _review_payload()
            review_payload["candidate_sha256"] = hashlib.sha256(candidate.read_bytes()).hexdigest()
            (review_dir / "protagonist_review.json").write_text(
                json.dumps(review_payload, ensure_ascii=False), encoding="utf-8"
            )
            (review_dir / "protagonist_review.md").write_text("# 审查\n\n需要修订。\n", encoding="utf-8")
            write_agent_completion_marker(task_path, root=root, handled_by="reviewer")

            recorded = asset_route._asset_review_gate_errors(root, "protagonist", require_pass=False)
            approval = asset_route._asset_review_gate_errors(root, "protagonist", require_pass=True)

            self.assertEqual(recorded, [])
            self.assertTrue(any("status must be pass" in item for item in approval))
            self.assertTrue(any("revision_actions" in item for item in approval))

    def test_revision_preflight_requires_recheck_instead_of_self_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            task_dir = project / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            candidate_rel = "characters/candidates/protagonist.json"
            candidate_report_rel = "characters/candidates/protagonist.md"
            review_rel = "reviews/assets/protagonist_review.json"
            review_report_rel = "reviews/assets/protagonist_review.md"
            completion_rel = "reviews/assets/protagonist_review.agent_completion.json"
            for relative, content in (
                (candidate_rel, json.dumps(_candidate_payload(), ensure_ascii=False)),
                (candidate_report_rel, "# 候选人物\n"),
                (review_rel, json.dumps(_review_payload("pass"), ensure_ascii=False)),
                (review_report_rel, "# 修订报告\n"),
            ):
                path = project / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            completion = project / completion_rel
            completion.write_text(
                json.dumps(
                    {
                        "schema": COMPLETION_SCHEMA,
                        "source_task": "reviews/assets/protagonist_review.agent_tasks.md",
                        "status": "complete",
                        "handled_by": "revision-agent",
                        "completed_at": "2026-07-21T00:00:00Z",
                        "expected_artifacts_checked": True,
                        "notes": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            task_json = task_dir / "revision.json"
            task_markdown = task_dir / "revision.agent_tasks.md"
            task_markdown.write_text("# revision\n", encoding="utf-8")
            task_json.write_text(
                json.dumps(
                    {
                        "schema": TASK_SCHEMA,
                        "task_id": "revision",
                        "route": "character-and-world-assets",
                        "current_state": "asset-review-pass",
                        "task_type": "platform-agent-revision",
                        "asset_type": "character",
                        "candidate": candidate_rel,
                        "task_markdown": "workflow/tasks/revision.agent_tasks.md",
                        "required_reading": [],
                        "source_paths": [],
                        "expected_outputs": [candidate_rel, candidate_report_rel, review_report_rel, review_rel, completion_rel],
                        "validation_gates": ["candidate schema validates", "review status is recheck_required"],
                        "forbidden_shortcuts": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            task = load_task_package(project, task_json)
            sandbox = stage_task(task, root / "runs", runtime="opencode")

            rejected = validate_task_outputs(task, sandbox)
            self.assertFalse(rejected.passed)
            self.assertIn("invalid-completion-evidence", {item.code for item in rejected.issues})
            self.assertIn("asset-review-invalid", {item.code for item in rejected.issues})

            revised_review = _review_payload("revise_required")
            revised_review.update(
                {
                    "status": "recheck_required",
                    "candidate_sha256": hashlib.sha256(
                        (sandbox.workspace / candidate_rel).read_bytes()
                    ).hexdigest(),
                    "applied_revision_actions": [
                        {"action": "明确道德边界", "evidence": "psychology.moral_line 已改为不伪造证据"}
                    ],
                    "revision_round": 1,
                    "revised_at": "2026-07-21T00:10:00Z",
                }
            )
            (sandbox.workspace / review_rel).write_text(json.dumps(revised_review, ensure_ascii=False), encoding="utf-8")
            (sandbox.workspace / completion_rel).write_text(
                json.dumps(
                    {
                        "schema": COMPLETION_SCHEMA,
                        "source_task": "reviews/assets/protagonist_review.agent_tasks.md",
                        "status": "recheck_required",
                        "handled_by": "revision-agent",
                        "completed_at": "2026-07-21T00:10:00Z",
                        "expected_artifacts_checked": False,
                        "notes": ["等待独立复审"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            accepted = validate_task_outputs(task, sandbox)
            self.assertTrue(accepted.passed, accepted.as_dict())

    def test_approval_revision_generates_lifecycle_evidence_after_candidate_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            task_dir = project / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            candidate_rel = "characters/candidates/protagonist.json"
            candidate_report_rel = "characters/candidates/protagonist.md"
            review_rel = "reviews/assets/protagonist_review.json"
            review_report_rel = "reviews/assets/protagonist_review.md"
            completion_rel = "reviews/assets/protagonist_review.agent_completion.json"
            candidate = _candidate_payload()
            for relative, content in (
                (candidate_rel, json.dumps(candidate, ensure_ascii=False)),
                (candidate_report_rel, "# 候选人物\n"),
                (review_rel, json.dumps(_review_payload("pass"), ensure_ascii=False)),
                (review_report_rel, "# 审查报告\n"),
                ("workflow/approvals/index.jsonl", json.dumps({"run_id": "protagonist", "decision": "revise", "notes": "补足角色与正式档案的映射说明。"}, ensure_ascii=False) + "\n"),
            ):
                path = project / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            before = hashlib.sha256((project / candidate_rel).read_bytes()).hexdigest()
            task_json = task_dir / "approval-revision.json"
            task_markdown = task_dir / "approval-revision.agent_tasks.md"
            task_markdown.write_text("# approval revision\n", encoding="utf-8")
            task_json.write_text(
                json.dumps(
                    {
                        "schema": TASK_SCHEMA,
                        "task_id": "approval-revision",
                        "route": "character-and-world-assets",
                        "current_state": "asset-approval-revision",
                        "task_type": "platform-agent-revision",
                        "asset_type": "character",
                        "candidate": candidate_rel,
                        "candidate_sha256_before_revision": before,
                        "task_markdown": "workflow/tasks/approval-revision.agent_tasks.md",
                        "required_reading": [],
                        "source_paths": ["workflow/approvals/index.jsonl"],
                        "expected_outputs": [candidate_rel, candidate_report_rel, review_report_rel, review_rel, completion_rel],
                        "core_managed_outputs": [review_report_rel, review_rel, completion_rel],
                        "validation_gates": ["candidate schema validates", "review status is recheck_required"],
                        "forbidden_shortcuts": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            task = load_task_package(project, task_json)
            sandbox = stage_task(task, root / "runs", runtime="opencode")
            revised = json.loads((sandbox.workspace / candidate_rel).read_text(encoding="utf-8"))
            revised["promotion_notes"] = "候选角色将以 dual-ID 映射连接至正式主角档案。"
            (sandbox.workspace / candidate_rel).write_text(json.dumps(revised, ensure_ascii=False), encoding="utf-8")
            canonicalize_task_outputs(task, sandbox)

            result = validate_task_outputs(task, sandbox)

            self.assertTrue(result.passed, result.as_dict())
            review = json.loads((sandbox.workspace / review_rel).read_text(encoding="utf-8"))
            self.assertEqual(review["status"], "recheck_required")
            self.assertEqual(review["revision_round"], 1)
            self.assertTrue(review["applied_revision_actions"])
            self.assertIn("Studio Revision Reset", (sandbox.workspace / review_report_rel).read_text(encoding="utf-8"))

    def test_revision_gate_reopens_review_and_requires_candidate_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "characters" / "candidates" / "protagonist.json"
            candidate.parent.mkdir(parents=True)
            candidate.write_text(json.dumps(_candidate_payload(), ensure_ascii=False), encoding="utf-8")
            candidate.with_suffix(".md").write_text("# 候选人物\n", encoding="utf-8")
            creation_task = candidate.with_suffix(".agent_tasks.md")
            creation_task.write_text("# create\n", encoding="utf-8")
            write_agent_completion_marker(creation_task, root=root, handled_by="creator")

            review_dir = root / "reviews" / "assets"
            review_dir.mkdir(parents=True)
            review_task = review_dir / "protagonist_review.agent_tasks.md"
            review_task.write_text("# review\n", encoding="utf-8")
            review = _review_payload()
            review.update(
                {
                    "status": "recheck_required",
                    "applied_revision_actions": ["明确道德边界"],
                    "revision_round": 1,
                }
            )
            (review_dir / "protagonist_review.json").write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
            (review_dir / "protagonist_review.md").write_text("# 修订待复审\n", encoding="utf-8")
            (review_dir / "protagonist_review.agent_completion.json").write_text(
                json.dumps(
                    {
                        "schema": COMPLETION_SCHEMA,
                        "source_task": "reviews/assets/protagonist_review.agent_tasks.md",
                        "status": "recheck_required",
                        "handled_by": "revision-agent",
                        "completed_at": "2026-07-21T00:10:00Z",
                        "expected_artifacts_checked": False,
                        "notes": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            state = _asset_state(root, {"candidate": candidate, "asset_type": "character", "creation_task": creation_task})
            self.assertEqual(state["current_step"], "asset-review-agent-task")

            before = hashlib.sha256(candidate.read_bytes()).hexdigest()
            unchanged_task = {"candidate_sha256_before_revision": before}
            errors = asset_route._asset_revision_gate_errors(root, unchanged_task, candidate, "protagonist")
            self.assertTrue(any("did not change" in item for item in errors))

            payload = _candidate_payload()
            payload["psychology"] = {"fear": "再次迟疑", "moral_line": "即使受罚也不伪造证据"}
            candidate.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(asset_route._asset_revision_gate_errors(root, unchanged_task, candidate, "protagonist"), [])

    def test_revision_task_contract_uses_recheck_enum_and_names_prior_actions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "characters" / "candidates" / "protagonist.json"
            candidate.parent.mkdir(parents=True)
            candidate.write_text(json.dumps(_candidate_payload(), ensure_ascii=False), encoding="utf-8")
            candidate.with_suffix(".md").write_text("# 候选人物\n", encoding="utf-8")
            review_dir = root / "reviews" / "assets"
            review_dir.mkdir(parents=True)
            review = _review_payload()
            review["revision_actions"] = [
                {"id": "REV-101", "target": "characters/candidates/protagonist.json", "description": "补足选择证据"},
                {"id": "REV-102", "target": "characters/candidates/protagonist.json", "description": "统一角色语气"},
            ]
            (review_dir / "protagonist_review.json").write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
            (review_dir / "protagonist_review.md").write_text("# 待修订\n", encoding="utf-8")

            blueprint = asset_route._asset_blueprint_for_state(
                root,
                "protagonist",
                "character",
                "characters/candidates/protagonist.json",
                "asset-review-pass",
                "",
            )
            contract = "\n".join(blueprint["hard_constraints"])
            self.assertIn("`REV-101`", contract)
            self.assertIn("`REV-102`", contract)

            fields = asset_route._asset_system_owned_fields(
                candidate_id="protagonist",
                asset_type="character",
                candidate="characters/candidates/protagonist.json",
                current_state="asset-review-pass",
                source_paths=[],
                expected_outputs=["reviews/assets/protagonist_review.json"],
            )
            self.assertEqual(fields["enums"]["asset_review.status"], ["recheck_required"])


if __name__ == "__main__":
    unittest.main()
