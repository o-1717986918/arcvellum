from pathlib import Path
import hashlib
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.contracts import TASK_SCHEMA, load_task_package
from literary_engineering_studio.sandbox import stage_task
from literary_engineering_studio.task_preflight import COMPLETION_SCHEMA, canonicalize_task_outputs, validate_task_outputs
import literary_engineering_studio_engine.task_registry as task_registry
from literary_engineering_studio_engine.candidate_promotion import _candidate_review_content_match, _human_decision_notes
from literary_engineering_studio_engine.review_ci import review_scene_draft
from literary_engineering_studio_engine.scene_revision import _prompt_manifest
from literary_engineering_studio_engine.workflow_state import _current_scene_candidate, _static_review_step
from literary_engineering_studio_engine.workflow_state import _review_step


class SceneReviewRevisionLoopTests(unittest.TestCase):
    def test_nonpass_static_review_routes_to_revision_and_stale_review_reopens(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            draft = root / "drafts" / "scenes" / "scene_0001.md"
            draft.parent.mkdir(parents=True)
            draft.write_text("## 正文草稿\n\n太短。\n", encoding="utf-8")
            result = review_scene_draft(root, draft)
            step = _static_review_step(root, "scene_0001")
            self.assertNotEqual(result.conclusion, "pass")
            self.assertEqual(step["key"], "static-revision")

            draft.write_text("## 正文草稿\n\n已经改变的正文。\n", encoding="utf-8")
            stale = _static_review_step(root, "scene_0001")
            self.assertEqual(stale["key"], "static-review")
            self.assertEqual(stale["status"], "stale")

    def test_newer_revision_candidate_supersedes_prior_promotion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = root / "drafts" / "candidates" / "scene_0001-platform-agent.md"
            original.parent.mkdir(parents=True)
            original.write_text("旧候选。\n", encoding="utf-8")
            promotion = root / "drafts" / "promotions" / "scene_0001_promotion.json"
            promotion.parent.mkdir(parents=True)
            promotion.write_text(
                json.dumps({"candidate": "drafts/candidates/scene_0001-platform-agent.md"}), encoding="utf-8"
            )
            revision = root / "drafts" / "revisions" / "scene_0001_revision.md"
            revision.parent.mkdir(parents=True)
            revision.write_text("新修订候选。\n", encoding="utf-8")
            future = promotion.stat().st_mtime_ns + 10_000_000
            os.utime(revision, ns=(future, future))

            self.assertEqual(_current_scene_candidate(root, "scene_0001"), revision)

    def test_scene_review_is_bound_to_exact_candidate_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "scene_0001.md"
            candidate.write_text("第一版正文。\n", encoding="utf-8")
            digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            self.assertTrue(_candidate_review_content_match({"candidate_sha256": digest}, candidate))
            candidate.write_text("第二版正文。\n", encoding="utf-8")
            self.assertFalse(_candidate_review_content_match({"candidate_sha256": digest}, candidate))

    def test_workflow_routes_semantic_failure_to_revision_but_infrastructure_failure_to_review(self):
        candidate = Path("C:/project/drafts/candidates/scene_0001-platform-agent.md")
        with patch("literary_engineering_studio_engine.workflow_state.candidate_review_gate", return_value={"status": "style_lint_failed", "review": "reviews/agent/scene_0001_scene_review.json", "message": "lint"}):
            revision = _review_step(Path("C:/project"), "scene_0001", candidate)
        with patch("literary_engineering_studio_engine.workflow_state.candidate_review_gate", return_value={"status": "task_incomplete", "review": "reviews/agent/scene_0001_scene_review.json", "message": "marker"}):
            review = _review_step(Path("C:/project"), "scene_0001", candidate)

        self.assertEqual(revision["key"], "candidate-revision")
        self.assertEqual(review["key"], "candidate-review")

    def test_cross_asset_review_finding_stops_for_exact_candidate_decision(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "drafts" / "candidates" / "scene_0001-platform-agent.md"
            candidate.parent.mkdir(parents=True)
            candidate.write_text("正文。\n", encoding="utf-8")
            digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            gate = {
                "status": "human_decision_required",
                "review": "reviews/agent/scene_0001_scene_review.json",
                "message": "formal age conflict",
                "candidate_sha256": digest,
            }
            with patch("literary_engineering_studio_engine.workflow_state.candidate_review_gate", return_value=gate):
                pending = _review_step(root, "scene_0001", candidate)
            self.assertEqual(pending["key"], "candidate-human-decision")
            self.assertEqual(pending["status"], "human_required")

            choices = root / "workflow" / "human_choices"
            choices.mkdir(parents=True)
            (choices / "index.jsonl").write_text(
                json.dumps(
                    {
                        "decision_type": "cross_asset_alignment",
                        "selected": "align_prose_to_formal_asset",
                        "target": {"scene_id": "scene_0001", "candidate_sha256": digest},
                    }
                ) + "\n",
                encoding="utf-8",
            )
            with patch("literary_engineering_studio_engine.workflow_state.candidate_review_gate", return_value=gate):
                routed = _review_step(root, "scene_0001", candidate)
            self.assertEqual(routed["key"], "candidate-revision")
            self.assertEqual(routed["status"], "needs_revision")

    def test_human_review_resolution_is_not_treated_as_normal_style_note(self):
        notes = _human_decision_notes(
            {
                "warnings": [
                    {"id": "W-001", "description": "formal age conflict", "resolution": "needs_human_review", "blocks_pass": True},
                    {"id": "W-002", "description": "ordinary warning", "resolution": "external_dependency", "blocks_pass": False},
                ]
            }
        )
        self.assertEqual(notes, ["W-001: formal age conflict"])

    def test_non_pass_scene_review_is_recordable_for_revision_routing(self):
        with patch("literary_engineering_studio_engine.task_registry.candidate_review_gate", return_value={"status": "notes_unresolved", "message": "revise"}):
            errors = task_registry._candidate_review_gate_errors(Path("C:/project"), {"scene_id": "scene_0001"}, Path("candidate.md"), require_pass=False)
            promotion_errors = task_registry._candidate_review_gate_errors(Path("C:/project"), {"scene_id": "scene_0001"}, Path("candidate.md"), require_pass=True)

        self.assertEqual(errors, [])
        self.assertTrue(promotion_errors)

    def test_revision_preflight_rejects_unchanged_prose_and_accepts_real_revision(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            source_rel = "drafts/candidates/scene_0001-platform-agent.md"
            candidate_rel = "drafts/revisions/scene_0001_revision.md"
            source = project / source_rel
            source.parent.mkdir(parents=True)
            source.write_text("## 正文候选\n\n她停在门口。\n", encoding="utf-8")
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            expected = [
                candidate_rel,
                "drafts/revisions/scene_0001_revision_report.md",
                "drafts/revisions/scene_0001_revision.json",
                "drafts/revisions/scene_0001_revision.prompt.json",
                "drafts/revisions/scene_0001_revision.agent_tasks.md",
                "drafts/revisions/scene_0001_revision.agent_completion.json",
            ]
            task_dir = project / "workflow" / "tasks"
            task_dir.mkdir(parents=True)
            task_md = task_dir / "revision.agent_tasks.md"
            task_md.write_text("# revision\n", encoding="utf-8")
            task_json = task_dir / "revision.json"
            task_json.write_text(
                json.dumps(
                    {
                        "schema": TASK_SCHEMA,
                        "task_id": "scene-revision",
                        "route": "scene-development",
                        "scene_id": "scene_0001",
                        "scene": "scenes/scene_0001.yaml",
                        "current_state": "candidate-revision",
                        "task_type": "platform-agent-revision",
                        "candidate": candidate_rel,
                        "revision_source": source_rel,
                        "candidate_sha256_before_revision": before,
                        "task_markdown": "workflow/tasks/revision.agent_tasks.md",
                        "required_reading": [],
                        "source_paths": [source_rel],
                        "expected_outputs": expected,
                        "validation_gates": ["revision candidate differs"],
                        "forbidden_shortcuts": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            task = load_task_package(project, task_json)
            sandbox = stage_task(task, root / "runs", runtime="opencode")
            for relative in expected:
                path = sandbox.workspace / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                if relative.endswith("_revision.md"):
                    path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
                elif relative.endswith("_revision.json"):
                    path.write_text(json.dumps({"schema": "literary-engineering-workbench/scene-revision/v0.1", "scene_id": "scene_0001", "revision_actions_applied": ["修正动作"], "anti_evasion_protocol_applied": True, "evasion_risks_unresolved": [], "ready_for_review": False}, ensure_ascii=False), encoding="utf-8")
                elif relative.endswith("agent_completion.json"):
                    path.write_text(json.dumps({"schema": COMPLETION_SCHEMA, "source_task": "drafts/revisions/scene_0001_revision.agent_tasks.md", "status": "complete", "handled_by": "main-agent", "completed_at": "2026-07-21T00:00:00Z", "expected_artifacts_checked": True, "notes": []}, ensure_ascii=False), encoding="utf-8")
                elif relative.endswith(".json"):
                    path.write_text("{}\n", encoding="utf-8")
                else:
                    path.write_text("# artifact\n", encoding="utf-8")

            rejected = validate_task_outputs(task, sandbox)
            self.assertFalse(rejected.passed)
            self.assertTrue(any(issue.code == "scene-revision-invalid" for issue in rejected.issues))

            (sandbox.workspace / candidate_rel).write_text("## 修订正文候选\n\n她没有停。门已经从里面打开。\n", encoding="utf-8")
            accepted = validate_task_outputs(task, sandbox)
            self.assertTrue(accepted.passed, accepted.as_dict())

    def test_revision_prompt_and_manifest_preserve_reader_and_rhythm_contracts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text("scene_id: scene_0001\nchapter_id: chapter_0001\n", encoding="utf-8")
            draft = root / "drafts" / "candidates" / "scene_0001-platform-agent.md"
            draft.parent.mkdir(parents=True)
            draft.write_text("## 正文候选\n\n她推开了门。\n", encoding="utf-8")
            context = root / "memory" / "context_packets" / "scene_0001.md"
            context.parent.mkdir(parents=True)
            context.write_text("# context\n", encoding="utf-8")
            trace = context.with_suffix(".trace.json")
            trace.write_text("{}\n", encoding="utf-8")
            review = root / "reviews" / "agent" / "scene_0001_scene_review.json"
            review.parent.mkdir(parents=True)
            review.write_text(json.dumps({"conclusion": "pass_with_notes"}), encoding="utf-8")
            candidate = root / "drafts" / "revisions" / "scene_0001_revision.md"
            report = candidate.with_name("scene_0001_revision_report.md")
            manifest = candidate.with_suffix(".json")

            prompt = _prompt_manifest(
                root, "scene_0001", scene, draft, context, trace, review,
                [scene, draft, context, trace, review], candidate, report, manifest,
            )
            standards = prompt["generation_standards"]
            self.assertIn("reader_experience_contract", standards)
            self.assertIn("narrative_rhythm_contract", standards)
            self.assertIn(standards["reader_experience_contract"]["status"], {"not_required", "pass", "blocked", "incomplete"})
            self.assertIn(standards["narrative_rhythm_contract"]["status"], {"defaulted", "pass", "incomplete"})


if __name__ == "__main__":
    unittest.main()
