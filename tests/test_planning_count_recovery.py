"""Planning count errors must share one bounded repair, preserving valid work."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.application.lean_longform_planning import LeanLongformPlanningService
from tests.test_lean_longform_plan import _scene
from tests.test_lean_longform_planning_service import _Gateway


def _plan():
    return {
        "premise": "旧信牵出一段未解的承诺", "central_question": "如何偿还旧债？",
        "ending_choice": "公开真相并承担代价", "volume_obligations": ["偿还旧债"],
        "chapters": [{"title": f"阶段{i}", "dramatic_turn": f"局面变化{i}",
                      "obligation": f"阶段任务{i}", "reader_question": f"问题{i}如何解决？"}
                     for i in range(1, 4)],
        "first_window": [_scene(f"单元{i}") for i in range(1, 4)],
    }


class PlanningCountRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "project.yaml").write_text(
            "target_length: 30000\ntarget_chapters: 3\ntarget_scenes: 9\n", encoding="utf-8")

    def test_one_repair_receives_both_bad_counts_and_replay_needs_no_calls(self):
        invalid = _plan()
        invalid["volume_obligations"] = ["甲", "乙", "丙", "丁"]
        invalid["first_window"] = invalid["first_window"][:1]
        original = deepcopy(invalid)
        gateway = _Gateway([invalid, _plan()])
        events = []
        service = LeanLongformPlanningService({}, data_root=self.root / "data", gateway=gateway,
            event_sink=lambda event, data: events.append((event, data)))

        plan = service.ensure_initial(self.root)

        self.assertEqual(len(gateway.calls), 2)
        self.assertIn("逐项展开 3 个独立正文单元", gateway.calls[0][1])
        feedback = gateway.calls[1][1]
        self.assertIn("volume_obligations: expected 1, received 4", feedback)
        self.assertIn("first_window: expected 3, received 1", feedback)
        self.assertIn('"first_window":3', feedback)
        self.assertIn("不要复制同一场景", feedback)
        self.assertEqual(len(plan["scenes"]), 3)
        self.assertEqual([row["name"] for row in plan["scenes"]], ["单元1", "单元2", "单元3"])
        self.assertEqual(invalid, original)
        self.assertEqual(events[0][0], "planning.validation_failed")
        self.assertIn("first_window", events[0][1]["message"])
        self.assertEqual(service.ensure_initial(self.root), plan)
        self.assertEqual(len(gateway.calls), 2)

    def test_volume_only_repair_still_fails_once_without_partial_writes(self):
        invalid = _plan()
        invalid["volume_obligations"] = ["甲", "乙", "丙", "丁"]
        invalid["first_window"] = invalid["first_window"][:1]
        incomplete = {**invalid, "volume_obligations": ["甲"]}
        gateway = _Gateway([invalid, incomplete])
        service = LeanLongformPlanningService({}, data_root=self.root / "data", gateway=gateway)

        with self.assertRaisesRegex(ValueError, "first_window: expected 3, received 1"):
            service.ensure_initial(self.root)

        self.assertEqual(len(gateway.calls), 2)
        self.assertFalse((self.root / "plot/lean_project_plan.json").exists())
        self.assertFalse((self.root / "plot/word_budget/word_budget.json").exists())
        self.assertFalse((self.root / "scenes").exists())

    def test_empty_next_window_gets_one_author_repair_without_dropping_previous_scenes(self):
        next_scenes = [_scene(f"后续单元{i}") for i in range(1, 4)]
        gateway = _Gateway([_plan(), {"scenes": []}, {"scenes": next_scenes}])
        service = LeanLongformPlanningService({}, data_root=self.root / "data", gateway=gateway)
        initial = service.ensure_initial(self.root)
        before = [(self.root / "scenes" / f"scene_{i:04d}.yaml").read_bytes() for i in range(1, 4)]

        self.assertTrue(service.expand_next_window(self.root))

        self.assertEqual(len(gateway.calls), 3)
        self.assertIn("scenes: expected 3, received 0", gateway.calls[2][1])
        stored = json.loads((self.root / "plot/lean_project_plan.json").read_text(encoding="utf-8"))
        self.assertEqual(stored["scenes"][:3], initial["scenes"])
        self.assertEqual([s["scene_id"] for s in stored["scenes"]], [f"scene_{i:04d}" for i in range(1, 7)])
        self.assertEqual(before, [(self.root / "scenes" / f"scene_{i:04d}.yaml").read_bytes() for i in range(1, 4)])
