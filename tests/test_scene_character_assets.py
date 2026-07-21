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
