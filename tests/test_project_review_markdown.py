from pathlib import Path
import json
import tempfile
import unittest

from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.preflight.canonicalization import canonicalize_task_outputs
from literary_engineering_studio.sandbox import SandboxManifest
from literary_engineering_studio.task_preflight import validate_task_outputs


class ProjectReviewMarkdownTests(unittest.TestCase):
    def test_english_canon_conclusion_is_projected_from_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            task, sandbox, json_path, markdown_path = self._fixture(Path(temporary))
            self._write_canon_json(json_path, "pass")
            markdown_path.write_text("# Canon Review\n\n- Conclusion: pass\n\nEvidence.\n", encoding="utf-8")

            changes = canonicalize_task_outputs(task, sandbox)

            text = markdown_path.read_text(encoding="utf-8")
            self.assertIn("- 结论： pass", text)
            self.assertNotIn("Conclusion:", text)
            self.assertEqual(text.count("- 结论："), 1)
            self.assertTrue(any(item.get("field") == "machine_conclusion" for item in changes))

    def test_missing_and_conflicting_lines_converge_idempotently(self):
        with tempfile.TemporaryDirectory() as temporary:
            task, sandbox, json_path, markdown_path = self._fixture(Path(temporary))
            self._write_canon_json(json_path, "revise_required")
            markdown_path.write_text(
                "# Canon Review\n\n- 结论： pass\n- Conclusion: reject\n\nEvidence.\n",
                encoding="utf-8",
            )

            first = canonicalize_task_outputs(task, sandbox)
            second = canonicalize_task_outputs(task, sandbox)

            text = markdown_path.read_text(encoding="utf-8")
            self.assertEqual(text.count("- 结论："), 1)
            self.assertIn("- 结论： revise_required", text)
            self.assertTrue(first)
            self.assertEqual(second, [])

    def test_valid_json_adds_machine_line_and_passes_live_gate_shape(self):
        with tempfile.TemporaryDirectory() as temporary:
            task, sandbox, json_path, markdown_path = self._fixture(Path(temporary))
            self._write_canon_json(json_path, "pass")
            markdown_path.write_text("# Canon Review v1\n\n## Evidence\n\nClean.\n", encoding="utf-8")
            sandbox.baseline_path.write_text("{}\n", encoding="utf-8")

            canonicalize_task_outputs(task, sandbox)
            result = validate_task_outputs(task, sandbox)

            self.assertTrue(result.passed, result.as_dict())
            self.assertEqual(markdown_path.read_text(encoding="utf-8").count("- 结论： pass"), 1)

    def test_invalid_json_contract_does_not_manufacture_a_verdict(self):
        with tempfile.TemporaryDirectory() as temporary:
            task, sandbox, json_path, markdown_path = self._fixture(Path(temporary))
            json_path.write_text(
                json.dumps({"schema": "wrong", "conclusion": "pass"}),
                encoding="utf-8",
            )
            markdown_path.write_text("# Canon Review\n\nEvidence.\n", encoding="utf-8")

            canonicalize_task_outputs(task, sandbox)

            self.assertNotIn("- 结论：", markdown_path.read_text(encoding="utf-8"))

    def test_committee_recommendation_uses_its_own_enum(self):
        with tempfile.TemporaryDirectory() as temporary:
            task, sandbox, json_path, markdown_path = self._fixture(Path(temporary), committee=True)
            json_path.write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/committee-review-agent/v1",
                        "final_recommendation": "approve_with_notes",
                    }
                ),
                encoding="utf-8",
            )
            markdown_path.write_text("# Committee\n\n- Conclusion: approve_with_notes\n", encoding="utf-8")

            canonicalize_task_outputs(task, sandbox)

            self.assertIn("- 结论： approve_with_notes", markdown_path.read_text(encoding="utf-8"))

    def test_non_project_review_task_is_untouched(self):
        with tempfile.TemporaryDirectory() as temporary:
            task, sandbox, json_path, markdown_path = self._fixture(Path(temporary))
            task.payload["current_state"] = "scene-review-agent-task"
            self._write_canon_json(json_path, "pass")
            original = "# Scene Review\n\n- Conclusion: pass\n"
            markdown_path.write_text(original, encoding="utf-8")

            canonicalize_task_outputs(task, sandbox)

            self.assertEqual(markdown_path.read_text(encoding="utf-8"), original)

    @staticmethod
    def _fixture(root: Path, *, committee: bool = False):
        workspace = root / "workspace"
        if committee:
            json_relative = "reviews/agent/committee_project-final-audit.json"
            markdown_relative = "reviews/agent/committee_project-final-audit.md"
            state = "committee-agent-task"
            task_id = "review-and-audit-project-review-committee-agent-task"
        else:
            json_relative = "reviews/agent/canon_review.json"
            markdown_relative = "reviews/agent/canon_review.md"
            state = "canon-review-agent-task"
            task_id = "review-and-audit-project-review-canon-review-agent-task"
        json_path = workspace / json_relative
        markdown_path = workspace / markdown_relative
        json_path.parent.mkdir(parents=True)
        task = TaskPackage(
            project_root=root,
            task_json_path=root / "task.json",
            task_markdown_path=root / "task.md",
            payload={
                "task_id": task_id,
                "route": "review-and-audit",
                "current_state": state,
                "source_paths": [],
                "expected_outputs": [json_relative, markdown_relative],
                "validation_gates": ["canon review conclusion is recorded"],
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
        return task, sandbox, json_path, markdown_path

    @staticmethod
    def _write_canon_json(path: Path, conclusion: str) -> None:
        path.write_text(
            json.dumps(
                {
                    "schema": "literary-engineering-workbench/canon-review-agent/v1",
                    "conclusion": conclusion,
                    "summary": "Clean review.",
                    "blocking_issues": [],
                    "warnings": [],
                    "unresolved_facts": [],
                    "timeline_risks": [],
                    "source_paths": [],
                    "recommendations": [],
                }
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
