from pathlib import Path
import hashlib
import tempfile
import unittest

from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.preflight.declared_repair import (
    validate_source_extraction_revision,
)
from literary_engineering_studio.sandbox import SandboxManifest


class DeclaredRepairPreflightTests(unittest.TestCase):
    def test_longform_review_does_not_require_candidate_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = self._task(root, "budget-review", "platform-agent-review", {})
            issues = []

            validate_source_extraction_revision(task, self._sandbox(root), issues)

        self.assertEqual(issues, [])

    def test_longform_revision_requires_a_changed_declared_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            relative = "plot/candidates/outlines/word_budget_expansion.md"
            target = root / "workspace" / relative
            target.parent.mkdir(parents=True)
            target.write_text("unchanged candidate", encoding="utf-8")
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            task = self._task(
                root,
                "budget-revision",
                "platform-agent-revision",
                {
                    "repair_targets": [relative],
                    "repair_target_sha256_before_revision": {relative: digest},
                },
            )
            issues = []

            validate_source_extraction_revision(task, self._sandbox(root), issues)

        self.assertEqual([issue.code for issue in issues], ["declared-repair-target-unchanged"])

    @staticmethod
    def _task(
        root: Path,
        state: str,
        task_type: str,
        extra: dict[str, object],
    ) -> TaskPackage:
        return TaskPackage(
            project_root=root,
            task_json_path=root / "task.json",
            task_markdown_path=root / "task.md",
            payload={
                "task_id": f"longform-planning-longform-{state}",
                "route": "longform-planning",
                "current_state": state,
                "task_type": task_type,
                "source_paths": [],
                "expected_outputs": [],
                **extra,
            },
        )

    @staticmethod
    def _sandbox(root: Path) -> SandboxManifest:
        workspace = root / "workspace"
        workspace.mkdir(exist_ok=True)
        return SandboxManifest(
            run_id="declared-repair-test",
            run_root=root,
            workspace=workspace,
            prompt_path=root / "prompt.md",
            manifest_path=root / "manifest.json",
            baseline_path=root / "baseline.json",
            expected_outputs=(),
        )


if __name__ == "__main__":
    unittest.main()
