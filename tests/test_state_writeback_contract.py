import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ruamel.yaml import YAML

from literary_engineering_studio_engine.agent_tasks import write_agent_completion_marker
from literary_engineering_studio_engine.approval import record_workflow_approval
from literary_engineering_studio_engine.character_state_apply import apply_character_state_patch, state_patch_writeback_status
from literary_engineering_studio_engine.character_state_evolver import build_character_state_patch
from literary_engineering_studio_engine.workflow.state_scene import (
    _state_patch_review_step,
    _state_patch_writeback_step,
)
from literary_engineering_studio_engine.workflow.audit.scene_completion import (
    add_scene_completion_gates,
)


class StateWritebackContractTests(unittest.TestCase):
    def test_indentationless_yaml_alias_routes_change_to_declared_character(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scenes").mkdir(parents=True)
            (root / "scenes" / "scene_0001.yaml").write_text(
                "scene_id: scene_0001\nparticipants:\n- 叙述者\n",
                encoding="utf-8",
            )
            (root / "characters").mkdir(parents=True)
            (root / "characters" / "narrator.yaml").write_text(
                "character_id: narrator\nname: 我\naliases:\n- 叙述者\nrole: 主角\n",
                encoding="utf-8",
            )
            draft = root / "drafts" / "scenes" / "scene_0001.md"
            draft.parent.mkdir(parents=True)
            draft.write_text("## 正文草稿\n\n叙述者承认自己数错了。\n", encoding="utf-8")
            composition = root / "drafts" / "compositions" / "scene_0001_composition.json"
            composition.parent.mkdir(parents=True)
            composition.write_text(
                json.dumps(
                    {"writeback_candidates": {"character_changes": ["叙述者承认自己数错了。"]}},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = build_character_state_patch(root)
            payload = json.loads(result.json_path.read_text(encoding="utf-8"))

            self.assertEqual([item["character_id"] for item in payload["characters"]], ["narrator"])
            self.assertEqual(payload["unresolved_changes"], [])

    def test_explicitly_not_yet_realized_change_is_deferred_not_written_back(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scenes").mkdir(parents=True)
            (root / "scenes" / "scene_0001.yaml").write_text(
                "scene_id: scene_0001\nparticipants: [叙述者]\n",
                encoding="utf-8",
            )
            (root / "characters").mkdir(parents=True)
            (root / "characters" / "narrator.yaml").write_text(
                "character_id: narrator\nname: 叙述者\nrole: 主角\n",
                encoding="utf-8",
            )
            draft = root / "drafts" / "scenes" / "scene_0001.md"
            draft.parent.mkdir(parents=True)
            draft.write_text("## 正文草稿\n\n叙述者仍不肯承认结果。\n", encoding="utf-8")
            composition = root / "drafts" / "compositions" / "scene_0001_composition.json"
            composition.parent.mkdir(parents=True)
            deferred = "叙述者的道德线转向允许自己数对一次，尚未在本场景内实际落地。"
            composition.write_text(
                json.dumps(
                    {"writeback_candidates": {"character_changes": [deferred]}},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = build_character_state_patch(root)
            payload = json.loads(result.json_path.read_text(encoding="utf-8"))

            self.assertEqual(payload["characters"], [])
            self.assertEqual(payload["unresolved_changes"], [])
            self.assertEqual(payload["source_changes"]["next_scene_inputs"], [deferred])
            self.assertEqual(state_patch_writeback_status(root, "scene_0001")["status"], "not_required")

    def test_symbolic_protagonist_does_not_match_secondary_protagonist(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scenes").mkdir(parents=True)
            (root / "scenes" / "scene_0001.yaml").write_text(
                'scene_id: scene_0001\nparticipants: ["主角", "林曦"]\n',
                encoding="utf-8",
            )
            (root / "characters").mkdir(parents=True)
            (root / "characters" / "lin-huan.yaml").write_text(
                'character_id: lin-huan\nname: 林桓\nrole: 主角——轨道维修员\n',
                encoding="utf-8",
            )
            (root / "characters" / "lin-xi.yaml").write_text(
                'character_id: lin-xi\nname: 林曦\nrole: 次要主角——往访工程师\n',
                encoding="utf-8",
            )
            draft = root / "drafts" / "scenes" / "scene_0001.md"
            draft.parent.mkdir(parents=True)
            draft.write_text("## 正文草稿\n\n林桓决定烧掉返航冗余。\n", encoding="utf-8")
            composition = root / "drafts" / "compositions" / "scene_0001_composition.json"
            composition.parent.mkdir(parents=True)
            composition.write_text(
                json.dumps(
                    {"writeback_candidates": {"character_changes": ["主角把自身存活押进燃料表。"]}},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = build_character_state_patch(root)
            payload = json.loads(result.json_path.read_text(encoding="utf-8"))
            by_id = {item["character_id"]: item for item in payload["characters"]}

            self.assertIn("lin-huan", by_id)
            self.assertNotIn("lin-xi", by_id)

    def test_symbolic_protagonist_alias_routes_named_change_to_protagonist(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scenes").mkdir(parents=True)
            (root / "scenes" / "scene_0001.yaml").write_text(
                'scene_id: scene_0001\nparticipants: ["主角", "调度员"]\n',
                encoding="utf-8",
            )
            (root / "characters").mkdir(parents=True)
            (root / "characters" / "protagonist.yaml").write_text(
                'character_id: protagonist\nname: 沈岸\naliases: [维修员]\nrole: 主线主角\n',
                encoding="utf-8",
            )
            (root / "characters" / "dispatcher.yaml").write_text(
                'character_id: dispatcher\nname: 调度员\nrole: 配角\n',
                encoding="utf-8",
            )
            draft = root / "drafts" / "scenes" / "scene_0001.md"
            draft.parent.mkdir(parents=True)
            draft.write_text("## 正文草稿\n\n沈岸烧掉第一笔返航余量。\n", encoding="utf-8")
            composition = root / "drafts" / "compositions" / "scene_0001_composition.json"
            composition.parent.mkdir(parents=True)
            composition.write_text(
                json.dumps(
                    {
                        "writeback_candidates": {
                            "character_changes": ["沈岸从等待确证转为承担风险。"],
                            "relationship_changes": ["调度员因越权烧燃而提高了对沈岸的压力。"],
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = build_character_state_patch(root, agent_tasks=True)
            payload = json.loads(result.json_path.read_text(encoding="utf-8"))

            by_id = {item["character_id"]: item for item in payload["characters"]}
            self.assertIn("protagonist", by_id)
            self.assertIn("dispatcher", by_id)
            self.assertEqual(
                by_id["protagonist"]["proposed_updates"]["arc"]["candidate_changes"],
                ["沈岸从等待确证转为承担风险。"],
            )
            self.assertEqual(
                by_id["dispatcher"]["proposed_updates"]["arc"]["candidate_changes"],
                [],
            )

    def test_unattributed_change_stays_unresolved_instead_of_guessing_only_active_character(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scenes").mkdir(parents=True)
            (root / "scenes" / "scene_0001.yaml").write_text(
                "scene_id: scene_0001\nparticipants: [李]\n",
                encoding="utf-8",
            )
            (root / "characters").mkdir(parents=True)
            (root / "characters" / "li.yaml").write_text("character_id: li\nname: 李\n", encoding="utf-8")
            draft = root / "drafts" / "scenes" / "scene_0001.md"
            draft.parent.mkdir(parents=True)
            draft.write_text("## 正文草稿\n\n有人改变了决定。\n", encoding="utf-8")
            composition = root / "drafts" / "compositions" / "scene_0001_composition.json"
            composition.parent.mkdir(parents=True)
            composition.write_text(
                json.dumps({"writeback_candidates": {"character_changes": ["从等待转为行动。"]}}, ensure_ascii=False),
                encoding="utf-8",
            )

            result = build_character_state_patch(root)
            payload = json.loads(result.json_path.read_text(encoding="utf-8"))

            self.assertEqual(payload["characters"], [])
            self.assertEqual(payload["unresolved_changes"][0]["text"], "从等待转为行动。")

    def test_equivalent_state_patch_rebuild_preserves_digest_and_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scenes").mkdir(parents=True)
            (root / "scenes" / "scene_0001.yaml").write_text(
                "scene_id: scene_0001\nparticipants: [李]\n",
                encoding="utf-8",
            )
            (root / "characters").mkdir(parents=True)
            (root / "characters" / "li.yaml").write_text("character_id: li\nname: 李\n", encoding="utf-8")
            draft = root / "drafts" / "scenes" / "scene_0001.md"
            draft.parent.mkdir(parents=True)
            draft.write_text("## 正文草稿\n\n李决定留下。\n", encoding="utf-8")
            composition = root / "drafts" / "compositions" / "scene_0001_composition.json"
            composition.parent.mkdir(parents=True)
            composition.write_text(
                json.dumps({"writeback_candidates": {"character_changes": ["李决定留下。"]}}, ensure_ascii=False),
                encoding="utf-8",
            )

            first = build_character_state_patch(root, agent_tasks=True)
            digest = hashlib.sha256(first.json_path.read_bytes()).hexdigest()
            review = first.json_path.with_name("scene_0001_state_patch_review.json")
            review.write_text(json.dumps({"status": "complete", "state_patch_sha256": digest}), encoding="utf-8")
            second = build_character_state_patch(root, agent_tasks=True)

            self.assertEqual(hashlib.sha256(second.json_path.read_bytes()).hexdigest(), digest)
            self.assertEqual(json.loads(review.read_text(encoding="utf-8"))["status"], "complete")

    def test_structured_composition_changes_cannot_collapse_into_empty_state_patch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scenes").mkdir(parents=True)
            (root / "scenes" / "scene_0001.yaml").write_text(
                "scene_id: scene_0001\nparticipants:\n  - li\n",
                encoding="utf-8",
            )
            (root / "characters").mkdir(parents=True)
            (root / "characters" / "li.yaml").write_text(
                "character_id: li\nname: 李\nstate:\n  known_facts: []\narc: {}\n",
                encoding="utf-8",
            )
            (root / "drafts" / "scenes").mkdir(parents=True)
            (root / "drafts" / "scenes" / "scene_0001.md").write_text(
                "## 正文草稿\n\n李推开门，决定独自进入旧楼。\n",
                encoding="utf-8",
            )
            composition = root / "drafts" / "compositions" / "scene_0001_composition.json"
            composition.parent.mkdir(parents=True)
            composition.write_text(
                json.dumps(
                    {
                        "writeback_candidates": {
                            "character_changes": ["李决定独自进入旧楼。"],
                            "relationship_changes": [],
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = build_character_state_patch(root)
            payload = json.loads(result.json_path.read_text(encoding="utf-8"))

            self.assertEqual(len(payload["characters"]), 1)
            self.assertIn(
                "drafts/compositions/scene_0001_composition.json",
                payload["source_change_sources"],
            )
            self.assertEqual(
                state_patch_writeback_status(root, "scene_0001")["status"],
                "semantic_incomplete",
            )

    def test_empty_old_patch_is_stale_when_composition_declares_state_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            patch = root / "characters" / "state_patches" / "scene_0001_state_patch.json"
            patch.parent.mkdir(parents=True)
            patch.write_text(
                json.dumps({"scene_id": "scene_0001", "characters": [], "unresolved_changes": []}),
                encoding="utf-8",
            )
            composition = root / "drafts" / "compositions" / "scene_0001_composition.json"
            composition.parent.mkdir(parents=True)
            composition.write_text(
                json.dumps({"writeback_candidates": {"character_changes": ["李改变决定。"]}}, ensure_ascii=False),
                encoding="utf-8",
            )

            status = state_patch_writeback_status(root, "scene_0001")

            self.assertEqual(status["status"], "stale_source")
            self.assertIn("composition", status["message"])

    def test_workflow_exposes_concrete_state_approval_apply_or_review_steps(self):
        cases = {
            "needs_revision": "state-patch-json",
            "needs_approval": "state-patch-approval",
            "pending_apply": "state-apply",
            "missing": "state-agent-task",
            "semantic_incomplete": "state-agent-task",
            "pass": "state-writeback",
            "rejected": "state-writeback",
        }
        for status, expected_key in cases.items():
            with self.subTest(status=status), patch(
                "literary_engineering_studio_engine.workflow.state_scene.state_patch_writeback_status",
                return_value={"status": status, "patch": "characters/state_patches/scene_0001_state_patch.json"},
            ):
                step = _state_patch_writeback_step(Path("C:/example"), "scene_0001")
                self.assertEqual(step["key"], expected_key)
                self.assertEqual(step["display_key"], "state-writeback")

    def test_unresolved_patch_returns_to_patch_rebuild_not_completed_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            patch_path = root / "characters" / "state_patches" / "scene_0001_state_patch.json"
            patch_path.parent.mkdir(parents=True)
            patch_path.write_text(
                json.dumps(
                    {
                        "scene_id": "scene_0001",
                        "characters": [],
                        "unresolved_changes": [{"kind": "character_changes", "text": "某人改变决定。"}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            status = state_patch_writeback_status(root, "scene_0001")
            step = _state_patch_writeback_step(root, "scene_0001")

            self.assertEqual(status["status"], "needs_revision")
            self.assertEqual(step["key"], "state-patch-json")
            self.assertIn("instead of repeating semantic review", step["message"])

    def test_empty_state_patch_skips_semantic_review_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            patch_path = root / "characters" / "state_patches" / "scene_0001_state_patch.json"
            patch_path.parent.mkdir(parents=True)
            patch_path.write_text(
                json.dumps(
                    {"scene_id": "scene_0001", "characters": [], "unresolved_changes": []},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            step = _state_patch_review_step(root, "scene_0001")

            self.assertEqual(step["status"], "pass")
            self.assertIn("not required", step["message"])

    def test_route_audit_does_not_require_review_receipt_for_empty_state_patch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            patch_path = root / "characters" / "state_patches" / "scene_0001_state_patch.json"
            patch_path.parent.mkdir(parents=True)
            patch_path.write_text(
                json.dumps(
                    {"scene_id": "scene_0001", "characters": [], "unresolved_changes": []},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            patch_path.with_suffix(".md").write_text("# No durable state change\n", encoding="utf-8")
            gates: list[dict[str, str]] = []

            add_scene_completion_gates(gates, root, "scene_0001", {})

            gate = next(item for item in gates if item["key"] == "scene_0001:state-agent-task-complete")
            self.assertEqual(gate["status"], "pass")
            self.assertIn("not required", gate["message"])

    def test_state_apply_gate_imports_the_modular_writeback_status(self):
        from literary_engineering_studio_engine.routes.scene.gates import _state_gate_validation

        with tempfile.TemporaryDirectory() as temporary:
            errors, notes = _state_gate_validation(
                Path(temporary),
                {"current_state": "state-apply", "scene_id": "scene_0001"},
            )

        self.assertTrue(errors)
        self.assertEqual(notes, [])
        self.assertNotIn("ModuleNotFoundError", "\n".join(errors))

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

            record_workflow_approval(root, patch.stem, "revise", subject_sha256=digest)
            self.assertEqual(state_patch_writeback_status(root, "scene_0001")["status"], "needs_revision")
            self.assertEqual(_state_patch_writeback_step(root, "scene_0001")["key"], "state-patch-json")
            with self.assertRaises(RuntimeError):
                apply_character_state_patch(root, patch=patch, approval_run_id=patch.stem)

            record_workflow_approval(root, patch.stem, "approve", subject_sha256=digest)
            self.assertEqual(state_patch_writeback_status(root, "scene_0001")["status"], "pending_apply")
            result = apply_character_state_patch(root, patch=patch, approval_run_id=patch.stem)

            self.assertEqual(result.status, "applied")
            self.assertIn("见过潮线", character.read_text(encoding="utf-8"))
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["patch_sha256"], digest)
            self.assertTrue(manifest["approval_matches_patch"])
            self.assertEqual(state_patch_writeback_status(root, "scene_0001")["status"], "pass")

    def test_relationship_deltas_do_not_corrupt_structured_relationships(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            character = root / "characters" / "li.yml"
            character.parent.mkdir(parents=True)
            character.write_text(
                "character_id: li\n"
                "name: 李\n"
                "relationships:\n"
                "  - character_id: zhou\n"
                "    relation: 合作者\n"
                "  - 李与周形成受审计约束的合作。\n"
                "state:\n"
                "  known_facts: []\n"
                "arc: {}\n",
                encoding="utf-8",
            )
            patch_path = root / "characters" / "state_patches" / "scene_0001_state_patch.json"
            patch_path.parent.mkdir(parents=True)
            patch_payload = {
                "scene_id": "scene_0001",
                "characters": [
                    {
                        "character_id": "li",
                        "name": "李",
                        "file": "characters/li.yml",
                        "proposed_updates": {
                            "state": {"known_facts_add": [], "resources_add": [], "location_note": "", "health_note": ""},
                            "arc": {"candidate_changes": []},
                            "relationships": {"candidate_changes": ["李与周形成受审计约束的合作。"]},
                        },
                    }
                ],
                "unresolved_changes": [],
            }
            patch_path.write_text(json.dumps(patch_payload, ensure_ascii=False), encoding="utf-8")
            digest = hashlib.sha256(patch_path.read_bytes()).hexdigest()
            review = patch_path.with_name("scene_0001_state_patch_review.json")
            review.write_text(json.dumps({
                "schema": "literary-engineering-workbench/state-patch-review/v1",
                "scene_id": "scene_0001",
                "status": "complete",
                "source_artifact": "characters/state_patches/scene_0001_state_patch.json",
                "state_patch_sha256": digest,
                "evidence_paths": ["drafts/scenes/scene_0001.md"],
                "verdict": "pass",
                "findings": ["关系变化有正文依据。"],
                "approval_recommendation": "approve",
                "required_changes": [],
            }, ensure_ascii=False), encoding="utf-8")
            sidecar = patch_path.with_suffix(".agent_tasks.md")
            sidecar.write_text("# state task\n", encoding="utf-8")
            write_agent_completion_marker(sidecar, root=root, handled_by="reviewer-session")
            record_workflow_approval(root, patch_path.stem, "approve", subject_sha256=digest)

            first = apply_character_state_patch(root, patch=patch_path, approval_run_id=patch_path.stem)
            second = apply_character_state_patch(root, patch=patch_path, approval_run_id=patch_path.stem)
            payload = YAML(typ="safe").load(character.read_text(encoding="utf-8"))

            self.assertEqual(first.update_count, 2)
            self.assertEqual(second.update_count, 0)
            self.assertTrue(all(isinstance(item, dict) for item in payload["relationships"]))
            self.assertEqual(payload["state"]["relationship_changes"], ["李与周形成受审计约束的合作。"])


if __name__ == "__main__":
    unittest.main()
