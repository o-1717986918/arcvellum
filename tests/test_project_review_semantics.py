from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio_engine.literary.review.longform_contract import (
    LONGFORM_AUDIT_SCHEMA,
    longform_input_snapshot,
)
from literary_engineering_studio_engine.literary.review.project_review_semantics import (
    canon_review_is_clean,
    committee_review_is_clean,
)
from literary_engineering_studio_engine.workflow.audit.review import (
    _add_review_audit_route_gates,
)


class ProjectReviewSemanticsTests(unittest.TestCase):
    def test_canon_pass_with_notes_is_clean_when_formal_findings_are_empty(self):
        payload = {
            "conclusion": "pass_with_notes",
            "blocking_issues": [],
            "warnings": [],
            "unresolved_facts": [],
            "timeline_risks": [],
            "recommendations": [{"action": "No change required."}],
        }

        self.assertTrue(canon_review_is_clean(payload))
        payload["warnings"] = [{"message": "真实警告"}]
        self.assertFalse(canon_review_is_clean(payload))

    def test_committee_approve_with_notes_requires_no_open_work(self):
        payload = {
            "final_recommendation": "approve_with_notes",
            "action_items": [],
            "disagreements": [],
        }

        self.assertTrue(committee_review_is_clean(payload))
        payload["action_items"] = [{"action": "修复"}]
        self.assertFalse(committee_review_is_clean(payload))

    def test_route_audit_uses_shared_clean_review_semantics(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write(root / "project.yaml", "project:\n  title: semantic review\n")
            self._write(
                root / "reviews/canon_lint.json",
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/canon-lint/v0.1",
                        "summary": {"blocking_count": 0},
                    }
                ),
            )
            canon = {
                "conclusion": "pass_with_notes",
                "blocking_issues": [],
                "warnings": [],
                "unresolved_facts": [],
                "timeline_risks": [],
            }
            committee = {
                "final_recommendation": "approve_with_notes",
                "action_items": [],
                "disagreements": [],
            }
            self._write(root / "reviews/agent/canon_review.json", json.dumps(canon))
            self._write(root / "reviews/agent/canon_review.md", "# Canon review\n")
            self._write(
                root / "reviews/agent/committee_project-final-audit.json",
                json.dumps(committee),
            )
            self._write(
                root / "reviews/agent/committee_project-final-audit.md",
                "# Committee review\n",
            )
            audit = {
                "schema": LONGFORM_AUDIT_SCHEMA,
                "summary": {"blocking_issue_count": 0},
                "issues": [],
                "input_snapshot": longform_input_snapshot(root),
            }
            self._write(root / "reviews/longform/longform_audit.json", json.dumps(audit))
            self._write(root / "reviews/longform/longform_audit.md", "# Longform audit\n")
            self._write(root / "plot/longform_graph.json", "{}\n")

            gates: list[dict[str, str]] = []
            with (
                patch(
                    "literary_engineering_studio_engine.workflow.audit.review.agent_task_completion_status",
                    return_value={"complete": True},
                ),
                patch(
                    "literary_engineering_studio_engine.workflow.audit.review.validate_payload",
                    return_value=([], []),
                ),
            ):
                _add_review_audit_route_gates(gates, root)

            by_key = {item["key"]: item["status"] for item in gates}
            self.assertEqual(by_key["review:canon-review-clean-pass"], "pass")
            self.assertEqual(by_key["review:committee-approve"], "pass")

    @staticmethod
    def _write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
