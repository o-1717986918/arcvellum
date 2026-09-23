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
        self.assertEqual(preview.asset.version, "v12")
        self.assertIn("可听见的语言曲线", str(preview.asset.metadata))
        self.assertTrue(any("可听见的语言曲线" in item for item in preview.asset.metadata["style_constraints"]))
        self.assertFalse(any("可听见的语言曲线" in item for item in preview.asset.metadata["hard_constraints"]))
        self.assertIn("让语言在入场、压力增长、转折和余波之间有来由地变化", preview.asset.body)
        self.assertIn("去掉姓名后仍可凭词域、句形、礼貌边界", preview.asset.body)
        self.assertIn("一篇最贴合本场功能的表达主参照", str(preview.asset.metadata))
        self.assertIn("Style Lint 与 AgentReview 继续核验违禁表达", str(preview.asset.metadata))
        self.assertNotIn("像给朋友讲一件真实发生的事", str(preview.asset.metadata))

    def test_provider_prompt_prioritizes_expression_and_keeps_hard_boundaries(self):
        templates = engine_root() / "templates" / "prompts"
        system = (templates / "scene_generation_system.md").read_text(encoding="utf-8")
        user = (templates / "scene_generation_user.md").read_text(encoding="utf-8")

        self.assertIn("速度、段落厚度和收束模式", STYLE_GENERATION_STANDARD)
        self.assertIn("机锋、幽默、误答、突然的坦白或沉默", STYLE_GENERATION_STANDARD)
        self.assertIn("不要求每段都推进一个外部事件", STYLE_GENERATION_STANDARD)
        self.assertNotIn("像日记里会写的句子", STYLE_GENERATION_STANDARD)
        self.assertIn("## 本场表达执行", user)
        self.assertIn("不把清晰误写为全程平直", system)
        self.assertIn("中文句子使用全角标点", OUTPUT_CONTRACT)
        self.assertIn("禁用机械“不是……而是……”", OUTPUT_CONTRACT)


if __name__ == "__main__":
    unittest.main()
