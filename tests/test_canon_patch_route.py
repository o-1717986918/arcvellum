from pathlib import Path
import hashlib
import json
import tempfile
import unittest

from literary_engineering_studio_engine.agent_tasks import write_agent_completion_marker
from literary_engineering_studio_engine.approval import record_workflow_approval
from literary_engineering_studio_engine.canon_evolver import apply_canon_patch
import literary_engineering_studio_engine.task_registry as task_registry
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
    def test_patch_moves_from_content_bound_approval_to_apply_and_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            patch = _write_patch(root)

            awaiting = _review_audit_state(root)
            self.assertEqual(awaiting["current_step"], "canon-patch-approval")
            self.assertEqual(awaiting["patch_id"], patch.stem)
            approval_task = task_registry._build_review_audit_task_payload(root, "review-and-audit", awaiting)
            self.assertEqual(approval_task["task_type"], "human-approval-boundary")

            digest = hashlib.sha256(patch.read_bytes()).hexdigest()
            record_workflow_approval(root, patch.stem, "approve", subject_sha256=digest)
            approved = _review_audit_state(root)
            self.assertEqual(approved["current_step"], "canon-patch-apply")

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
            task = task_registry._build_review_audit_task_payload(root, "review-and-audit", state)
            self.assertEqual(task["task_type"], "platform-agent-revision")
            self.assertIn(patch.relative_to(root).as_posix(), task["repair_targets"])
            self.assertEqual(task["repair_target_sha256_before_revision"][patch.relative_to(root).as_posix()], digest)


if __name__ == "__main__":
    unittest.main()
