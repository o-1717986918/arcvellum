from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio_engine.literary.scene.composition.draft import (
    build_scene_draft,
)


class SceneDraftPromptRulesTests(unittest.TestCase):
    def test_draft_distinguishes_iterative_words_and_useful_counts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text("scene_id: scene_0001\n", encoding="utf-8")
            context = root / "memory" / "context_packets" / "scene_0001.md"
            context.parent.mkdir(parents=True)
            context.write_text("## 当前场景\n人物争执。\n", encoding="utf-8")
            trace = context.with_suffix(".trace.json")
            trace.write_text("{}\n", encoding="utf-8")

            with patch(
                "literary_engineering_studio_engine.literary.scene.composition.draft.default_context_trace_path",
                return_value=trace,
            ), patch(
                "literary_engineering_studio_engine.literary.scene.composition.draft.context_trace_status",
                return_value=SimpleNamespace(passed=True),
            ):
                result = build_scene_draft(root, context=context)

            prompt = result.draft_path.read_text(encoding="utf-8")
            self.assertIn("“一个又一个”等虚指反复不是精确计数", prompt)
            self.assertIn("一项实际功能即可保留精度", prompt)
            self.assertIn("人物对白在用词、句法或回避方式上可辨", prompt)
            self.assertNotIn("量词中的数词同样须过五项", prompt)


if __name__ == "__main__":
    unittest.main()
