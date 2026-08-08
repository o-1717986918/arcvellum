from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.literary.scene.facts import (
    SceneFacts,
    load_scene_facts,
)


class SceneFactsTests(unittest.TestCase):
    def test_loader_preserves_nested_yaml_and_quoted_commas(self):
        with tempfile.TemporaryDirectory() as temporary:
            scene = Path(temporary) / "scene_0042.yaml"
            scene.write_text(
                "scene_id: scene_0042\n"
                "chapter_id: chapter_0007\n"
                "location: '旧车站，第三站台'\n"
                "participants: ['柳,生', 阿梨]\n"
                "input_state:\n"
                "  canon_refs: [world/weather, 'rule,with,comma']\n"
                "  active_foreshadowing:\n"
                "    - 没有寄件人的信\n"
                "scene_goal: >-\n"
                "  让阿梨确认来信与失踪案有关，\n"
                "  但暂不揭示寄件人。\n"
                "conflict:\n"
                "  external: 列车即将进站，证据可能被带走。\n"
                "  internal: 阿梨不愿承认自己认得字迹。\n"
                "style_constraints: [克制, '不要解释, 让动作说话']\n"
                "output_state:\n"
                "  next_hooks:\n"
                "    - 字迹来自一个按理不可能写信的人\n",
                encoding="utf-8",
            )

            facts = load_scene_facts(scene)

            self.assertIsInstance(facts, SceneFacts)
            self.assertEqual(facts.scene_id, "scene_0042")
            self.assertEqual(facts.chapter_id, "chapter_0007")
            self.assertEqual(facts.location, "旧车站，第三站台")
            self.assertEqual(facts.participants, ["柳,生", "阿梨"])
            self.assertEqual(
                facts.canon_refs,
                ["world/weather", "rule,with,comma"],
            )
            self.assertEqual(facts.active_foreshadowing, ["没有寄件人的信"])
            self.assertEqual(
                facts.scene_goal,
                "让阿梨确认来信与失踪案有关， 但暂不揭示寄件人。",
            )
            self.assertEqual(
                facts.external_conflict,
                "列车即将进站，证据可能被带走。",
            )
            self.assertEqual(
                facts.internal_conflict,
                "阿梨不愿承认自己认得字迹。",
            )
            self.assertEqual(
                facts.style_constraints,
                ["克制", "不要解释, 让动作说话"],
            )
            self.assertEqual(
                facts.next_hooks,
                ["字迹来自一个按理不可能写信的人"],
            )

    def test_loader_accepts_legacy_top_level_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            scene = Path(temporary) / "legacy.yaml"
            scene.write_text(
                "chapter_id: chapter_0001\n"
                "external: 门外有人。\n"
                "internal: 他不愿开门。\n"
                "canon_refs: [door-rule]\n"
                "active_foreshadowing: [旧钥匙]\n"
                "next_hooks: [门锁从里面转动]\n",
                encoding="utf-8",
            )

            facts = load_scene_facts(scene)

            self.assertEqual(facts.scene_id, "legacy")
            self.assertEqual(facts.external_conflict, "门外有人。")
            self.assertEqual(facts.internal_conflict, "他不愿开门。")
            self.assertEqual(facts.canon_refs, ["door-rule"])
            self.assertEqual(facts.active_foreshadowing, ["旧钥匙"])
            self.assertEqual(facts.next_hooks, ["门锁从里面转动"])

    def test_loader_rejects_non_mapping_or_invalid_yaml(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sequence = root / "sequence.yaml"
            invalid = root / "invalid.yaml"
            sequence.write_text("- one\n- two\n", encoding="utf-8")
            invalid.write_text("scene_id: [unclosed\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "scene YAML must be a mapping"):
                load_scene_facts(sequence)
            with self.assertRaisesRegex(ValueError, "invalid scene YAML"):
                load_scene_facts(invalid)


if __name__ == "__main__":
    unittest.main()
