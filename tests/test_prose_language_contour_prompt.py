from __future__ import annotations

import unittest

from literary_engineering_studio_engine.foundation.resources import engine_root
from literary_engineering_studio_engine.prompting.pack import (
    OUTPUT_CONTRACT,
    STYLE_GENERATION_STANDARD,
)
from literary_engineering_studio_engine.prompting.registry import resolve_prompt_asset


class ProseLanguageContourPromptTests(unittest.TestCase):
    def test_formal_prompt_requires_scene_shaped_language_without_weakening_review(self):
        preview = resolve_prompt_asset("route.scene-development.prose.generate.v1")
        self.assertIsNotNone(preview.asset)
        assert preview.asset is not None
        self.assertEqual(preview.asset.version, "v13")
        self.assertIn("本场选中的完整参考", str(preview.asset.metadata))
        self.assertTrue(any("本场选中的完整参考" in item for item in preview.asset.metadata["style_constraints"]))
        self.assertFalse(any("本场选中的完整参考" in item for item in preview.asset.metadata["hard_constraints"]))
        self.assertIn("句法、叙述距离、对白与意象要随本场", preview.asset.body)
        self.assertIn("人物选择、物证或关系后果", preview.asset.body)
        self.assertIn("Style Lint 与 AgentReview 继续核验违禁表达", str(preview.asset.metadata))
        self.assertNotIn("像给朋友讲一件真实发生的事", str(preview.asset.metadata))

    def test_provider_prompt_prioritizes_expression_and_keeps_hard_boundaries(self):
        templates = engine_root() / "templates" / "prompts"
        system = (templates / "scene_generation_system.md").read_text(encoding="utf-8")
        user = (templates / "scene_generation_user.md").read_text(encoding="utf-8")

        self.assertIn("长短句随压力与认识变化", STYLE_GENERATION_STANDARD)
        self.assertIn("当下对话对象共同决定言语行动", STYLE_GENERATION_STANDARD)
        self.assertIn("停在后果，不替读者解释", STYLE_GENERATION_STANDARD)
        self.assertNotIn("像日记里会写的句子", STYLE_GENERATION_STANDARD)
        self.assertIn("## 本场参考选段", user)
        self.assertIn("软审美问题在生成时解决", system)
        self.assertIn("已编译硬语言边界", OUTPUT_CONTRACT)


if __name__ == "__main__":
    unittest.main()
