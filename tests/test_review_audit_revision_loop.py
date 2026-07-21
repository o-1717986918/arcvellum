from pathlib import Path
import hashlib
import json
import tempfile
import unittest

from literary_engineering_studio.contracts import TASK_SCHEMA, load_task_package
from literary_engineering_studio.sandbox import stage_task
from literary_engineering_studio.task_preflight import COMPLETION_SCHEMA, validate_task_outputs
from literary_engineering_studio_engine.agent_tasks import write_agent_completion_marker
import literary_engineering_studio_engine.task_registry as task_registry


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
            (review_dir / "canon_review.md").write_text("# Canon Review\n\n需要修订。\n", encoding="utf-8")
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

            blueprint = task_registry._review_audit_blueprint_for_state(project, "canon-review-pass", "repair")
            self.assertEqual(blueprint["repair_targets"], ["canon/world_rules.yaml"])
            before = hashlib.sha256(target.read_bytes()).hexdigest()
            task_json = self._write_task(
                project,
                {
                    "task_id": "canon-fix",
                    "route": "review-and-audit",
                    "current_state": "canon-review-pass",
                    "task_type": "platform-agent-revision",
                    "repair_targets": ["canon/world_rules.yaml"],
                    "repair_target_sha256_before_revision": {"canon/world_rules.yaml": before},
                    "expected_outputs": blueprint["expected_outputs"],
                    "validation_gates": blueprint["validation_gates"],
                },
                "canon-fix",
            )
            task = load_task_package(project, task_json)
            sandbox = stage_task(task, root / "runs", runtime="opencode")
            (sandbox.workspace / "canon" / "world_rules.yaml").write_text("rules:\n  - power_has_cost\n", encoding="utf-8")
            reset = _canon_review("revise_required")
            reset.update({"conclusion": "recheck_required", "applied_repair_actions": [{"target_path": "canon/world_rules.yaml", "evidence": "added cost"}]})
            (sandbox.workspace / "reviews" / "agent" / "canon_review.json").write_text(json.dumps(reset, ensure_ascii=False), encoding="utf-8")
            (sandbox.workspace / "reviews" / "agent" / "canon_review.md").write_text("# 已修复，等待复审\n", encoding="utf-8")
            (sandbox.workspace / "reviews" / "agent" / "canon_review.agent_completion.json").write_text(
                json.dumps({"schema": COMPLETION_SCHEMA, "source_task": "reviews/agent/canon_review.agent_tasks.md", "status": "recheck_required", "handled_by": "revision-agent", "completed_at": "2026-07-21T00:10:00Z", "expected_artifacts_checked": False, "notes": []}, ensure_ascii=False),
                encoding="utf-8",
            )

            result = validate_task_outputs(task, sandbox)

            self.assertTrue(result.passed, result.as_dict())


if __name__ == "__main__":
    unittest.main()
