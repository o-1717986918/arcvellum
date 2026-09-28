import unittest

from literary_engineering_studio_engine.public.literary import (
    parse_describer_candidates, render_describer_initialization, render_describer_turn,
)


class DescriberContractTests(unittest.TestCase):
    def test_character_lens_guards_private_thought_and_returns_short_candidates(self):
        init = render_describer_initialization("character-description", "克制的作品语言")
        turn = render_describer_turn(
            "character-description", {"scene_id": "s1", "viewpoint": "甲", "participants": ["甲", "乙"]},
            target="乙", purpose="让读者注意他习惯性的迟疑", scene_moment="递杯时",
            cue="他把杯沿转向自己", confirmed_sources="杯子有缺口", public_stage=[],
        )
        self.assertIn("不得断言视角外动机", init)
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
        self.assertIn("人物所信", init)
        self.assertIn("旧城停电", turn)
        self.assertNotIn("物的质地", init)
        with self.assertRaisesRegex(ValueError, "basis and source note"):
            parse_describer_candidates({"candidates": [{"text": "旧城曾停电三日。", "focus": "延迟交代"}]}, "event-narration")
        proposal = parse_describer_candidates({"candidates": [{"text": "若旧城每逢大潮就断电，夜行会成为一门手艺。",
            "focus": "给世界规则以生活后果", "basis": "proposed", "source_note": "新设定候选，尚无确认来源"}]}, "event-narration")
        self.assertEqual(proposal[0]["basis"], "proposed")


if __name__ == "__main__":
    unittest.main()
