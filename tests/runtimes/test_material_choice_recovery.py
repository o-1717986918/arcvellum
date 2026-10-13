"""Material corrections preserve creative work and do not repeat paid attempts."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from literary_engineering_studio.runtime.role_conversation import RoleConversationResult
from literary_engineering_studio.runtimes.pi_scene_transaction import PiSceneTransactionRuntime
from literary_engineering_studio.runtimes.scene_creator_material_policy import (
    MaterialSelectionError, material_selection_error, repair_material_choice,
)
from tests.test_lean_kernel_v2_pi_runtime import _brief


class MaterialChoiceRecoveryTests(unittest.TestCase):
    def test_archive_selection_notes_before_materials_do_not_become_candidate_decisions(self):
        from literary_engineering_studio.runtimes.natural_selection_pending import archive_notes_before_materials
        source = '我采用档案中把天气想成船的性情，填入角色卡。'
        payload = {'prose': '', 'material_requests': [{'kind': 'actor'}],
            'decision_summary': source, 'material_decisions': [{'candidate_id': 'invented-archive-id', 'decision': 'use', 'reason': source}]}
        result = archive_notes_before_materials(payload, source, {'available_material_ids': []})
        self.assertEqual(result['material_decisions'], [])
        self.assertEqual(result['decision_summary'], source)
        self.assertEqual(result['archive_selection_transport_notes'], payload['material_decisions'])
        self.assertEqual(archive_notes_before_materials(payload, source, {'available_material_ids': ['v2:real:1']}), payload)
        self.assertEqual(archive_notes_before_materials(payload, source + 'invented-archive-id', {'available_material_ids': []}), payload)
    def test_correction_only_changes_material_decisions(self):
        original = {"prose": "她把信压在杯底。", "scene_delta": {"next_handoff": ["等她抬头"]},
                    "material_decisions": [{"candidate_id": "invented", "decision": "adopt", "reason": "停顿"}]}
        corrected = {"material_decisions": [{"candidate_id": "t1:1", "decision": "adapt", "reason": "留下停顿"}],
                     "prose": "另一篇正文。", "scene_delta": {}}
        invoke = Mock(return_value=corrected)
        result, prompt = repair_material_choice(original, "场景资料", phase="material-ready",
            candidate_ids=["t1:1"], prior_decisions=[], invoke=invoke)
        self.assertEqual(result["prose"], original["prose"])
        self.assertEqual(result["scene_delta"], original["scene_delta"])
        self.assertEqual(original["material_decisions"][0]["candidate_id"], "invented")
        self.assertEqual(result["material_decisions"], corrected["material_decisions"])
        self.assertIn('已提供的候选 ID：["t1:1"]', prompt)
        self.assertIn("unknown candidate_id: 'invented'", prompt)
        self.assertIn(original["prose"], prompt)
        invoke.assert_called_once()

    def test_valid_decision_has_no_correction_cost(self):
        payload = {"prose": "一场日常。", "material_decisions": [
            {"candidate_id": "t1:1", "decision": "discard", "reason": "此处保留沉默"}]}
        invoke = Mock()
        result, _ = repair_material_choice(payload, "场景资料", phase="material-ready",
            candidate_ids=["t1:1"], prior_decisions=[], invoke=invoke)
        self.assertEqual(result, payload)
        invoke.assert_not_called()

    def test_invalid_choice_is_reported_and_one_correction_exhausts(self):
        payload = {"material_decisions": [{"candidate_id": "t1:1", "decision": "adopt", "reason": "停顿"}]}
        self.assertIn("decision 'adopt'", material_selection_error(payload, ["t1:1"], []))
        invoke = Mock(return_value=payload)
        with self.assertRaisesRegex(MaterialSelectionError, "valid choices"):
            repair_material_choice(payload, "资料", phase="material-ready", candidate_ids=["t1:1"],
                                   prior_decisions=[], invoke=invoke)
        invoke.assert_called_once()

    def test_blocked_compatibility_transaction_reuses_body_and_correction(self):
        class Gateway:
            calls = 0

            def run(self, _root, _prompt, **_kwargs):
                self.calls += 1
                payload = ({"material_requests": [{"kind": "environment", "cue": "雨停了",
                    "purpose": "保留雨后停顿", "scene_moment": "她抬头时"}]} if self.calls == 1 else
                    {"prose": "雨停了，她仍坐着。", "decision_summary": "保留停顿", "scene_delta": {},
                     "material_decisions": [{"candidate_id": "missing", "decision": "adapt", "reason": "停顿"}]})
                return RoleConversationResult("pi-worker", "test", "test/model", json.dumps(payload, ensure_ascii=False))

        materials = "素材\n" + json.dumps({"environment_candidates": {"passages": [
            {"candidate_id": "environment:1", "beat_id": "b1", "description": "雨停了。"}]}})
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            gateway = Gateway()
            runtime = PiSceneTransactionRuntime({"application": {"scene_performance_agents": {"enabled": True}}},
                project_root=root, data_root=root / "data", gateway=gateway)
            with patch("literary_engineering_studio.runtimes.pi_scene_transaction.fulfill_scene_material_requests", return_value=materials):
                for _ in range(2):
                    with self.assertRaisesRegex(MaterialSelectionError, "unknown candidate_id: 'missing'"):
                        runtime.create_scene("tx-blocked", _brief())
            self.assertEqual(gateway.calls, 3)
            self.assertEqual(len(list((root / "data/scene-transactions/tx-blocked/creator-answers").glob("*.md"))), 3)


if __name__ == "__main__":
    unittest.main()
