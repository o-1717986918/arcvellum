from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.narrative_rhythm import narrative_rhythm_contract
from literary_engineering_studio_engine.rhythm_plan import load_rhythm_plan, save_rhythm_plan


class RhythmPlanTests(unittest.TestCase):
    def test_saved_plan_becomes_formal_scene_contract_and_is_versioned(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scenes").mkdir()
            (root / "project.yaml").write_text("project:\n  title: test\n", encoding="utf-8")
            scene = root / "scenes" / "scene_0001.yaml"
            scene.write_text(
                "scene_id: scene_0001\nchapter_id: chapter_0001\ntitle: 第一场\n"
                "narrative_rhythm:\n  scene_function: [推进主线]\n  scene_turn: 主角改变选择\n  reader_effect: 风险被重新理解\n"
                "scene_bridge:\n  incoming_pressure: 上一场承诺尚未兑现\n  outgoing_hook: 对手开始行动\n",
                encoding="utf-8",
            )
            implicit = load_rhythm_plan(root)
            self.assertEqual(implicit["entries"][0]["tension_curve"], {"entry": 2, "peak": 3, "exit": 2})
            saved = save_rhythm_plan(root, [{
                "scene_id": "scene_0001",
                "pace": "slow_to_fast",
                "rhythm_role": "turn",
                "scene_function": ["改变人物选择"],
                "tension_curve": {"entry": 2, "peak": 5, "exit": 4},
            }])
            contract = narrative_rhythm_contract(root, scene)
            self.assertEqual(saved["revision"], 1)
            self.assertEqual(contract["source"], "rhythm-plan")
            self.assertEqual(contract["status"], "pass")
            self.assertEqual(contract["narrative_rhythm"]["tension_curve"]["peak"], 5)
            self.assertEqual(contract["plan_digest"], saved["digest"])
            unchanged = save_rhythm_plan(root, saved["entries"])
            self.assertEqual(unchanged["revision"], 1)

    def test_invalid_curve_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scenes").mkdir()
            (root / "scenes" / "scene_0001.yaml").write_text("scene_id: scene_0001\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                save_rhythm_plan(root, [{"scene_id": "scene_0001", "pace": "fast", "rhythm_role": "action", "tension_curve": [1, 7, 2]}])


if __name__ == "__main__":
    unittest.main()
