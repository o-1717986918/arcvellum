from __future__ import annotations

import json
import unittest

from literary_engineering_studio.runtimes.scene_performance_ownership import audit_visible_actions, compact_performance_materials, has_actor_entries, repair_actor_ownership, unlicensed_scene_dialogue
from literary_engineering_studio_engine.public.literary import CreativeResult, SceneDelta


def _materials() -> str:
    return "一级角色素材\n" + json.dumps({"actor_entries": [
        {"entry_id": "a1", "speaker": "character/protagonist", "spoken": "信……我拿的。你拿去看。", "first_person_action": "我没碰信。", "private_impulse": "别让人知道我的念头。"},
        {"entry_id": "a2", "speaker": "character/sister", "spoken": "门我没关。信呢？", "first_person_action": "站在门口。"},
    ]}, ensure_ascii=False)


class ScenePerformanceOwnershipTests(unittest.TestCase):
    def test_environment_only_supplement_does_not_trigger_actor_audit(self) -> None:
        material = "环境候选\n" + json.dumps({"actor_entries": [], "environment_candidates": {
            "passages": [{"beat_id": "b1", "description": "雨停了。"}],
        }}, ensure_ascii=False)
        candidate = CreativeResult("雨停了。", "视角停留", SceneDelta())
        self.assertFalse(has_actor_entries(material))
        self.assertIn("雨停了", compact_performance_materials(material))
        self.assertIs(repair_actor_ownership(candidate, material,
                                             lambda _prose: self.fail("unexpected actor audit"),
                                             lambda *_args: self.fail("unexpected repair")), candidate)

    def test_compact_review_material_keeps_visible_provenance_without_private_repetition(self) -> None:
        compact = compact_performance_materials(_materials())
        self.assertIn("信……我拿的", compact)
        self.assertIn("我没碰信", compact)
        self.assertNotIn("别让人知道我的念头", compact)

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
        self.assertIn("普通走位、拿放无情节后果的道具、眼神、手势、台词间停顿", captured[0])
        self.assertIn("决定性交付、藏取证物、揭露线索", captured[0])
        self.assertEqual(audit_visible_actions(prose, _materials(), lambda _: '{"status":"clean","violations":[]}'), [])
        finding["violations"][0]["closest_entry_id"] = "a2"
        with self.assertRaisesRegex(ValueError, "same-actor evidence"):
            audit_visible_actions(prose, _materials(), lambda _: json.dumps(finding, ensure_ascii=False))

    def test_action_audit_preserves_grounded_findings_when_reviewer_adds_fiction(self) -> None:
        prose = "他拿起信。"
        real = {"prose_quote": prose, "speaker": "character/protagonist", "closest_entry_id": "a1",
                "why_not_covered": "来源明确没碰信。"}
        imagined = {**real, "prose_quote": "他捡起两枚硬币。"}
        response = {"status": "violations_found", "violations": [real, imagined]}
        self.assertEqual(audit_visible_actions(prose, _materials(), lambda _: json.dumps(response, ensure_ascii=False)), [real])

    def test_consequential_dialogue_audit_keeps_rewrites_but_flags_new_turns(self) -> None:
        prose = "他说：\u201c饭在锅里。\u201d"
        finding = {"kind": "dialogue", "prose_quote": "饭在锅里。", "speaker": "character/protagonist",
                   "closest_entry_id": "a1", "why_not_covered": "这句招呼没有同一人物的 spoken 来源。"}
        captured = []
        result = audit_visible_actions(prose, _materials(),
                                       lambda prompt: captured.append(prompt) or json.dumps(
                                           {"status": "violations_found", "violations": [finding]}, ensure_ascii=False))
        self.assertEqual(result, [finding])
        self.assertIn("同一人物的 spoken", captured[0])
        self.assertIn("主创可以改写已有台词", captured[0])

        candidate = CreativeResult(prose, "初稿", SceneDelta())
        repaired = CreativeResult("他说：\u201c信是我拿的。\u201d", "修订", SceneDelta())
        repairs = []
        self.assertIs(repair_actor_ownership(
            candidate, _materials(), lambda text: [finding] if text == prose else [],
            lambda _candidate, kind, evidence: repairs.append((kind, evidence)) or repaired,
            allow_dialogue_rewrite=True,
        ), repaired)
        self.assertEqual(repairs[0][0], "dialogue")
        self.assertIn("饭在锅里。", repairs[0][1][0])

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

    def test_strict_ownership_helper_still_rejects_unsourced_dialogue(self) -> None:
        candidate = CreativeResult("她说：“饭在锅里。”", "初稿", SceneDelta())
        repaired = CreativeResult("他说：“信……我拿的。”", "修订", SceneDelta())
        self.assertIs(repair_actor_ownership(candidate, _materials(), lambda _: [],
                                             lambda _candidate, _kind, _evidence: repaired), repaired)
        with self.assertRaisesRegex(RuntimeError, "after four repairs"):
            repair_actor_ownership(candidate, _materials(), lambda _: [],
                                   lambda current, _kind, _evidence: current)


if __name__ == "__main__":
    unittest.main()
