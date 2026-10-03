"""New top prompts stay behind the existing opt-in and use positive guidance."""
import unittest
from literary_engineering_studio.project_agent.prompt_policy import (
    system_prompt, natural_prompts_enabled, turn_prompt,
    delegated_goal_followup_prompt, delegated_scene_checkpoint_prompt,
)
from literary_engineering_studio_engine.public.prompting import prompt_layer_spec
class NaturalTopPromptTests(unittest.TestCase):
    def test_optin_uses_separate_versioned_prompts(self):
        self.assertFalse(natural_prompts_enabled({}))
        self.assertTrue(natural_prompts_enabled({"application":{"scene_creator_v2":{"enabled":True}}}))
        natural=system_prompt({"name":"总编","prompt":"细读人物"},write_enabled=True,natural=True)
        for phrase in ("你不是","你不能","不要","没有权限"):
            self.assertNotIn(phrase,natural)
        self.assertIn("Writing-DNA",natural)
        self.assertIn("stop_after_formal_units",natural)
        self.assertIn("你不能直接写项目文件",system_prompt({},write_enabled=True))

    def test_edited_top_templates_reach_each_stage(self):
        seen = []
        def edited(layer_id):
            seen.append(layer_id)
            return "作者定稿：沿水声组织交流。\n" + prompt_layer_spec(layer_id).default_text
        options = {"natural": True, "prompt_reader": edited}
        for text in (
            system_prompt({}, write_enabled=True, **options),
            turn_prompt("继续", {}, **options),
            delegated_goal_followup_prompt("继续", "进度", {}, **options),
            delegated_scene_checkpoint_prompt("继续", {}, "雨信", **options),
        ):
            self.assertIn("作者定稿：沿水声组织交流。", text)
        self.assertEqual(seen, ["project_agent.v2.creative_direction", "project_agent.v2.system.write.protocol", "project_agent.v2.turn.protocol",
            "project_agent.v2.goal_followup.protocol", "project_agent.v2.scene_checkpoint.protocol"])

