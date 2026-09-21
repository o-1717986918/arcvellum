import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.application.lean_assets import ensure_lean_planning_assets


class LeanAssetsTests(unittest.TestCase):
    def test_existing_user_assets_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "plot").mkdir()
            (root / "canon").mkdir()
            (root / "characters").mkdir()
            (root / "characters" / "林昭.yaml").write_text(
                'name: "林昭"\nidentity:\n  background: "用户确认的背景"\n',
                encoding="utf-8",
            )
            (root / "canon" / "world_rules.yaml").write_text(
                "rules: [用户规则]\n", encoding="utf-8",
            )
            (root / "plot" / "lean_project_plan.json").write_text(
                json.dumps({
                    "characters": [{
                        "name": "林昭", "role": "主角", "importance": "major",
                        "background": "模型建议", "desire": "履约",
                    }],
                    "world_facts": ["模型建议的规则"],
                }, ensure_ascii=False), encoding="utf-8",
            )
            self.assertEqual(
                ensure_lean_planning_assets(root),
                {"characters_created": 0, "world_rules_created": 0},
            )
            self.assertIn("用户确认的背景", (root / "characters" / "林昭.yaml").read_text(encoding="utf-8"))
            self.assertEqual(
                (root / "canon" / "world_rules.yaml").read_text(encoding="utf-8"),
                "rules: [用户规则]\n",
            )


if __name__ == "__main__":
    unittest.main()
