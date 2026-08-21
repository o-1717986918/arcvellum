from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from ruamel.yaml import YAML

from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.preflight.project_review_repair_scope import (
    canonicalize_project_review_repair_scope,
)
from literary_engineering_studio.runtime.sandbox_contracts import SandboxManifest


class ProjectReviewRepairScopeTests(unittest.TestCase):
    def test_compiles_only_lint_authorized_fields_over_original_structure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sandbox = _sandbox(root)
            _write_baseline_documents(sandbox.control_workspace)
            _write_destructive_candidates(sandbox.workspace)
            _write_lint(sandbox.control_workspace)

            changes = canonicalize_project_review_repair_scope(_task(root), sandbox)

            scene = _yaml().load(
                (sandbox.workspace / "scenes" / "scene_0001.yaml").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(scene["status"], "ready")
            self.assertEqual(scene["scene_id"], "scene_0001")
            self.assertEqual(scene["chapter_id"], "chapter_0001")
            self.assertEqual(scene["output_state"]["new_facts"], ["fact-a"])
            self.assertNotIn("new_facts", scene)

            chapter = json.loads(
                (sandbox.workspace / "plot" / "chapters" / "chapter_001.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(chapter["status"], "completed")
            self.assertEqual(chapter["word_count_target"], 15000)
            self.assertEqual(chapter["scenes"][0]["status"], "ready")
            self.assertEqual(
                {item["scope"] for item in changes},
                {"status", "scenes[].status"},
            )

    def test_invalid_agent_status_is_not_promoted_into_original_scene(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sandbox = _sandbox(root)
            _write_baseline_documents(sandbox.control_workspace)
            _write_destructive_candidates(sandbox.workspace, scene_status="canon_lint_clear")
            _write_lint(sandbox.control_workspace)

            changes = canonicalize_project_review_repair_scope(_task(root), sandbox)

            scene_text = (sandbox.workspace / "scenes" / "scene_0001.yaml").read_text(
                encoding="utf-8"
            )
            self.assertNotIn("scene_id", scene_text)
            self.assertFalse(any(item["scope"] == "status" for item in changes))

    def test_non_mechanical_canon_target_keeps_agent_candidate_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sandbox = _sandbox(root)
            target = "canon/world_rules.yaml"
            for workspace, text in (
                (sandbox.control_workspace, "rules: []\n"),
                (sandbox.workspace, "rules:\n  - power_has_cost\n"),
            ):
                path = workspace / target
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            _write_lint(
                sandbox.control_workspace,
                issues=[
                    {
                        "check_id": "world-rule-semantic-gap",
                        "location": target,
                    }
                ],
            )
            task = _task(root, targets=[target])

            changes = canonicalize_project_review_repair_scope(task, sandbox)

            self.assertEqual(changes, [])
            self.assertEqual(
                (sandbox.workspace / target).read_text(encoding="utf-8"),
                "rules:\n  - power_has_cost\n",
            )


def _sandbox(root: Path) -> SandboxManifest:
    workspace = root / "workspace"
    control = root / "control"
    workspace.mkdir()
    control.mkdir()
    return SandboxManifest(
        run_id="run",
        run_root=root,
        workspace=workspace,
        prompt_path=workspace / "AGENT_TASK.md",
        manifest_path=root / "run.json",
        baseline_path=root / "baseline.json",
        expected_outputs=(),
        control_workspace=control,
    )


def _task(root: Path, *, targets: list[str] | None = None) -> TaskPackage:
    return TaskPackage(
        project_root=root,
        task_json_path=root / "task.json",
        task_markdown_path=root / "task.md",
        payload={
            "task_id": "canon-repair",
            "route": "review-and-audit",
            "current_state": "canon-review-pass",
            "repair_targets": targets
            or ["scenes/scene_0001.yaml", "plot/chapters/chapter_001.json"],
            "expected_outputs": targets or [],
        },
    )


def _write_baseline_documents(control: Path | None) -> None:
    assert control is not None
    scene = control / "scenes" / "scene_0001.yaml"
    scene.parent.mkdir(parents=True)
    scene.write_text(
        "scene_id: scene_0001\n"
        "chapter_id: chapter_0001\n"
        "status: canon_lint_clear\n"
        "location: orbital station\n"
        "participants: [protagonist]\n"
        "output_state:\n"
        "  new_facts: [fact-a]\n",
        encoding="utf-8",
    )
    chapter = control / "plot" / "chapters" / "chapter_001.json"
    chapter.parent.mkdir(parents=True)
    chapter.write_text(
        json.dumps(
            {
                "chapter_id": "chapter_001",
                "status": "completed",
                "word_count_target": 15000,
                "scenes": [
                    {
                        "scene_id": "scene_0001",
                        "path": "scenes/scene_0001.yaml",
                        "title": "Signal",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _write_destructive_candidates(
    workspace: Path,
    *,
    scene_status: str = "ready",
) -> None:
    scene = workspace / "scenes" / "scene_0001.yaml"
    scene.parent.mkdir(parents=True)
    scene.write_text(
        json.dumps(
            {
                "status": scene_status,
                "location": "orbital station",
                "participants": ["protagonist"],
                "new_facts": ["fact-a"],
            }
        ),
        encoding="utf-8",
    )
    chapter = workspace / "plot" / "chapters" / "chapter_001.json"
    chapter.parent.mkdir(parents=True)
    chapter.write_text(
        json.dumps(
            {
                "chapter_id": "chapter_001",
                "status": "ready",
                "word_count_target": 999,
                "scenes": [
                    {
                        "scene_id": "scene_0001",
                        "path": "scenes/scene_0001.yaml",
                        "status": "ready",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_lint(
    control: Path | None,
    *,
    issues: list[dict[str, object]] | None = None,
) -> None:
    assert control is not None
    path = control / "reviews" / "canon_lint.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "issues": issues
                or [
                    {
                        "check_id": "scene-status-invalid",
                        "location": "scenes/scene_0001.yaml",
                    },
                    {
                        "check_id": "chapter-scene-fields-missing",
                        "location": "plot/chapters/chapter_001.json",
                    },
                    {
                        "check_id": "chapter-scene-not-ready",
                        "location": "plot/chapters/chapter_001.json",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )


def _yaml() -> YAML:
    parser = YAML(typ="safe")
    parser.allow_duplicate_keys = False
    return parser


if __name__ == "__main__":
    unittest.main()
