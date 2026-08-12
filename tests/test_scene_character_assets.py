import tempfile
import unittest
from pathlib import Path

from literary_engineering_studio_engine.scene_character_assets import (
    ensure_scene_character_asset_tasks,
    scene_character_asset_requirements,
)


class SceneCharacterAssetTests(unittest.TestCase):
    def test_named_nonformal_participant_receives_stable_candidate_sidecar(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "characters").mkdir()
            (root / "characters" / "hero.yaml").write_text(
                "character_id: hero\nname: 林昭\n",
                encoding="utf-8",
            )
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir()
            scene.write_text(
                "scene_id: scene_0001\nparticipants: [林昭, 林正]\n",
                encoding="utf-8",
            )

            requirements = scene_character_asset_requirements(root, scene)

            self.assertEqual(len(requirements), 1)
            requirement = requirements[0]
            self.assertEqual(requirement.name, "林正")
            self.assertEqual(requirement.candidate_path.as_posix().split("/")[-1], "scene-0001-林正.json")
            self.assertFalse(requirement.task_path.exists())

            emitted = ensure_scene_character_asset_tasks(root, scene)

            self.assertEqual(emitted, requirements)
            self.assertTrue(requirement.task_path.is_file())
            self.assertIn("候选角色档案", requirement.task_path.read_text(encoding="utf-8"))

    def test_block_list_participants_are_supported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scene = root / "scenes" / "scene_0002.yaml"
            scene.parent.mkdir()
            scene.write_text(
                "scene_id: scene_0002\nparticipants:\n  - 阿梨\n  - 舟夫\nscene_goal: 过河\n",
                encoding="utf-8",
            )

            requirements = scene_character_asset_requirements(root, scene)

            self.assertEqual([item.name for item in requirements], ["阿梨", "舟夫"])

    def test_protagonist_symbol_and_declared_alias_resolve_to_formal_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "characters").mkdir()
            (root / "characters" / "protagonist-orbit-engineer.yaml").write_text(
                "character_id: protagonist-orbit-engineer\n"
                "name: 林昭\n"
                "aliases: [小林]\n",
                encoding="utf-8",
            )
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir()
            scene.write_text(
                "scene_id: scene_0001\nparticipants: [主角, 小林, 新同事]\n",
                encoding="utf-8",
            )

            requirements = scene_character_asset_requirements(root, scene)

            self.assertEqual([item.name for item in requirements], ["新同事"])

    def test_promoted_scene_candidate_id_remains_a_reference_alias(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "characters").mkdir()
            (root / "characters" / "crew-member.yaml").write_text(
                "character_id: crew-member\nname: 陈默\n",
                encoding="utf-8",
            )
            promotions = root / "workflow" / "asset_promotions"
            promotions.mkdir(parents=True)
            (promotions / "scene-0001-轨道维修舱内同仁_promotion.json").write_text(
                '{"candidate_id":"scene-0001-轨道维修舱内同仁"}\n',
                encoding="utf-8",
            )
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir()
            scene.write_text(
                "scene_id: scene_0001\nparticipants: [轨道维修舱内同仁]\n",
                encoding="utf-8",
            )

            self.assertEqual(scene_character_asset_requirements(root, scene), [])

    def test_foundational_promotion_binds_symbolic_protagonist_to_real_character(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "characters").mkdir()
            (root / "characters" / "gu-zheng.yaml").write_text(
                "character_id: gu-zheng\nname: 顾铮\nrole: protagonist\n",
                encoding="utf-8",
            )
            promotions = root / "workflow" / "asset_promotions"
            promotions.mkdir(parents=True)
            (promotions / "protagonist-foundation_promotion.json").write_text(
                '{"candidate_id":"protagonist-foundation","outputs":["characters/gu-zheng.yaml"]}\n',
                encoding="utf-8",
            )
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir()
            scene.write_text(
                "scene_id: scene_0001\nparticipants: [主角]\n",
                encoding="utf-8",
            )

            self.assertEqual(scene_character_asset_requirements(root, scene), [])
