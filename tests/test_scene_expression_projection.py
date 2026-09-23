from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.public.literary import project_brief_expression_context


class SceneExpressionProjectionTests(unittest.TestCase):
    def test_character_voice_survives_and_perception_has_no_stock_fillers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            characters = root / "characters"
            characters.mkdir()
            (characters / "sister.yaml").write_text(
                """character_id: sister
name: 阿青
role: 姐姐
background_story:
  summary: 小时候常替弟弟把信送到邮局。
  formative_events: [有一年弟弟把回信藏在鞋盒里]
bdi:
  belief: [弟弟隐瞒了信]
  desire: [知道信的去向]
  intention: [当面追问]
psychology:
  secret: [她已看过信]
relationships:
  - target: brother
    state: 不愿当众拆穿
speech_style:
  vocabulary: 带有家中旧称呼
  rhythm: 问句短，解释缓
  taboo_words: [背叛]
  signature_patterns: [先答非所问再追问]
state:
  known_facts: [信昨夜已被取走]
""",
                encoding="utf-8",
            )
            projection = project_brief_expression_context(root, {
                "scene_id": "scene_0001",
                "objective": "姐姐逼问弟弟信的去向",
                "participants": ["character/sister", "character/brother"],
                "location": "客厅",
                "external_conflict": "隐瞒信的真相",
                "internal_conflict": "不愿承认已经读过",
                "rhythm": {"pace": "缓入急出"},
            })
            self.assertNotIn("prose_seed", projection)
            self.assertLessEqual(len(projection["expression_plan"]["active_axes"]), 3)
            self.assertEqual(projection["perceptual_options"]["sound"], [])
            self.assertEqual(projection["perceptual_options"]["texture"], [])
            self.assertEqual(projection["perceptual_options"]["light"], [])
            voice = projection["dialogue_intents"][0]
            self.assertEqual(voice["stable_voice"]["vocabulary"], "带有家中旧称呼")
            self.assertEqual(voice["stable_voice"]["rhythm"], "问句短，解释缓")
            self.assertEqual(voice["stable_voice"]["taboo_words"], ["背叛"])
            self.assertEqual(voice["stable_voice"]["signature_patterns"], ["先答非所问再追问"])
            self.assertEqual(voice["voice_state"]["interlocutors"], ["character/brother"])
            self.assertEqual(voice["voice_state"]["known_facts"], ["信昨夜已被取走"])
            self.assertIn("不愿当众拆穿", voice["voice_state"]["relationship_evidence"][0])
            self.assertIn("替弟弟把信送到邮局", voice["lived_history"]["summary"])
            self.assertIn("回信藏在鞋盒里", voice["lived_history"]["formative_events"][0])


if __name__ == "__main__":
    unittest.main()
