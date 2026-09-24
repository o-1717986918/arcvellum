from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.runtimes.pi_scene_transaction import PiSceneTransactionRuntime
from literary_engineering_studio.runtimes.scene_performance_ownership import audit_visible_actions, unlicensed_scene_dialogue
from literary_engineering_studio_engine.public.literary import CreativeResult, SceneDelta
from tests.test_lean_kernel_v2_pi_runtime import _brief


def _materials() -> str:
    return "一级角色素材\n" + json.dumps({"actor_entries": [
        {"entry_id": "a1", "speaker": "character/protagonist", "spoken": "信……我拿的。你拿去看。", "first_person_action": "我没碰信。", "private_impulse": "别让人知道我的念头。"},
        {"entry_id": "a2", "speaker": "character/sister", "spoken": "门我没关。信呢？", "first_person_action": "站在门口。"},
    ]}, ensure_ascii=False)


class ScenePerformanceOwnershipTests(unittest.TestCase):
    def test_quote_check_allows_actor_fragments_but_not_new_dialogue(self) -> None:
        self.assertEqual(unlicensed_scene_dialogue("他说：“信……我拿的。”她问：“信呢？”", _materials()), [])
        self.assertEqual(unlicensed_scene_dialogue("他说：“饭在锅里。”", _materials()), ["饭在锅里。"])
        self.assertEqual(unlicensed_scene_dialogue("她闻到潮气，想起去年。", _materials()), [])
        self.assertEqual(unlicensed_scene_dialogue("她想起那句“原谅”，心里仍不肯信。", _materials()), [])
        self.assertEqual(unlicensed_scene_dialogue("她想着“信里有没有我”，没有问出口。", _materials()), [])

    def test_focused_action_audit_checks_exact_same_actor_evidence(self) -> None:
        prose = "他拿起信。"
        finding = {"status": "violations_found", "violations": [{
            "prose_quote": prose, "speaker": "character/protagonist", "closest_entry_id": "a1",
            "why_not_covered": "来源明确没碰信，正文却拿起。",
        }]}
        captured = []
        result = audit_visible_actions(prose, _materials(), lambda prompt: captured.append(prompt) or json.dumps(finding, ensure_ascii=False))
        self.assertEqual(result, finding["violations"])
        self.assertNotIn("别让人知道", captured[0])
        self.assertIn("朝某处看一眼", captured[0])
        self.assertEqual(audit_visible_actions(prose, _materials(), lambda _: '{"status":"clean","violations":[]}'), [])
        finding["violations"][0]["closest_entry_id"] = "a2"
        with self.assertRaisesRegex(ValueError, "same-actor evidence"):
            audit_visible_actions(prose, _materials(), lambda _: json.dumps(finding, ensure_ascii=False))

    def test_batch_entries_inherit_speaker_and_receive_stable_audit_ids(self) -> None:
        materials = "一级角色素材\n" + json.dumps({"actor_candidates": [{
            "speaker": "柳烟", "entries": [{"spoken": "", "first_person_action": "我没碰信。"}],
        }]}, ensure_ascii=False)
        finding = {"status": "violations_found", "violations": [{
            "prose_quote": "柳烟拿起信。", "speaker": "柳烟", "closest_entry_id": "batch:1:1",
            "why_not_covered": "没碰信不等于拿起信。",
        }]}
        self.assertEqual(audit_visible_actions("柳烟拿起信。", materials,
                                              lambda _: json.dumps(finding, ensure_ascii=False)), finding["violations"])

    def test_repairs_use_original_material_and_reject_persistent_violation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = PiSceneTransactionRuntime({}, project_root=root, data_root=root / ".studio")
            candidate = CreativeResult("她说：“饭在锅里。”", "初稿", SceneDelta())
            good = json.dumps({"prose": "他说：“信……我拿的。”", "decision_summary": "修订", "scene_delta": {}}, ensure_ascii=False)
            bad = json.dumps({"prose": "她又说：“去吃饭。”", "decision_summary": "修订", "scene_delta": {}}, ensure_ascii=False)
            def good_run(prompt: str, *, role: str, transaction_id: str) -> str:
                return '{"status":"clean","violations":[]}' if role == "reviewer" else good
            with patch.object(runtime, "_run", side_effect=good_run) as run:
                result = runtime._repair_actor_ownership("tx", _brief(), candidate, _materials(), "", "")
                self.assertEqual(unlicensed_scene_dialogue(result.prose, _materials()), [])
                self.assertIn("饭在锅里", run.call_args_list[0].args[0])
                self.assertIn("一级角色素材", run.call_args_list[0].args[0])
            with patch.object(runtime, "_run", return_value=bad) as run, self.assertRaisesRegex(RuntimeError, "after four repairs"):
                runtime._repair_actor_ownership("tx", _brief(), candidate, _materials(), "", "")
            self.assertEqual(run.call_count, 4)

    def test_runtime_repairs_unauthorized_action_without_additional_dialogue(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = PiSceneTransactionRuntime({}, project_root=root, data_root=root / ".studio")
            candidate = CreativeResult("他拿起信。", "初稿", SceneDelta())
            repaired = json.dumps({"prose": "他望着信，没有碰。", "decision_summary": "修订", "scene_delta": {}}, ensure_ascii=False)
            finding = json.dumps({"status": "violations_found", "violations": [{
                "prose_quote": "他拿起信。", "speaker": "character/protagonist", "closest_entry_id": "a1",
                "why_not_covered": "来源没碰信，正文拿起了。",
            }]}, ensure_ascii=False)
            calls = []
            def run(prompt: str, *, role: str, transaction_id: str) -> str:
                calls.append((role, prompt))
                if role == "worker":
                    return repaired
                return finding if "他拿起信。" in prompt else '{"status":"clean","violations":[]}'
            with patch.object(runtime, "_run", side_effect=run):
                result = runtime._repair_actor_ownership("tx", _brief(), candidate, _materials(), "", "")
            self.assertEqual(result.prose, "他望着信，没有碰。")
            self.assertEqual([role for role, _ in calls], ["reviewer", "worker", "reviewer"])
            self.assertIn("来源没碰信", calls[1][1])


if __name__ == "__main__":
    unittest.main()
