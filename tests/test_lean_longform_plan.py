import tempfile
from pathlib import Path
import unittest

from literary_engineering_studio_engine.literary.planning.lean_plan import (
    chapter_obligations,
    normalize_initial_plan,
    normalize_rhythm_role,
    normalize_scene_window,
    render_outline,
)
from literary_engineering_studio_engine.literary.planning.service import calculate_word_budget


def _scene(name: str) -> dict[str, object]:
    return {
        "name": name,
        "function": "mainline_action",
        "participants": ["林昭"],
        "conflict": "承诺与现实冲突",
        "information_release": "新证据出现",
        "consequence": "林昭改变行动",
        "setup_payoff_role": "兑现旧承诺",
        "rhythm_role": "escalation",
        "obligation": "改变主角选择",
    }


class LeanLongformPlanTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "project.yaml").write_text(
            "target_length: 6000\ntarget_chapters: 2\ntarget_scenes: 3\n",
            encoding="utf-8",
        )
        self.budget = calculate_word_budget(self.root)

    def test_initial_plan_owns_ids_and_exact_scene_targets(self):
        answer = {
            "premise": "一份旧承诺改变两个人的命运",
            "central_question": "林昭会付出什么代价？",
            "ending_choice": "履约并失去家，或者背约保住家",
            "volume_obligations": ["第一卷制造不可撤回的债务"],
            "chapters": [
                {"title": "欠债", "dramatic_turn": "秘密被发现", "obligation": "建立债务", "reader_question": "谁留下了承诺？"},
                {"title": "索偿", "dramatic_turn": "盟友要求兑现", "obligation": "代价扩大", "reader_question": "林昭会选择谁？"},
            ],
            "first_window": [_scene("信件"), _scene("争执")],
        }

        plan = normalize_initial_plan(answer, self.budget, project_digest="abc")
        self.assertEqual([scene["scene_id"] for scene in plan["scenes"]], ["scene_0001", "scene_0002"])
        self.assertEqual(sum(scene["target_chars"] for scene in plan["scenes"]), self.budget["chapter_budgets"][0]["target_words"])
        self.assertEqual(plan["chapters"][1]["chapter_id"], "chapter_0002")
        self.assertEqual(
            plan["event_budget"],
            [
                {
                    "chapter_id": "chapter_0001",
                    "irreversible_change": "秘密被发现",
                    "scene_ids": ["scene_0001", "scene_0002"],
                },
                {
                    "chapter_id": "chapter_0002",
                    "irreversible_change": "盟友要求兑现",
                    "scene_ids": [],
                },
            ],
        )
        self.assertIn("秘密被发现", render_outline(plan))
        self.assertIn("chapter_0002", chapter_obligations(plan))

        second = normalize_scene_window(
            [_scene("索偿")], self.budget["chapter_budgets"][1], start_index=3
        )
        self.assertEqual(second[0]["scene_id"], "scene_0003")
        self.assertEqual(second[0]["target_chars"], self.budget["chapter_budgets"][1]["target_words"])

    def test_rejects_shortcut_chapters_and_scene_counts(self):
        with self.assertRaisesRegex(ValueError, "exactly 2 chapter turns"):
            normalize_initial_plan({"chapters": []}, self.budget, project_digest="abc")
        with self.assertRaisesRegex(ValueError, "exactly 2 scenes"):
            normalize_scene_window([_scene("summary")], self.budget["chapter_budgets"][0], start_index=1)

    def test_creative_rhythm_descriptions_are_normalized_before_materialization(self):
        self.assertEqual(
            normalize_rhythm_role("慢起，以劳作引入，结尾发现旧信", "建立人物日常"),
            "setup",
        )
        self.assertEqual(
            normalize_rhythm_role("真相加速冲突，最终平缓收束并和解", "完成旧承诺"),
            "payoff",
        )

        setup = _scene("发现")
        setup["rhythm_role"] = "慢起，以日常引入"
        payoff = _scene("选择")
        payoff["rhythm_role"] = "回收线索并完成和解"
        scenes = normalize_scene_window(
            [setup, payoff], self.budget["chapter_budgets"][0], start_index=1
        )
        self.assertEqual([scene["rhythm_role"] for scene in scenes], ["setup", "payoff"])


if __name__ == "__main__":
    unittest.main()
