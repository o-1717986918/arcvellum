from pathlib import Path
import json
import tempfile
import unittest

from literary_engineering_studio_engine.agent_tasks import write_agent_completion_marker
from literary_engineering_studio_engine.reader_experience import (
    CHAPTER_OBLIGATION_SCHEMA,
    chapter_obligation_contract_issues,
    chapter_obligation_contract,
)


class ReaderExperienceContractTests(unittest.TestCase):
    def test_opening_chapter_allows_empty_payoff_and_inherited_hook_lists(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("target_length: 100000\n", encoding="utf-8")
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text(
                "scene_id: scene_0001\nchapter_id: chapter_0001\n",
                encoding="utf-8",
            )
            contract = root / "plot" / "chapter_obligations" / "chapter_0001.json"
            contract.parent.mkdir(parents=True)
            contract.write_text(
                json.dumps(
                    {
                        "schema": CHAPTER_OBLIGATION_SCHEMA,
                        "chapter_id": "chapter_0001",
                        "status": "pass",
                        "chapter_function": "建立开场冲突",
                        "must_payoff": [],
                        "must_setup": ["人物必须离开故乡"],
                        "must_change": ["人物进入新环境"],
                        "must_not_resolve": ["谜题的答案"],
                        "inherited_hooks": [],
                        "ending_hook": "门后传来陌生声音",
                        "inventory_sufficiency": "sufficient",
                        "expansion_needed": [],
                        "reader_experience_by_scene": [
                            {
                                "scene_id": "scene_0001",
                                "reader_question": "门后是谁？",
                                "promised_reward": "确认陌生声音的来源",
                                "withheld_information": ["来者目的"],
                                "payoff_or_delay": "本场确认身份，目的后延",
                                "emotional_curve": ["平静", "警觉"],
                                "tension_source": "陌生声音逼近",
                                "curiosity_hook": "门后的身份",
                                "freshness_requirement": "以行动核验声音",
                                "anti_summary_requirement": "完整呈现开门前的选择",
                                "reader_aftertaste": "人物必须面对来者",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            task_path = contract.with_suffix(".agent_tasks.md")
            task_path.write_text("# chapter obligation\n", encoding="utf-8")
            write_agent_completion_marker(task_path, root=root, handled_by="test")

            result = chapter_obligation_contract(root, scene)

            self.assertEqual(result["status"], "pass")

    def test_contract_rejects_non_list_optional_hook_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("target_length: 100000\n", encoding="utf-8")
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text(
                "scene_id: scene_0001\nchapter_id: chapter_0001\n",
                encoding="utf-8",
            )
            contract = root / "plot" / "chapter_obligations" / "chapter_0001.json"
            contract.parent.mkdir(parents=True)
            contract.write_text(
                json.dumps(
                    {
                        "schema": CHAPTER_OBLIGATION_SCHEMA,
                        "chapter_id": "chapter_0001",
                        "status": "pass",
                        "chapter_function": "建立开场冲突",
                        "must_payoff": "not a list",
                        "must_setup": ["人物必须离开故乡"],
                        "must_change": ["人物进入新环境"],
                        "must_not_resolve": ["谜题的答案"],
                        "inherited_hooks": [],
                        "ending_hook": "门后传来陌生声音",
                        "inventory_sufficiency": "sufficient",
                        "expansion_needed": [],
                        "reader_experience_by_scene": [{"scene_id": "scene_0001"}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            task_path = contract.with_suffix(".agent_tasks.md")
            task_path.write_text("# chapter obligation\n", encoding="utf-8")
            write_agent_completion_marker(task_path, root=root, handled_by="test")

            result = chapter_obligation_contract(root, scene)

            self.assertEqual(result["status"], "incomplete")
            self.assertIn("chapter obligation field must be a list: must_payoff", result["issues"])

    def test_contract_rejects_boolean_expansion_needed_from_live_failure(self):
        payload = {
            "chapter_function": "建立燃料冲突",
            "must_payoff": [],
            "must_setup": ["求救信号"],
            "must_change": ["主角承担代价"],
            "must_not_resolve": ["空间站真相"],
            "inherited_hooks": [],
            "ending_hook": "主角改变航迹",
            "inventory_sufficiency": "sufficient",
            "expansion_needed": False,
            "reader_experience_by_scene": [{"scene_id": "scene_0001"}],
        }

        self.assertIn(
            "chapter obligation field must be a list: expansion_needed",
            chapter_obligation_contract_issues(payload),
        )

    def test_contract_rejects_non_list_required_obligation_fields(self):
        payload = {
            "chapter_function": "建立燃料冲突",
            "must_payoff": [],
            "must_setup": "求救信号",
            "must_change": ["主角承担代价"],
            "must_not_resolve": ["空间站真相"],
            "inherited_hooks": [],
            "ending_hook": "主角改变航迹",
            "inventory_sufficiency": "sufficient",
            "expansion_needed": [],
            "reader_experience_by_scene": [{"scene_id": "scene_0001"}],
        }

        self.assertIn(
            "chapter obligation field must be a list: must_setup",
            chapter_obligation_contract_issues(payload),
        )


if __name__ == "__main__":
    unittest.main()
