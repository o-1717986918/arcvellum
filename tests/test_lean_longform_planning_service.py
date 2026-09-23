import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from literary_engineering_studio.application.lean_longform_planning import LeanLongformPlanningService
from literary_engineering_studio.application.project_manager import record_direction
from literary_engineering_studio_engine.public.literary import longform_materialization_status

from tests.test_lean_longform_plan import _scene


class _Gateway:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    def run(self, workspace, prompt, **kwargs):
        self.calls.append((workspace, prompt, kwargs))
        return SimpleNamespace(answer=json.dumps(self.answers.pop(0), ensure_ascii=False))


class LeanLongformPlanningServiceTests(unittest.TestCase):
    def test_initial_plan_and_next_chapter_are_resumable_without_legacy_tasks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text(
                "target_length: 6000\ntarget_chapters: 2\ntarget_scenes: 3\n",
                encoding="utf-8",
            )
            gateway = _Gateway([
                {
                    "premise": "旧承诺使林昭欠下一笔债",
                    "central_question": "他会怎样履约？",
                    "ending_choice": "保住盟友或完成承诺",
                    "volume_obligations": ["债务变得不可撤销"],
                    "chapters": [
                        {"title": "信件", "dramatic_turn": "承诺公开", "obligation": "建立债务", "reader_question": "谁留下信？"},
                        {"title": "索偿", "dramatic_turn": "盟友离开", "obligation": "兑现代价", "reader_question": "林昭会选择谁？"},
                    ],
                    "first_window": [_scene("拆信"), _scene("追问")],
                },
                {"scenes": [_scene("索偿")]},
            ])
            service = LeanLongformPlanningService(
                {}, data_root=root / "data", gateway=gateway
            )

            first = service.ensure_initial(root)
            self.assertEqual(len(first["scenes"]), 2)
            self.assertEqual(len(gateway.calls), 1)
            self.assertIn("不得在结局后追加尾声", gateway.calls[0][1])
            self.assertIn("必须逐字复用 characters", gateway.calls[0][1])
            self.assertIn("一致的日期、年份和时间差口径", gateway.calls[0][1])
            self.assertIn("跨场景硬限制", gateway.calls[0][1])
            self.assertIn("逐条保存在 world_facts", gateway.calls[0][1])
            self.assertIn("虚指反复与精确计数", gateway.calls[0][1])
            self.assertIn("一项实际功能", gateway.calls[0][1])
            self.assertNotIn("会改变眼前选择且后文会核验", gateway.calls[0][1])
            self.assertEqual(len(service.ensure_initial(root)["scenes"]), 2)
            self.assertEqual(len(gateway.calls), 1)
            self.assertTrue(longform_materialization_status(root)[0])
            record_direction(root, "下一章让林昭主动说出代价，而非旁白解释。")
            self.assertTrue(service.expand_next_window(root))
            self.assertFalse(service.expand_next_window(root))
            self.assertEqual(len(gateway.calls), 2)
            self.assertIn("林昭主动说出代价", gateway.calls[1][1])
            self.assertIn('"chapter_spine"', gateway.calls[1][1])
            self.assertIn('"registered_characters"', gateway.calls[1][1])
            self.assertIn('"world_facts"', gateway.calls[1][1])
            self.assertIn('"used_events"', gateway.calls[1][1])
            self.assertIn('"event_budget"', gateway.calls[1][1])
            self.assertIn('"irreversible_change":"盟友离开"', gateway.calls[1][1])
            self.assertIn("不追加尾声或续集钩子", gateway.calls[1][1])
            self.assertIn("虚指反复不当作精确计数", gateway.calls[1][1])
            self.assertIn("不强求当场有用的值日后再次兑现", gateway.calls[1][1])
            self.assertTrue((root / "scenes" / "scene_0003.yaml").is_file())
            stored = json.loads((root / "plot" / "lean_project_plan.json").read_text(encoding="utf-8"))
            second_event = next(
                item for item in stored["event_budget"] if item["chapter_id"] == "chapter_0002"
            )
            self.assertEqual(second_event["scene_ids"], ["scene_0003"])
            self.assertFalse((root / "reviews").exists())
            self.assertFalse(list(root.rglob("*.agent_tasks.md")))

    def test_initial_plan_repairs_an_overfull_first_window_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text(
                "target_length: 6000\ntarget_chapters: 1\ntarget_scenes: 2\n",
                encoding="utf-8",
            )
            base = {
                "premise": "旧承诺使林昭欠下一笔债",
                "central_question": "他会怎样履约？",
                "ending_choice": "保住盟友或完成承诺",
                "volume_obligations": ["债务变得不可撤销"],
                "chapters": [{
                    "title": "信件", "dramatic_turn": "承诺公开",
                    "obligation": "建立债务", "reader_question": "谁留下信？",
                }],
            }
            gateway = _Gateway([
                {**base, "first_window": [_scene("拆信"), _scene("追问"), _scene("赴约")]},
                {**base, "first_window": [_scene("拆信与追问"), _scene("赴约")]},
            ])
            events = []
            service = LeanLongformPlanningService(
                {}, data_root=root / "data", gateway=gateway,
                event_sink=lambda event, data: events.append((event, data)),
            )

            plan = service.ensure_initial(root)

            self.assertEqual(len(plan["scenes"]), 2)
            self.assertEqual(len(gateway.calls), 2)
            self.assertIn("chapter window requires exactly 2 scenes", gateway.calls[1][1])
            self.assertIn("不要简单截断", gateway.calls[1][1])
            self.assertIn("不得追加尾声或续集钩子", gateway.calls[1][1])
            self.assertIn("继续逐条保存在 world_facts", gateway.calls[1][1])
            self.assertEqual(events[0][0], "planning.validation_failed")
            self.assertTrue((root / "plot" / "lean_project_plan.json").is_file())

    def test_failed_initial_repair_does_not_write_a_partial_plan(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text(
                "target_length: 6000\ntarget_chapters: 1\ntarget_scenes: 2\n",
                encoding="utf-8",
            )
            invalid = {
                "premise": "旧承诺使林昭欠下一笔债",
                "central_question": "他会怎样履约？",
                "ending_choice": "保住盟友或完成承诺",
                "volume_obligations": ["债务变得不可撤销"],
                "chapters": [{
                    "title": "信件", "dramatic_turn": "承诺公开",
                    "obligation": "建立债务", "reader_question": "谁留下信？",
                }],
                "first_window": [_scene("拆信"), _scene("追问"), _scene("赴约")],
            }
            service = LeanLongformPlanningService(
                {}, data_root=root / "data", gateway=_Gateway([invalid, invalid])
            )

            with self.assertRaisesRegex(ValueError, "exactly 2 scenes"):
                service.ensure_initial(root)

            self.assertFalse((root / "plot" / "lean_project_plan.json").exists())

    def test_next_chapter_window_repairs_an_overfull_response_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text(
                "target_length: 6000\ntarget_chapters: 2\ntarget_scenes: 3\n",
                encoding="utf-8",
            )
            initial = {
                "premise": "旧承诺使林昭欠下一笔债",
                "central_question": "他会怎样履约？",
                "ending_choice": "保住盟友或完成承诺",
                "volume_obligations": ["债务变得不可撤销"],
                "chapters": [
                    {"title": "信件", "dramatic_turn": "承诺公开", "obligation": "建立债务", "reader_question": "谁留下信？"},
                    {"title": "索偿", "dramatic_turn": "盟友离开", "obligation": "兑现代价", "reader_question": "林昭会选择谁？"},
                ],
                "first_window": [_scene("拆信"), _scene("追问")],
            }
            gateway = _Gateway([
                initial,
                {"scenes": [_scene("索偿"), _scene("重复索偿")]},
                {"scenes": [_scene("索偿与选择")]},
            ])
            service = LeanLongformPlanningService(
                {}, data_root=root / "data", gateway=gateway
            )
            service.ensure_initial(root)

            self.assertTrue(service.expand_next_window(root))
            self.assertEqual(len(gateway.calls), 3)
            self.assertIn("chapter window requires exactly 1 scenes", gateway.calls[2][1])
            self.assertIn("不新增尾声与续集钩子", gateway.calls[2][1])
            self.assertTrue((root / "scenes" / "scene_0003.yaml").is_file())


if __name__ == "__main__":
    unittest.main()
