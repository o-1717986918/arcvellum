import tempfile
import unittest
from pathlib import Path

from literary_engineering_studio_engine.prompt_compiler import compile_active_constraints, render_compiled_constraints


class PromptCompilerTests(unittest.TestCase):
    def test_rendered_constraints_include_the_actual_authoritative_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "canon").mkdir()
            (root / "scenes").mkdir()
            (root / "canon" / "world_rules.yaml").write_text("rule: 角色不能凭空得知密信内容。\n", encoding="utf-8")
            (root / "canon" / "forbidden_changes.yaml").write_text("- 不得改变死亡事实\n", encoding="utf-8")
            scene = root / "scenes" / "scene_0001.yaml"
            scene.write_text("scene_id: scene_0001\ngoal: 让角色付出代价。\n", encoding="utf-8")

            compiled = compile_active_constraints(root, scene)
            rendered = render_compiled_constraints(compiled)

            self.assertIn("角色不能凭空得知密信内容", rendered)
            self.assertIn("不得改变死亡事实", rendered)
            self.assertIn("scene_causality", compiled["priority_order"])
            self.assertTrue(compiled["digest"])


if __name__ == "__main__":
    unittest.main()
