import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from literary_engineering_studio_engine.agent_tasks import write_agent_completion_marker
from literary_engineering_studio_engine.approval import record_workflow_approval
from literary_engineering_studio_engine.character_state_apply import apply_character_state_patch, state_patch_writeback_status


class StateWritebackContractTests(unittest.TestCase):
    def test_reviewed_digest_bound_patch_requires_approval_then_applies_atomically(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            character = root / "characters" / "li.yml"
            character.parent.mkdir(parents=True)
            character.write_text("character_id: li\nname: 李\nstate:\n  known_facts: []\n", encoding="utf-8")
            patch = root / "characters" / "state_patches" / "scene_0001_state_patch.json"
            patch.parent.mkdir(parents=True)
            patch_payload = {
                "scene_id": "scene_0001",
                "characters": [{"character_id": "li", "name": "李", "file": "characters/li.yml", "proposed_updates": {"state": {"known_facts_add": ["见过潮线"], "resources_add": [], "location_note": "", "health_note": ""}, "arc": {"candidate_changes": []}, "relationships": {"candidate_changes": []}}}],
                "unresolved_changes": [],
            }
            patch.write_text(json.dumps(patch_payload, ensure_ascii=False), encoding="utf-8")
            digest = hashlib.sha256(patch.read_bytes()).hexdigest()
            review = patch.with_name("scene_0001_state_patch_review.json")
            review.write_text(json.dumps({
                "schema": "literary-engineering-workbench/state-patch-review/v1",
                "scene_id": "scene_0001",
                "status": "complete",
                "source_artifact": "characters/state_patches/scene_0001_state_patch.json",
                "state_patch_sha256": digest,
                "evidence_paths": ["drafts/scenes/scene_0001.md"],
                "verdict": "pass",
                "findings": ["正文证据支持已知事实变化。"],
                "approval_recommendation": "approve",
                "required_changes": [],
            }, ensure_ascii=False), encoding="utf-8")
            sidecar = patch.with_suffix(".agent_tasks.md")
            sidecar.write_text("# state task\n", encoding="utf-8")
            write_agent_completion_marker(sidecar, root=root, handled_by="reviewer-session")

            self.assertEqual(state_patch_writeback_status(root, "scene_0001")["status"], "needs_approval")
            with self.assertRaises(RuntimeError):
                apply_character_state_patch(root, patch=patch)

            record_workflow_approval(root, patch.stem, "approve", subject_sha256=digest)
            self.assertEqual(state_patch_writeback_status(root, "scene_0001")["status"], "pending_apply")
            result = apply_character_state_patch(root, patch=patch, approval_run_id=patch.stem)

            self.assertEqual(result.status, "applied")
            self.assertIn("见过潮线", character.read_text(encoding="utf-8"))
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["patch_sha256"], digest)
            self.assertTrue(manifest["approval_matches_patch"])
            self.assertEqual(state_patch_writeback_status(root, "scene_0001")["status"], "pass")


if __name__ == "__main__":
    unittest.main()
