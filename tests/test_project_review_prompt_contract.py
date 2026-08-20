from pathlib import Path
import json
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


class ProjectReviewPromptContractTests(unittest.TestCase):
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
    def _fixture(root: Path) -> tuple[TaskPackage, SandboxManifest, Path]:
        workspace = root / "workspace"
        review = workspace / "reviews" / "agent" / "canon_review.json"
        review.parent.mkdir(parents=True)
        task = TaskPackage(
            project_root=root,
            task_json_path=root / "task.json",
            task_markdown_path=root / "task.md",
            payload={
                "task_id": "review-and-audit-project-review-canon-review-agent-task",
                "route": "review-and-audit",
                "current_state": "canon-review-agent-task",
                "target_id": "project-review",
                "source_paths": ["reviews/canon_lint.json", "canon"],
                "expected_outputs": [
                    "reviews/agent/canon_review.json",
                    "reviews/agent/canon_review.md",
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
        return task, sandbox, review


if __name__ == "__main__":
    unittest.main()
