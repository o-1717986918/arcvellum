import unittest

from literary_engineering_studio_engine.public.literary import (
    parse_describer_candidates, render_describer_initialization, render_describer_turn,
)


class DescriberContractTests(unittest.TestCase):
    def test_character_lens_uses_visible_and_sourced_life_experience(self):
        init = render_describer_initialization("character-description", "克制的作品语言")
        turn = render_describer_turn(
            "character-description", {"scene_id": "s1", "viewpoint": "甲", "participants": ["甲", "乙"]},
            target="乙", purpose="让读者注意他习惯性的迟疑", scene_moment="递杯时",
            cue="他把杯沿转向自己", confirmed_sources="杯子有缺口", public_stage=[],
        )
        self.assertIn("可见形态与来源已知的生活经验", init)
        self.assertIn("递杯时", turn)
        self.assertEqual(len(parse_describer_candidates({"candidates": [
            {"text": "他把缺口藏进掌心，仍没接话。", "focus": "迟疑与惯常照顾"},
        ]}, "character-description")), 1)

    def test_empty_candidate_needs_reason_and_more_than_three_are_rejected(self):
        with self.assertRaises(ValueError):
            parse_describer_candidates({"candidates": []}, "scene-description")
        self.assertEqual(parse_describer_candidates({"candidates": [], "no_material_reason": "此刻停顿已足够"}, "scene-description"), [])
        with self.assertRaises(ValueError):
            parse_describer_candidates({"candidates": [{"text": "有效文本", "focus": "焦点"}] * 4}, "scene-description")

    def test_event_narrator_handles_offstage_history_instead_of_object_texture(self):
        init = render_describer_initialization("event-narration", "简净而有回声")
        turn = render_describer_turn(
            "event-narration", {"scene_id": "s1", "viewpoint": "甲", "participants": ["甲"]},
            target="旧城停电", purpose="让读者重新理解这次沉默", scene_moment="灯再次熄灭时",
            cue="已确认停电发生在三年前", confirmed_sources="三年前旧城停电三日", public_stage=[],
        )
        self.assertIn("场外事件", init)
        self.assertIn("人物转述", init)
        self.assertIn("旧城停电", turn)
        self.assertNotIn("物的质地", init)
        unclassified = parse_describer_candidates({"candidates": [{"text": "旧城曾停电三日。", "focus": "延迟交代"}]}, "event-narration")[0]
        self.assertEqual(unclassified["basis"], "proposed")
        self.assertIn("未标来源状态", unclassified["source_note"])
        proposal = parse_describer_candidates({"candidates": [{"text": "若旧城每逢大潮就断电，夜行会成为一门手艺。",
            "focus": "给世界规则以生活后果", "basis": "proposed", "source_note": "新设定候选，尚无确认来源"}]}, "event-narration")
        self.assertEqual(proposal[0]["basis"], "proposed")

    def test_mixed_declared_sources_remain_proposals_with_original_note_and_prose(self):
        text = "森林改了路，商队却把这当成一次免费游览。"
        declaration = "confirmed（道路规则）；proposed（商队经历）"
        result = parse_describer_candidates({"candidates": [{"text": text, "focus": "风俗与喜剧",
            "basis": declaration, "source_note": "规则见世界档案；商队经历为候选。"}]}, "event-narration")[0]
        self.assertEqual(result["text"], text)
        self.assertEqual(result["basis"], "proposed")
        self.assertIn(declaration, result["source_note"])
        self.assertIn("商队经历为候选", result["source_note"])
        for invalid in ("unconfirmed", "maybe confirmed", "confirmed + unknown", "fabricated"):
            with self.subTest(basis=invalid), self.assertRaises(ValueError):
                parse_describer_candidates({"candidates": [{"text": text, "focus": "风俗",
                    "basis": invalid, "source_note": "来源"}]}, "event-narration")

    def test_confirmed_label_without_source_remains_unconfirmed_material(self):
        result = parse_describer_candidates({"candidates": [{"text": "旧城每逢大潮便停电。", "focus": "风俗",
            "basis": "confirmed"}]}, "event-narration")[0]
        self.assertEqual(result["basis"], "proposed")
        self.assertIn("未附来源说明", result["source_note"])
        self.assertIn("confirmed", result["source_note"])

    def test_macro_task_keeps_full_rules_and_source_information(self):
        sources = "前期资料。" * 1200 + "招牌在夜里吸收星光，翌日结成糖霜。"
        turn = render_describer_turn("event-narration", {"scene_id": "s", "participants": [],
            "objective": "建立世界尺度", "scene_function": "世界开场",
            "canon_constraints": ["诺亚是学徒，露米娅是店主。"]}, target="森林",
            purpose="介绍世界", scene_moment="跨季节", cue="", confirmed_sources=sources, public_stage=[])
        self.assertIn("诺亚是学徒，露米娅是店主", turn)
        self.assertIn("翌日结成糖霜", turn)
        self.assertIn("建立世界尺度", turn)


if __name__ == "__main__":
    unittest.main()
