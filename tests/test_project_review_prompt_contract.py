from pathlib import Path
import json
import os
import tempfile
import unittest

from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.preflight.canonicalization import canonicalize_task_outputs
from literary_engineering_studio.preflight.common import PreflightIssue
from literary_engineering_studio.preflight.project_review import validate_project_review_contract
from literary_engineering_studio.sandbox import SandboxManifest
from literary_engineering_studio_engine.platform_agent_tasks import (
    write_platform_canon_review_task,
    write_platform_committee_task,
)
from literary_engineering_studio_engine.public.literary import (
    project_review_repair_target_issues,
)
from literary_engineering_studio_engine.routes.review.project_gates import (
    _committee_decision_errors,
)
from literary_engineering_studio_engine.workflow.state_review_audit import (
    _committee_pass_step,
)


class ProjectReviewPromptContractTests(unittest.TestCase):
    def test_committee_disagreement_is_not_misclassified_as_action_item(self):
        with tempfile.TemporaryDirectory() as temporary:
            task, sandbox, review = self._fixture(Path(temporary), committee=True)
            review.write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/committee-review-agent/v1",
                        "final_recommendation": "revise",
                        "reviewers": [],
                        "disagreements": [
                            {
                                "topic": "Canon pass 是否足以发布",
                                "position_a": "足以",
                                "position_b": "仍需长篇门禁",
                                "resolution": "维持 revise",
                                "blocking": True,
                            }
                        ],
                        "action_items": [
                            {
                                "target_path": "plot/rhythm_plan.json",
                                "action": "补足第二章余波节奏。",
                                "verification": "章节节奏审计不再阻塞。",
                            }
                        ],
                        "source_paths": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            issues: list[PreflightIssue] = []

            validate_project_review_contract(task, sandbox, issues)

            self.assertEqual(issues, [])

    def test_committee_non_approve_still_requires_an_action_item(self):
        with tempfile.TemporaryDirectory() as temporary:
            task, sandbox, review = self._fixture(Path(temporary), committee=True)
            review.write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/committee-review-agent/v1",
                        "final_recommendation": "revise",
                        "reviewers": [],
                        "disagreements": [{"topic": "未解决争议", "blocking": True}],
                        "action_items": [],
                        "source_paths": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            issues: list[PreflightIssue] = []

            validate_project_review_contract(task, sandbox, issues)

            self.assertTrue(any(item.path.endswith("#action_items") for item in issues))

    def test_committee_rejects_invented_repair_targets_before_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            task, sandbox, review = self._fixture(Path(temporary), committee=True)
            review.write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/committee-review-agent/v1",
                        "final_recommendation": "approve_with_notes",
                        "reviewers": [],
                        "disagreements": [],
                        "action_items": [
                            {
                                "target_path": "drafts/candidates/chapter10_ending.md",
                                "action": "补足不存在的第十章。",
                                "verification": "达到精确目标字数。",
                            },
                            {
                                "target_path": "scenes/s06_consequence.md",
                                "action": "改变六场节奏。",
                                "verification": "节奏更丰富。",
                            },
                        ],
                        "source_paths": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            issues: list[PreflightIssue] = []

            validate_project_review_contract(task, sandbox, issues)

            selectors = {item.path.split("#", 1)[-1] for item in issues}
            self.assertIn("action_items[0].target_path", selectors)
            self.assertIn("action_items[1].target_path", selectors)
            self.assertTrue(all("does not exist" in item.message for item in issues))

    def test_project_review_target_contract_accepts_existing_exact_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "plot" / "rhythm_plan.json"
            target.parent.mkdir(parents=True)
            target.write_text("{}\n", encoding="utf-8")
            payload = {
                "action_items": [
                    {
                        "target_path": "plot/rhythm_plan.json",
                        "action": "调整节奏。",
                        "verification": "节奏审计通过。",
                    }
                ],
                "disagreements": [{"topic": "已解决分歧", "blocking": False}],
            }

            issues = project_review_repair_target_issues(
                root,
                payload,
                ("action_items", "disagreements"),
            )

            self.assertEqual(issues, [])

    def test_invalid_imported_committee_review_returns_to_agent_task(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            review = root / "reviews" / "agent" / "committee_project-final-audit.json"
            review.parent.mkdir(parents=True)
            payload = {
                "final_recommendation": "revise",
                "action_items": [
                    {
                        "target_path": "scenes/invented_scene.yaml",
                        "action": "改写场景。",
                        "verification": "缺陷消失。",
                    }
                ],
                "disagreements": [],
            }
            review.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            step = _committee_pass_step(root, review)
            gate_errors = _committee_decision_errors(
                root,
                payload,
                require_approve=False,
            )

            self.assertEqual(step["key"], "committee-agent-task")
            self.assertEqual(step["status"], "invalid")
            self.assertTrue(any("does not exist" in error for error in gate_errors))

    def test_repair_declaring_disagreement_has_its_own_exact_error_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            task, sandbox, review = self._fixture(Path(temporary), committee=True)
            review.write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/committee-review-agent/v1",
                        "final_recommendation": "revise",
                        "reviewers": [],
                        "disagreements": [
                            {
                                "topic": "节奏修复位置",
                                "repair_required": True,
                                "target_path": "plot/rhythm_plan.json",
                            }
                        ],
                        "action_items": [
                            {
                                "target_path": "plot/rhythm_plan.json",
                                "action": "调整宏观节奏。",
                                "verification": "节奏审计通过。",
                            }
                        ],
                        "source_paths": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            issues: list[PreflightIssue] = []

            validate_project_review_contract(task, sandbox, issues)

            paths = {item.path for item in issues}
            self.assertIn(
                "reviews/agent/committee_project-final-audit.json#disagreements[0].action",
                paths,
            )
            self.assertIn(
                "reviews/agent/committee_project-final-audit.json#disagreements[0].verification",
                paths,
            )

    def test_task_sidecars_expose_exact_top_level_contracts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canon = write_platform_canon_review_task(root)
            committee = write_platform_committee_task(
                root,
                subject="project-final-audit",
            )

            canon_text = canon.task_path.read_text(encoding="utf-8")
            committee_text = committee.task_path.read_text(encoding="utf-8")
            for field in (
                "conclusion",
                "blocking_issues",
                "warnings",
                "unresolved_facts",
                "timeline_risks",
                "recommendations",
            ):
                self.assertIn(field, canon_text)
            for field in (
                "final_recommendation",
                "reviewers",
                "disagreements",
                "action_items",
                "minority_opinions",
            ):
                self.assertIn(field, committee_text)

    def test_project_review_sidecars_are_explicitly_reissued(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canon = write_platform_canon_review_task(root)
            committee = write_platform_committee_task(
                root,
                subject="project-final-audit",
            )
            old = 1_000_000_000
            os.utime(canon.task_path, ns=(old, old))
            os.utime(committee.task_path, ns=(old, old))

            write_platform_canon_review_task(root)
            write_platform_committee_task(root, subject="project-final-audit")

            self.assertGreater(canon.task_path.stat().st_mtime_ns, old)
            self.assertGreater(committee.task_path.stat().st_mtime_ns, old)

    def test_explicit_verdict_and_actionable_findings_are_normalized(self):
        with tempfile.TemporaryDirectory() as temporary:
            task, sandbox, review = self._fixture(Path(temporary))
            review.write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/canon-review-agent/v1",
                        "verdict": "revise_required",
                        "summary": "时间线仍需修订。",
                        "blocking_issues": [],
                        "warnings": [],
                        "unresolved_facts": [],
                        "timeline_risks": [],
                        "source_paths": [],
                        "findings": [
                            {
                                "id": "F1",
                                "target_path": "canon/timeline.yaml",
                                "action": "补充事件顺序。",
                                "verification": "时间线包含已晋升场景事件。",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            canonicalize_task_outputs(task, sandbox)

            payload = json.loads(review.read_text(encoding="utf-8"))
            self.assertEqual(payload["conclusion"], "revise_required")
            self.assertEqual(payload["recommendations"][0]["target_path"], "canon/timeline.yaml")
            self.assertEqual(payload["recommendations"][0]["verification"], "时间线包含已晋升场景事件。")

    def test_preflight_reports_all_missing_contract_fields_in_one_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            task, sandbox, review = self._fixture(Path(temporary))
            review.write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/canon-review-agent/v1",
                        "verdict": "revise_required",
                        "findings": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            issues: list[PreflightIssue] = []

            validate_project_review_contract(task, sandbox, issues)

            selectors = {item.path.split("#", 1)[-1] for item in issues}
            self.assertIn("conclusion", selectors)
            self.assertIn("summary", selectors)
            self.assertIn("blocking_issues", selectors)
            self.assertIn("warnings", selectors)
            self.assertIn("unresolved_facts", selectors)
            self.assertIn("timeline_risks", selectors)
            self.assertIn("source_paths", selectors)
            self.assertIn("recommendations", selectors)

    @staticmethod
    def _fixture(
        root: Path,
        *,
        committee: bool = False,
    ) -> tuple[TaskPackage, SandboxManifest, Path]:
        workspace = root / "workspace"
        relative = (
            "reviews/agent/committee_project-final-audit.json"
            if committee
            else "reviews/agent/canon_review.json"
        )
        review = workspace / relative
        review.parent.mkdir(parents=True)
        state = "committee-agent-task" if committee else "canon-review-agent-task"
        markdown_relative = (
            "reviews/agent/committee_project-final-audit.md"
            if committee
            else "reviews/agent/canon_review.md"
        )
        task = TaskPackage(
            project_root=root,
            task_json_path=root / "task.json",
            task_markdown_path=root / "task.md",
            payload={
                "task_id": f"review-and-audit-project-review-{state}",
                "route": "review-and-audit",
                "current_state": state,
                "target_id": "project-review",
                "source_paths": ["reviews/canon_lint.json", "canon"],
                "expected_outputs": [
                    relative,
                    markdown_relative,
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
        for target, content in (
            ("plot/rhythm_plan.json", "{}\n"),
            ("canon/timeline.yaml", "events: []\n"),
        ):
            path = root / target
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return task, sandbox, review


if __name__ == "__main__":
    unittest.main()
