from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.contracts import TASK_SCHEMA, load_task_package
from literary_engineering_studio.sandbox import stage_task
from literary_engineering_studio.task_preflight import (
    COMPLETION_SCHEMA,
    canonicalize_task_outputs,
    validate_task_outputs,
)


class TaskPreflightTests(unittest.TestCase):
    def test_rejects_format_shortcuts_then_accepts_exact_review_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            task_dir = project / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            (project / "project.yaml").write_text("title: fixture\n", encoding="utf-8")
            task_markdown = task_dir / "review.agent_tasks.md"
            task_markdown.write_text("# Review task\n", encoding="utf-8")
            task_json = task_dir / "review.json"
            task_json.write_text(
                json.dumps(
                    {
                        "schema": TASK_SCHEMA,
                        "task_id": "review",
                        "route": "review-and-audit",
                        "current_state": "agent-review",
                        "task_type": "platform-agent-review",
                        "task_markdown": "workflow/tasks/review.agent_tasks.md",
                        "required_reading": [],
                        "source_paths": [],
                        "expected_outputs": [
                            "reviews/scene.agent_review.md",
                            "workflow/tasks/review.agent_tasks.agent_completion.json",
                        ],
                        "validation_gates": ["review conclusion is pass"],
                        "forbidden_shortcuts": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            task = load_task_package(project, task_json)
            sandbox = stage_task(task, root / "runs", runtime="opencode")
            review = sandbox.workspace / "reviews" / "scene.agent_review.md"
            completion = sandbox.workspace / "workflow" / "tasks" / "review.agent_tasks.agent_completion.json"
            review.parent.mkdir(parents=True, exist_ok=True)
            completion.parent.mkdir(parents=True, exist_ok=True)
            review.write_text("## 结论： pass\n", encoding="utf-8")
            completion.write_text(
                json.dumps(
                    {
                        "schema": COMPLETION_SCHEMA,
                        "status": "complete",
                        "expected_artifacts_checked": False,
                        "source_task": "wrong.md",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            failed = validate_task_outputs(task, sandbox)
            self.assertFalse(failed.passed)
            self.assertEqual(
                {item.code for item in failed.issues},
                {"invalid-completion-evidence", "missing-machine-conclusion"},
            )
            self.assertIn("只修复下列明确问题", failed.repair_prompt(1, 2))

            changes = canonicalize_task_outputs(task, sandbox)
            self.assertEqual(changes, [{"path": "reviews/scene.agent_review.md", "verdict": "pass"}])
            self.assertEqual(
                {item.code for item in validate_task_outputs(task, sandbox).issues},
                {"invalid-completion-evidence"},
            )

            review.write_text("# 审查报告\n\n- 结论： pass\n", encoding="utf-8")
            completion.write_text(
                json.dumps(
                    {
                        "schema": COMPLETION_SCHEMA,
                        "status": "complete",
                        "expected_artifacts_checked": True,
                        "source_task": "workflow/tasks/review.agent_tasks.md",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            passed = validate_task_outputs(task, sandbox)
            self.assertTrue(passed.passed, passed.as_dict())

    def test_scene_review_contract_is_checked_before_writeback_and_task_metadata_is_normalized(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            task_dir = project / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            candidate = project / "drafts" / "candidates" / "scene_0001-platform-agent.md"
            candidate.parent.mkdir(parents=True)
            candidate.write_text("## 正文候选\n\n她推开了门。\n", encoding="utf-8")
            (project / "project.yaml").write_text("title: fixture\n", encoding="utf-8")
            task_markdown = task_dir / "candidate-review.agent_tasks.md"
            task_markdown.write_text("# Candidate review\n", encoding="utf-8")
            task_json = task_dir / "candidate-review.json"
            task_json.write_text(
                json.dumps(
                    {
                        "schema": TASK_SCHEMA,
                        "task_id": "scene-development-scene_0001-candidate-review",
                        "route": "scene-development",
                        "scene_id": "scene_0001",
                        "current_state": "candidate-review",
                        "task_type": "platform-agent-review",
                        "candidate": "drafts/candidates/scene_0001-platform-agent.md",
                        "task_markdown": "workflow/tasks/candidate-review.agent_tasks.md",
                        "required_reading": [],
                        "source_paths": ["drafts/candidates/scene_0001-platform-agent.md"],
                        "expected_outputs": ["reviews/agent/scene_0001_scene_review.json"],
                        "validation_gates": ["scene_review.v1 JSON exists"],
                        "forbidden_shortcuts": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            task = load_task_package(project, task_json)
            sandbox = stage_task(task, root / "runs", runtime="opencode")
            self.assertEqual(
                (sandbox.workspace / "project.yaml").read_text(encoding="utf-8"),
                "title: fixture\n",
            )
            review = sandbox.workspace / "reviews" / "agent" / "scene_0001_scene_review.json"
            review.parent.mkdir(parents=True, exist_ok=True)
            review.write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/scene-review/v1",
                        "scene_id": "wrong-scene",
                        "candidate_sha256": "example",
                        "conclusion": "pass_with_notes",
                        "summary": "Review evidence exists, but the contract is incomplete.",
                    }
                ),
                encoding="utf-8",
            )

            failed = validate_task_outputs(task, sandbox)
            codes = {item.code for item in failed.issues}
            self.assertIn("scene-review-schema-invalid", codes)
            self.assertIn("scene-review-candidate-digest-mismatch", codes)
            self.assertIn("scene-review-candidate-source-missing", codes)

            changes = canonicalize_task_outputs(task, sandbox)
            self.assertTrue(changes)
            normalized = json.loads(review.read_text(encoding="utf-8"))
            self.assertEqual(normalized["schema"], "literary-engineering-workbench/scene-review-agent/v1")
            self.assertEqual(normalized["scene_id"], "scene_0001")
            self.assertIn("drafts/candidates/scene_0001-platform-agent.md", normalized["source_paths"])
            remaining = validate_task_outputs(task, sandbox)
            self.assertTrue(any(item.code == "scene-review-schema-invalid" for item in remaining.issues))
            self.assertFalse(any(item.code == "scene-review-candidate-digest-mismatch" for item in remaining.issues))
            self.assertIn("必须逐一读取", (sandbox.workspace / "AGENT_TASK.md").read_text(encoding="utf-8"))

    def test_asset_schema_is_rejected_before_writeback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            task_dir = project / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            (project / "project.yaml").write_text("title: fixture\n", encoding="utf-8")
            task_markdown = task_dir / "asset.agent_tasks.md"
            task_markdown.write_text("# Asset task\n", encoding="utf-8")
            task_json = task_dir / "asset.json"
            task_json.write_text(
                json.dumps(
                    {
                        "schema": TASK_SCHEMA,
                        "task_id": "asset",
                        "route": "character-and-world-assets",
                        "current_state": "asset-creation-agent-task",
                        "task_type": "platform-agent-asset-creation",
                        "asset_type": "character",
                        "candidate": "characters/candidates/protagonist.json",
                        "task_markdown": "workflow/tasks/asset.agent_tasks.md",
                        "required_reading": [],
                        "source_paths": [],
                        "expected_outputs": ["characters/candidates/protagonist.json"],
                        "validation_gates": ["candidate schema validates"],
                        "forbidden_shortcuts": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            task = load_task_package(project, task_json)
            sandbox = stage_task(task, root / "runs", runtime="opencode")
            candidate = sandbox.workspace / "characters" / "candidates" / "protagonist.json"
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_text(
                json.dumps(
                    {
                        "schema": "character_profile.v1",
                        "candidate_id": "protagonist",
                        "asset_type": "character",
                        "risks": [],
                        "source_paths": [],
                        "promotion_notes": {"action": "review"},
                        "characters": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = validate_task_outputs(task, sandbox)

            self.assertFalse(result.passed)
            self.assertIn("asset-schema-invalid", {item.code for item in result.issues})
            self.assertIn("asset-metadata-invalid", {item.code for item in result.issues})
            self.assertIn("character_id", result.repair_prompt(1, 2))

    def test_candidate_provenance_gate_reaches_runner_repair_loop(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            task_dir = project / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            (project / "project.yaml").write_text("title: fixture\n", encoding="utf-8")
            task_markdown = task_dir / "candidate.agent_tasks.md"
            task_markdown.write_text("# Candidate task\n", encoding="utf-8")
            task_json = task_dir / "candidate.json"
            outputs = [
                "drafts/candidates/scene_0001-platform-agent.md",
                "drafts/candidates/scene_0001-platform-agent.json",
                "drafts/candidates/scene_0001-platform-agent.prompt.json",
                "drafts/candidates/scene_0001-platform-agent.agent_tasks.md",
                "drafts/candidates/scene_0001-platform-agent.agent_completion.json",
            ]
            task_json.write_text(
                json.dumps(
                    {
                        "schema": TASK_SCHEMA,
                        "task_id": "candidate",
                        "route": "scene-development",
                        "scene_id": "scene_0001",
                        "current_state": "candidate-generation-provenance",
                        "task_type": "main-platform-agent-prose",
                        "task_markdown": "workflow/tasks/candidate.agent_tasks.md",
                        "required_reading": [],
                        "source_paths": [],
                        "expected_outputs": outputs,
                        "validation_gates": [],
                        "forbidden_shortcuts": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            task = load_task_package(project, task_json)
            sandbox = stage_task(task, root / "runs", runtime="opencode")
            for relative in outputs:
                path = sandbox.workspace / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                if relative.endswith(".json"):
                    path.write_text("{}", encoding="utf-8")
                else:
                    path.write_text("正文。", encoding="utf-8")
            completion = sandbox.workspace / outputs[-1]
            completion.write_text(
                json.dumps(
                    {
                        "schema": COMPLETION_SCHEMA,
                        "status": "complete",
                        "expected_artifacts_checked": True,
                        "source_task": "drafts/candidates/scene_0001-platform-agent.agent_tasks.md",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with patch(
                "literary_engineering_studio_engine.candidate_promotion.candidate_generation_gate",
                return_value={"status": "invalid", "message": "provenance invalid", "invalid": ["new_character_register.blocking_issues is not empty"]},
            ):
                result = validate_task_outputs(task, sandbox)

            self.assertFalse(result.passed)
            self.assertIn("candidate-provenance-invalid", {item.code for item in result.issues})
            self.assertIn("new_character_register", result.repair_prompt(1, 2))

    def test_candidate_register_is_normalized_from_declared_scene_character_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            task_dir = project / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            (project / "project.yaml").write_text("title: fixture\n", encoding="utf-8")
            markdown = task_dir / "candidate.agent_tasks.md"
            markdown.write_text("# Candidate task\n", encoding="utf-8")
            payload = {
                "schema": TASK_SCHEMA,
                "task_id": "candidate",
                "route": "scene-development",
                "scene_id": "scene_0001",
                "current_state": "candidate-generation-provenance",
                "task_type": "main-platform-agent-prose",
                "task_markdown": "workflow/tasks/candidate.agent_tasks.md",
                "required_reading": [],
                "source_paths": [],
                "expected_outputs": ["drafts/candidates/scene_0001-platform-agent.md"],
                "scene_character_assets": [{
                    "name": "林正",
                    "candidate_id": "scene-0001-林正",
                    "candidate_path": "characters/candidates/scene-0001-林正.json",
                    "formal_character_path": "characters/scene-0001-林正.yaml",
                }],
                "validation_gates": [],
                "forbidden_shortcuts": [],
            }
            task_json = task_dir / "candidate.task.json"
            task_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            task = load_task_package(project, task_json)
            sandbox = stage_task(task, root / "runs", runtime="opencode")
            candidate = sandbox.workspace / "drafts" / "candidates" / "scene_0001-platform-agent.json"
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_text(json.dumps({"new_character_register": []}, ensure_ascii=False), encoding="utf-8")
            character = sandbox.workspace / "characters" / "candidates" / "scene-0001-林正.json"
            character.parent.mkdir(parents=True, exist_ok=True)
            character.write_text("{}\n", encoding="utf-8")

            changes = canonicalize_task_outputs(task, sandbox)
            normalized = json.loads(candidate.read_text(encoding="utf-8"))

            self.assertTrue(changes)
            self.assertEqual(normalized["new_character_register"]["status"], "candidates_ready")
            self.assertEqual(normalized["new_character_register"]["introduced"][0]["candidate_path"], "characters/candidates/scene-0001-林正.json")


if __name__ == "__main__":
    unittest.main()
