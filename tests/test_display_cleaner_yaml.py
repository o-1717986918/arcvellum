import unittest

from literary_engineering_studio_engine.display_cleaner import (
    list_from_yaml_text,
    nested_scalar_from_yaml_text,
)


class DisplayCleanerYamlTests(unittest.TestCase):
    def test_block_list_stops_before_the_next_yaml_field(self):
        text = (
            "participants:\n"
            "  - character_001\n"
            "  - character_004\n"
            "participant_refs:\n"
            "  - character_001\n"
            "scene_goal: 继续推进\n"
            "narrative_rhythm:\n"
            "  pace: fast\n"
        )
        self.assertEqual(list_from_yaml_text(text, "participants"), ["character_001", "character_004"])
        self.assertEqual(list_from_yaml_text(text, "participant_refs"), ["character_001"])

    def test_nested_scalar_stays_inside_its_parent_block(self):
        text = (
            "background_story:\n"
            "  summary: 失去一段记忆\n"
            "reader_experience:\n"
            "  summary: 这里不是角色背景\n"
        )
        self.assertEqual(nested_scalar_from_yaml_text(text, "background_story", "summary"), "失去一段记忆")
        self.assertEqual(nested_scalar_from_yaml_text(text, "missing", "summary", "fallback"), "fallback")


if __name__ == "__main__":
    unittest.main()
