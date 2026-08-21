from pathlib import Path
import hashlib
import json
import os
import tempfile
import unittest

from literary_engineering_studio.contracts import TASK_SCHEMA, load_task_package
from literary_engineering_studio.runtime.context_budget import resolve_task_context_budget
from literary_engineering_studio.sandbox import stage_task
from literary_engineering_studio.preflight.service import canonicalize_task_outputs
from literary_engineering_studio.task_preflight import COMPLETION_SCHEMA, validate_task_outputs
from literary_engineering_studio_engine.agent_tasks import write_agent_completion_marker
from literary_engineering_studio_engine.literary.assets.canon.contracts import CANON_LINT_CONTRACT_REVISION
from literary_engineering_studio_engine.platform_agent_tasks import write_platform_canon_review_task
from literary_engineering_studio_engine.review_audit_route import _review_audit_blueprint_for_state
from literary_engineering_studio_engine.routes.review.canon_gates import canon_lint_gate_errors
from literary_engineering_studio_engine.routes.review.gates import review_audit_state_gate_validation
from literary_engineering_studio_engine.routes.review.task_payload import build_review_audit_task_payload
from literary_engineering_studio_engine.tasking.package_contract import enrich_task_payload
from literary_engineering_studio_engine.workflow.state_review_audit import _review_audit_state


def _canon_review(conclusion: str = "revise_required") -> dict[str, object]:
    return {
        "schema": "literary-engineering-workbench/canon-review-agent/v1",
        "conclusion": conclusion,
        "summary": "世界规则缺少能力代价。",
        "blocking_issues": [{"id": "B1", "target_path": "canon/world_rules.yaml", "action": "补充代价"}] if conclusion != "pass" else [],
        "warnings": [],
        "unresolved_facts": [],
        "timeline_risks": [],
        "source_paths": ["canon/world_rules.yaml"],
        "recommendations": [{"id": "R1", "target_path": "canon/world_rules.yaml", "action": "补充代价", "verification": "规则包含可验证代价"}] if conclusion != "pass" else [],
        "next_gate": "repair" if conclusion != "pass" else "longform-audit",
    }


def _lint_payload() -> dict[str, object]:
    return {
        "schema": "literary-engineering-workbench/canon-lint/v0.1",
        "contract_revision": CANON_LINT_CONTRACT_REVISION,
        "status": "pass",
        "summary": {"blocking_count": 0, "warning_count": 0},
    }


class ReviewAuditRevisionLoopTests(unittest.TestCase):
    def _write_task(self, project: Path, payload: dict[str, object], name: str) -> Path:
        task_dir = project / "workflow" / "tasks"
        task_dir.mkdir(parents=True, exist_ok=True)
        markdown = task_dir / f"{name}.agent_tasks.md"
        markdown.write_text("# task\n", encoding="utf-8")
        path = task_dir / f"{name}.json"
        path.write_text(json.dumps({"schema": TASK_SCHEMA, "task_markdown": f"workflow/tasks/{name}.agent_tasks.md", "required_reading": [], "source_paths": [], "forbidden_shortcuts": [], **payload}, ensure_ascii=False), encoding="utf-8")
        return path

    def test_non_pass_canon_review_is_valid_completed_judgment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            task_json = self._write_task(
                project,
                {
                    "task_id": "canon-review",
                    "route": "review-and-audit",
                    "current_state": "canon-review-agent-task",
                    "task_type": "platform-agent-review",
                    "expected_outputs": ["reviews/agent/canon_review.json", "reviews/agent/canon_review.md", "reviews/agent/canon_review.agent_completion.json"],
                    "validation_gates": ["canon review conclusion is recorded"],
                },
                "canon-review",
            )
            task = load_task_package(project, task_json)
            sandbox = stage_task(task, root / "runs", runtime="opencode")
            review_dir = sandbox.workspace / "reviews" / "agent"
            review_dir.mkdir(parents=True, exist_ok=True)
            (review_dir / "canon_review.json").write_text(json.dumps(_canon_review(), ensure_ascii=False), encoding="utf-8")
            (review_dir / "canon_review.md").write_text(
                "# Canon Review\n\n- 结论： revise_required\n\n需要修订。\n",
                encoding="utf-8",
            )
            (review_dir / "canon_review.agent_completion.json").write_text(
                json.dumps({"schema": COMPLETION_SCHEMA, "source_task": "reviews/agent/canon_review.agent_tasks.md", "status": "complete", "handled_by": "reviewer", "completed_at": "2026-07-21T00:00:00Z", "expected_artifacts_checked": True, "notes": []}, ensure_ascii=False),
                encoding="utf-8",
            )

            result = validate_task_outputs(task, sandbox)

            self.assertTrue(result.passed, result.as_dict())

    def test_canon_revision_changes_declared_target_and_reopens_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            (project / "canon").mkdir(parents=True)
            target = project / "canon" / "world_rules.yaml"
            target.write_text("rules: []\n", encoding="utf-8")
            review_dir = project / "reviews" / "agent"
            review_dir.mkdir(parents=True)
            (review_dir / "canon_review.json").write_text(json.dumps(_canon_review(), ensure_ascii=False), encoding="utf-8")
            (review_dir / "canon_review.md").write_text("# Canon Review\n", encoding="utf-8")
            sidecar = review_dir / "canon_review.agent_tasks.md"
            sidecar.write_text("# review\n", encoding="utf-8")
            write_agent_completion_marker(sidecar, root=project, handled_by="reviewer")
            (project / "reviews" / "canon_lint.json").write_text(json.dumps(_lint_payload(), ensure_ascii=False), encoding="utf-8")
            (project / "reviews" / "canon_lint.md").write_text("# Canon Lint\n", encoding="utf-8")

            blueprint = _review_audit_blueprint_for_state(project, "canon-review-pass", "repair")
            self.assertEqual(blueprint["repair_targets"], ["canon/world_rules.yaml"])
            payload = build_review_audit_task_payload(
                project,
                "review-and-audit",
                {
                    "current_step": "canon-review-pass",
                    "next_action": "repair",
                },
            )
            self.assertEqual(
                payload["context_must_inline_paths"],
                ["reviews/agent/canon_review.json"],
            )
            self.assertIn(
                "canon/world_rules.yaml",
                payload["context_exact_on_demand_paths"],
            )
            self.assertNotIn(
                "reviews/agent/canon_review.md",
                payload["agent_source_paths"],
            )
            self.assertEqual(payload["context_contract_status"], "bounded-ready")
            before = hashlib.sha256(target.read_bytes()).hexdigest()
            payload = enrich_task_payload(
                build_review_audit_task_payload(
                    project,
                    "review-and-audit",
                    {
                        "current_step": "canon-review-pass",
                        "next_action": "repair",
                    },
                )
            )
            self.assertEqual(
                payload["expected_outputs"],
                [
                    "canon/world_rules.yaml",
                    "reviews/agent/canon_review.json",
                    "reviews/agent/canon_review.agent_completion.json",
                ],
            )
            self.assertEqual(
                payload["core_managed_outputs"],
                ["reviews/agent/canon_review.json"],
            )
            self.assertNotIn("reviews/canon_lint.json", payload["expected_outputs"])
            task_json = self._write_task(
                project,
                payload,
                "canon-fix",
            )
            task = load_task_package(project, task_json)
            sandbox = stage_task(task, root / "runs", runtime="opencode")
            (sandbox.workspace / "canon" / "world_rules.yaml").write_text("rules:\n  - power_has_cost\n", encoding="utf-8")

            canonicalize_task_outputs(task, sandbox)
            result = validate_task_outputs(task, sandbox)

            self.assertTrue(result.passed, result.as_dict())
            reset = json.loads(
                (sandbox.workspace / "reviews" / "agent" / "canon_review.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(reset["conclusion"], "recheck_required")
            self.assertEqual(
                reset["applied_repair_actions"][0]["target_path"],
                "canon/world_rules.yaml",
            )
            self.assertEqual(
                reset["applied_repair_actions"][0]["before_sha256"], before
            )
            completion = json.loads(
                (
                    sandbox.workspace
                    / "reviews"
                    / "agent"
                    / "canon_review.agent_completion.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(completion["status"], "recheck_required")
            self.assertFalse(completion["expected_artifacts_checked"])

    def test_project_revision_rejects_refreshed_lint_warnings(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reviews = root / "reviews"
            reviews.mkdir(parents=True)
            (reviews / "canon_lint.md").write_text("# Canon Lint\n", encoding="utf-8")
            (reviews / "canon_lint.json").write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/canon-lint/v0.1",
                        "contract_revision": CANON_LINT_CONTRACT_REVISION,
                        "status": "pass_with_warnings",
                        "summary": {"blocking_count": 0, "warning_count": 1},
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(canon_lint_gate_errors(root), [])
            errors = canon_lint_gate_errors(root, require_clean=True)
            self.assertTrue(any("warning_count must be 0" in item for item in errors))
            self.assertTrue(any("status must be pass" in item for item in errors))

    def test_review_state_refreshes_an_outdated_lint_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lint = root / "reviews" / "canon_lint.json"
            lint.parent.mkdir(parents=True)
            lint.write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/canon-lint/v0.1",
                        "status": "pass",
                        "summary": {"blocking_count": 0, "warning_count": 0},
                    }
                ),
                encoding="utf-8",
            )
            lint.with_suffix(".md").write_text("# old lint\n", encoding="utf-8")

            state = _review_audit_state(root)
            errors = canon_lint_gate_errors(root, require_current_contract=True)

            self.assertEqual(state["current_step"], "canon-lint-file")
            self.assertEqual(state["steps"][1]["status"], "stale")
            self.assertTrue(any("contract_revision" in item for item in errors))

    def test_large_canon_revision_compiles_as_target_sliced_review_prompt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("project:\n  title: 测试\n", encoding="utf-8")
            review_dir = root / "reviews" / "agent"
            review_dir.mkdir(parents=True)
            targets = ["canon/timeline.yaml", *[f"scenes/scene_{index:04d}.yaml" for index in range(1, 7)]]
            recommendations = [
                {
                    "target_path": target,
                    "action": "补齐精确时间或地点事实。",
                    "verification": "重新审查后缺口消失。",
                }
                for target in targets
            ]
            review = _canon_review()
            review["blocking_issues"] = recommendations
            review["recommendations"] = recommendations
            (review_dir / "canon_review.json").write_text(
                json.dumps(review, ensure_ascii=False), encoding="utf-8"
            )
            (review_dir / "canon_review.md").write_text("审查说明" * 2_000, encoding="utf-8")
            lint_dir = root / "reviews"
            (lint_dir / "canon_lint.json").write_text(
                json.dumps({**_lint_payload(), "details": "诊断" * 4_000}, ensure_ascii=False),
                encoding="utf-8",
            )
            for target in targets:
                path = root / target
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("scene: evidence\n" + "事实" * 1_300, encoding="utf-8")

            payload = enrich_task_payload(
                build_review_audit_task_payload(
                    root,
                    "review-and-audit",
                    {"current_step": "canon-review-pass", "next_action": "repair"},
                )
            )
            self.assertTrue(
                any(
                    "allowed_values" in item and "never invent lifecycle labels" in item
                    for item in payload["hard_constraints"]
                )
            )
            task = load_task_package(
                root,
                self._write_task(root, payload, "canon-fix-prompt"),
            )
            budget = resolve_task_context_budget(task)

            sandbox = stage_task(
                task,
                root / "runs",
                runtime="pi-worker",
                context_budget=budget,
                execution_profile={"runtime_id": "pi-worker"},
                prompt_program_config={
                    "mode": "enforced",
                    "fallback": "error",
                    "enforcement": {"enabled": True, "runtimes": ["pi-worker"]},
                },
            )
            run = json.loads(sandbox.manifest_path.read_text(encoding="utf-8"))
            context = json.loads(
                (sandbox.workspace / "TASK_CONTEXT.json").read_text(encoding="utf-8")
            )

            self.assertEqual(budget.task_kind.value, "review")
            self.assertLess(
                run["prompt_program"]["formal"]["metrics"]["total_characters"],
                12_000,
            )
            self.assertEqual(
                context["prompt_access"]["inline"],
                ["reviews/agent/canon_review.json"],
            )
            for target in targets:
                self.assertIn(target, context["prompt_access"]["exact_on_demand"])
            self.assertEqual(
                [
                    item.path
                    for item in task.execution_contract.outputs
                    if item.kind == "agent-authored"
                ],
                targets,
            )

    def test_committee_revision_uses_the_same_target_sliced_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "plot" / "outline.md"
            target.parent.mkdir(parents=True)
            target.write_text("# 大纲\n", encoding="utf-8")
            review_dir = root / "reviews" / "agent"
            review_dir.mkdir(parents=True)
            (review_dir / "committee_project-final-audit.json").write_text(
                json.dumps(
                    {
                        "final_recommendation": "revise",
                        "action_items": [
                            {
                                "target_path": "plot/outline.md",
                                "action": "补足结尾因果。",
                                "verification": "长篇审计不再报告缺口。",
                            }
                        ],
                        "disagreements": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (review_dir / "committee_project-final-audit.md").write_text(
                "# 委员会审查\n", encoding="utf-8"
            )
            (review_dir / "canon_review.json").write_text(
                json.dumps(_canon_review("pass"), ensure_ascii=False), encoding="utf-8"
            )
            longform = root / "reviews" / "longform" / "longform_audit.json"
            longform.parent.mkdir(parents=True)
            longform.write_text("{}\n", encoding="utf-8")

            payload = build_review_audit_task_payload(
                root,
                "review-and-audit",
                {"current_step": "committee-pass", "next_action": "repair"},
            )

            self.assertEqual(
                payload["context_must_inline_paths"],
                ["reviews/agent/committee_project-final-audit.json"],
            )
            self.assertIn(
                "reviews/agent/canon_review.json",
                payload["context_exact_on_demand_paths"],
            )
            self.assertIn(
                "reviews/longform/longform_audit.json",
                payload["context_exact_on_demand_paths"],
            )
            self.assertIn(
                "plot/outline.md",
                payload["context_exact_on_demand_paths"],
            )
            enriched = enrich_task_payload(payload)
            self.assertNotIn(
                "reviews/longform/longform_audit.json",
                enriched["expected_outputs"],
            )
            self.assertEqual(
                enriched["core_managed_outputs"],
                [
                    "reviews/agent/canon_review.json",
                    "reviews/agent/committee_project-final-audit.json",
                ],
            )

    def test_recheck_marker_makes_prior_canon_lint_stale(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lint = root / "reviews" / "canon_lint.json"
            lint.parent.mkdir(parents=True)
            lint.write_text(json.dumps(_lint_payload()), encoding="utf-8")
            lint.with_suffix(".md").write_text("# lint\n", encoding="utf-8")
            marker = root / "reviews" / "agent" / "canon_review.agent_completion.json"
            marker.parent.mkdir(parents=True)
            marker.write_text(
                json.dumps({"status": "recheck_required"}), encoding="utf-8"
            )
            os.utime(lint, ns=(1_000_000_000, 1_000_000_000))
            os.utime(marker, ns=(2_000_000_000, 2_000_000_000))

            state = _review_audit_state(root)

            self.assertEqual(state["current_step"], "canon-lint-file")
            self.assertEqual(state["steps"][1]["status"], "stale")

    def test_fresh_lint_requires_a_fresh_canon_review_sidecar(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = root / "reviews" / "agent" / "canon_review.agent_tasks.md"
            task.parent.mkdir(parents=True)
            task.write_text("# old sidecar\n", encoding="utf-8")
            lint = root / "reviews" / "canon_lint.json"
            lint.parent.mkdir(parents=True, exist_ok=True)
            lint.write_text(json.dumps(_lint_payload()), encoding="utf-8")
            lint.with_suffix(".md").write_text("# lint\n", encoding="utf-8")
            os.utime(task, ns=(1_000_000_000, 1_000_000_000))
            os.utime(lint, ns=(2_000_000_000, 2_000_000_000))

            state = _review_audit_state(root)

            self.assertEqual(state["current_step"], "canon-review-task-file")
            self.assertEqual(state["steps"][2]["status"], "stale")

            stale_errors, _ = review_audit_state_gate_validation(
                root,
                {"current_state": "canon-review-task-file"},
            )
            self.assertTrue(any("predates current lint" in item for item in stale_errors))

            write_platform_canon_review_task(root)
            refreshed = _review_audit_state(root)
            fresh_errors, _ = review_audit_state_gate_validation(
                root,
                {"current_state": "canon-review-task-file"},
            )

            self.assertEqual(refreshed["current_step"], "canon-review-agent-task")
            self.assertEqual(fresh_errors, [])


if __name__ == "__main__":
    unittest.main()
