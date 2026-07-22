from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.narrative_rhythm import narrative_rhythm_contract, render_narrative_rhythm_contract
from literary_engineering_studio_engine.rhythm_plan import load_rhythm_plan, save_rhythm_plan


class RhythmPlanTests(unittest.TestCase):
    def test_saved_plan_becomes_formal_scene_contract_and_is_versioned(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scenes").mkdir()
            (root / "project.yaml").write_text("project:\n  title: test\n", encoding="utf-8")
            scene = root / "scenes" / "scene_0001.yaml"
            scene.write_text(
                "scene_id: scene_0001\nchapter_id: chapter_0001\ntitle: 第一场\nword_count_target: 1800\ntime:\n  timeline_order: 9\nspatial_time_gap_before: 1.6\n"
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
                "detail_level": "set_piece",
                "spatial_time_gap_before": 2.1,
            }])
            contract = narrative_rhythm_contract(root, scene)
            self.assertEqual(saved["revision"], 1)
            self.assertEqual(contract["source"], "rhythm-plan")
            self.assertEqual(contract["status"], "pass")
            self.assertEqual(contract["narrative_rhythm"]["tension_curve"]["peak"], 5)
            self.assertEqual(contract["narrative_rhythm"]["detail_level"], "set_piece")
            self.assertEqual(saved["entries"][0]["word_count_target"], 1800)
            self.assertEqual(saved["entries"][0]["timeline_order"], 9)
            self.assertEqual(saved["entries"][0]["spatial_time_gap_before"], 2.1)
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

    def test_plan_exposes_book_and_volume_curves_without_changing_scene_authority(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scenes").mkdir()
            (root / "scenes" / "scene_0001.yaml").write_text(
                "scene_id: scene_0001\nvolume_id: volume_01\nchapter_id: chapter_01\ntitle: 开端\nword_count_target: 1800\n",
                encoding="utf-8",
            )
            (root / "scenes" / "scene_0002.yaml").write_text(
                "scene_id: scene_0002\nvolume_id: volume_01\nchapter_id: chapter_02\ntitle: 推进\nword_count_target: 2200\n",
                encoding="utf-8",
            )
            plan = load_rhythm_plan(root)
            self.assertEqual(plan["entries"][0]["volume_id"], "volume_01")
            self.assertIn("volume_01", plan["volumes"])
            self.assertEqual(plan["book"]["scene_count"], 2)

    def test_book_profile_is_versioned_and_visible_to_scene_generation_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scenes").mkdir()
            scene = root / "scenes" / "scene_0001.yaml"
            scene.write_text(
                "scene_id: scene_0001\nchapter_id: chapter_0001\ntitle: 开端\n"
                "narrative_rhythm:\n  scene_function: [铺垫]\n  scene_turn: 发现异常\n  reader_effect: 读者意识到平静不可靠\n  tension_curve: {entry: 1, peak: 3, exit: 2}\n"
                "scene_bridge:\n  incoming_pressure: 日常秩序已经出现裂缝\n  outgoing_hook: 一封未署名的信\n",
                encoding="utf-8",
            )
            saved = save_rhythm_plan(root, [{
                "scene_id": "scene_0001",
                "pace": "balanced",
                "rhythm_role": "setup",
                "tension_curve": {"entry": 1, "peak": 3, "exit": 2},
                "detail_level": "standard",
            }], book_profile={
                "profile_id": "contemplative",
                "arc": {"opening": 1, "ascent": 2, "midpoint": 4, "crisis": 3, "finale": 4},
                "breathing_interval": 4,
                "set_piece_ratio": 14,
                "narrative_distance": "observant",
                "ending_policy": "afterglow",
                "directive": "让关键变化落在选择之后，而不是解释之前。",
            })
            contract = narrative_rhythm_contract(root, scene)
            self.assertEqual(saved["book_profile"]["profile_id"], "contemplative")
            self.assertEqual(saved["book_profile"]["arc"]["midpoint"], 4)
            self.assertEqual(contract["book_rhythm_profile"]["ending_policy"], "afterglow")
            self.assertIn("关键变化", contract["book_rhythm_profile"]["directive"])
            self.assertIn("沉静回响", render_narrative_rhythm_contract(root, scene))
            self.assertIn("关键变化", render_narrative_rhythm_contract(root, scene))


if __name__ == "__main__":
    unittest.main()
