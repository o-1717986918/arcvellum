from pathlib import Path
import hashlib
import json
import tempfile
import unittest

from literary_engineering_studio_engine.agent_tasks import write_agent_completion_marker
from literary_engineering_studio_engine.approval import record_workflow_approval
from literary_engineering_studio_engine.canon_evolver import apply_canon_patch, canon_writeback_status
from literary_engineering_studio_engine.review_audit_route import build_task_payload
from literary_engineering_studio_engine.semantic_task_contracts import semantic_artifact_relative_path
from literary_engineering_studio_engine import task_registry
from literary_engineering_studio_engine.workflow_state import _review_audit_state


def _write_patch(root: Path) -> Path:
    patch = root / "canon" / "patches" / "scene_0001_canon_patch.json"
    patch.parent.mkdir(parents=True)
    patch.write_text(
        json.dumps(
            {
                "schema": "literary-engineering-workbench/canon-patch-candidate/v0.1",
                "scene_id": "scene_0001",
                "canon_change": True,
                "no_canon_change_reason": "",
                "items": [
                    {
                        "type": "world_rule",
                        "summary": "越过潮线会留下可追踪的盐痕。",
                        "source_evidence": ["drafts/scenes/scene_0001.md#潮线"],
                        "target_files": ["canon/world_rules.yaml"],
                        "risk_level": "medium",
                        "requires_user_approval": True,
                    }
                ],
                "requires_user_approval": True,
                "status": "candidate",
                "applied": False,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    patch.with_suffix(".md").write_text("# Canon Patch\n\n潮线规则候选。\n", encoding="utf-8")
    sidecar = patch.with_suffix(".agent_tasks.md")
    sidecar.write_text("# canon evolve\n", encoding="utf-8")
    write_agent_completion_marker(sidecar, root=root, handled_by="main-agent")
    return patch


class CanonPatchRouteTests(unittest.TestCase):
    def _write_scene_canon_evidence(self, root: Path, patch: Path) -> None:
        candidate = root / "drafts/candidates/scene_0001-platform-agent.md"
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text("正文候选。\n", encoding="utf-8")
        promotion = root / "drafts/promotions/scene_0001_promotion.json"
        promotion.parent.mkdir(parents=True, exist_ok=True)
        promotion.write_text(
            json.dumps(
                {
                    "candidate": candidate.relative_to(root).as_posix(),
                    "draft_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
                    "canon_writeback": {"canon_change": True, "no_canon_change_reason": ""},
                }
            ),
            encoding="utf-8",
        )
        review = root / semantic_artifact_relative_path("canon-agent-task", "scene_0001")
        review.write_text(
            json.dumps(
                {
                    "schema": "literary-engineering-workbench/canon-patch-review/v1",
                    "scene_id": "scene_0001",
                    "status": "complete",
                    "source_artifact": patch.relative_to(root).as_posix(),
                    "evidence_paths": [candidate.relative_to(root).as_posix()],
                    "findings": [],
                    "canon_patch_sha256": hashlib.sha256(patch.read_bytes()).hexdigest(),
                    "verdict": "pass",
                    "approval_recommendation": "approve",
                    "required_changes": [],
                }
            ),
            encoding="utf-8",
        )

    def test_candidate_generation_gate_does_not_require_its_future_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_patch(root)
            promotion = root / "drafts/promotions/scene_0001_promotion.json"
            promotion.parent.mkdir(parents=True)
            promotion.write_text(
                json.dumps(
                    {
                        "candidate": "drafts/candidates/scene_0001-platform-agent.md",
                        "canon_writeback": {
                            "canon_change": True,
                            "no_canon_change_reason": "",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            candidate = canon_writeback_status(root, "scene_0001", require_review=False)
            reviewed = canon_writeback_status(root, "scene_0001", require_review=True)

            self.assertEqual(candidate["status"], "pass")
            self.assertIn("independent review", candidate["message"])
            self.assertNotEqual(reviewed["status"], "pass")

    def test_patch_moves_from_content_bound_approval_to_apply_and_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            patch = _write_patch(root)

            awaiting = _review_audit_state(root)
            self.assertEqual(awaiting["current_step"], "canon-patch-approval")
            self.assertEqual(awaiting["patch_id"], patch.stem)
            approval_task = build_task_payload(root, "review-and-audit", awaiting)
            self.assertEqual(approval_task["task_type"], "human-approval-boundary")

            digest = hashlib.sha256(patch.read_bytes()).hexdigest()
            record_workflow_approval(root, patch.stem, "approve", subject_sha256=digest)
            approved = _review_audit_state(root)
            self.assertEqual(approved["current_step"], "canon-patch-apply")
            apply_task = build_task_payload(root, "review-and-audit", approved)
            self.assertIn(
                "canon/patches/scene_0001_canon_patch.agent_tasks.md",
                apply_task["source_paths"],
            )
            self.assertIn(
                "canon/patches/scene_0001_canon_patch_review.json",
                apply_task["source_paths"],
            )

            apply_canon_patch(root, patch=patch, approval_run_id=patch.stem)
            after_apply = _review_audit_state(root)
            self.assertEqual(after_apply["current_step"], "canon-lint-file")
            apply_payload = json.loads((root / "canon" / "applied" / f"{patch.stem}_apply.json").read_text(encoding="utf-8"))
            self.assertEqual(apply_payload["candidate_sha256"], digest)
            self.assertEqual(apply_payload["approval"]["subject_sha256"], digest)

    def test_revise_decision_routes_to_real_candidate_repair(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            patch = _write_patch(root)
            digest = hashlib.sha256(patch.read_bytes()).hexdigest()
            record_workflow_approval(root, patch.stem, "revise", notes="缩小规则适用范围。", subject_sha256=digest)

            state = _review_audit_state(root)
            self.assertEqual(state["current_step"], "canon-patch-revision")
            task = build_task_payload(root, "review-and-audit", state)
            self.assertEqual(task["task_type"], "platform-agent-revision")
            self.assertIn(patch.relative_to(root).as_posix(), task["repair_targets"])
            self.assertEqual(task["repair_target_sha256_before_revision"][patch.relative_to(root).as_posix()], digest)

    def test_scene_canon_status_requires_apply_and_binds_applied_patch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            patch = _write_patch(root)
            self._write_scene_canon_evidence(root, patch)

            pending = canon_writeback_status(root, "scene_0001")
            self.assertEqual(pending["status"], "needs_approval")
            digest = hashlib.sha256(patch.read_bytes()).hexdigest()
            record_workflow_approval(root, patch.stem, "approve", subject_sha256=digest)
            self.assertEqual(canon_writeback_status(root, "scene_0001")["status"], "pending_apply")

            apply_canon_patch(root, patch=patch, approval_run_id=patch.stem)
            applied = canon_writeback_status(root, "scene_0001")
            self.assertEqual(applied["status"], "pass")
            manifest = json.loads((root / applied["apply_manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["applied_patch_sha256"], hashlib.sha256(patch.read_bytes()).hexdigest())

            patch.write_text(patch.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            self.assertNotEqual(canon_writeback_status(root, "scene_0001")["status"], "pass")

    def test_scene_canon_revision_task_carries_exact_repair_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            patch = _write_patch(root)
            scene = root / "scenes/scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text("scene_id: scene_0001\n", encoding="utf-8")
            task = task_registry._build_task_payload(
                root,
                "scene-development",
                {
                    "scene_id": "scene_0001",
                    "scene": "scenes/scene_0001.yaml",
                    "current_step": "canon-patch-revision",
                    "next_action": "revise canon patch",
                },
            )
            relative = patch.relative_to(root).as_posix()
            self.assertIn(relative, task["repair_targets"])
            self.assertEqual(
                task["repair_target_sha256_before_revision"][relative],
                hashlib.sha256(patch.read_bytes()).hexdigest(),
            )

    def test_scene_handoff_is_a_deterministic_formal_task(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scene = root / "scenes/scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text("scene_id: scene_0001\n", encoding="utf-8")
            blueprint = task_registry._blueprint_for_state(
                root,
                "scene_0001",
                "scenes/scene_0001.yaml",
                "scene-handoff",
                "",
            )
            self.assertEqual(blueprint["task_type"], "deterministic-cli")
            self.assertIn("scene-handoff", blueprint["command"])
            self.assertEqual(blueprint["expected_outputs"], ["workflow/handoffs/scene_0001.json"])


if __name__ == "__main__":
    unittest.main()
