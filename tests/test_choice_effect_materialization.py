import tempfile
import unittest
from pathlib import Path

from literary_engineering_studio.config import default_config
from literary_engineering_studio.core_read_models import record_choice
from literary_engineering_studio.project_manager import read_directions


class ChoiceEffectMaterializationTests(unittest.TestCase):
    def test_direction_choice_becomes_task_readable_project_direction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")

            result = record_choice(
                default_config(),
                root,
                {
                    "choice_id": "choice-budget",
                    "route": "longform-planning",
                    "decision_type": "word_budget_direction",
                    "target": {"target_id": "volume_01"},
                    "options": [{"id": "expand_inventory", "label": "扩充剧情库存"}],
                    "selected": "expand_inventory",
                    "rationale": "先扩充分支事件，再分配章节字数。",
                    "actor": "arcvellum-user",
                },
            )

            self.assertEqual(result["effect"]["kind"], "creative-direction")
            self.assertEqual(result["materialized"], "workflow/studio/user_directions.md")
            directions = read_directions(root)
            self.assertEqual(len(directions), 1)
            self.assertIn("expand_inventory", directions[0]["message"])
            self.assertIn("先扩充分支事件", directions[0]["message"])
            self.assertTrue(result["consumed"])
            self.assertTrue(result["materialized_ok"])
            self.assertTrue(result["receipt_id"].startswith("receipt."))

            duplicate = record_choice(
                default_config(),
                root,
                {
                    "choice_id": "choice-budget",
                    "route": "longform-planning",
                    "decision_type": "word_budget_direction",
                    "target": {"target_id": "volume_01"},
                    "options": [{"id": "expand_inventory", "label": "扩充剧情库存"}],
                    "selected": "expand_inventory",
                    "rationale": "重复点击不能制造第二条方向记录。",
                    "actor": "arcvellum-user",
                },
            )
            self.assertEqual(duplicate["receipt_id"], result["receipt_id"])
            self.assertEqual(len(read_directions(root)), 1)

            with self.assertRaisesRegex(ValueError, "不能静默覆盖"):
                record_choice(
                    default_config(),
                    root,
                    {
                        "choice_id": "choice-budget",
                        "route": "longform-planning",
                        "decision_type": "word_budget_direction",
                        "target": {"target_id": "volume_01"},
                        "selected": "compress_inventory",
                    },
                )


if __name__ == "__main__":
    unittest.main()
