"""Controlled append-only chapter repair available to Project Agent."""

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.application.lean_chapter_extension import extend_lean_chapter
from literary_engineering_studio_engine.public.literary import (
    calculate_word_budget, chapter_obligations, materialize_lean_window,
    normalize_initial_plan, normalize_scene_window, render_outline,
)

from tests.test_lean_longform_plan import _scene


class _Gateway:
    def run(self, workspace, prompt, *, role, timeout):
        self.prompt = prompt
        return type("Response", (), {"answer": json.dumps({"scenes": [_scene("尾声之后的新选择")]}, ensure_ascii=False)})()


class _ConcurrentGateway(_Gateway):
    def run(self, workspace, prompt, *, role, timeout):
        plan = workspace / "plot" / "lean_project_plan.json"
        plan.write_text(plan.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        return super().run(workspace, prompt, role=role, timeout=timeout)


class LeanChapterExtensionTests(unittest.TestCase):
    def _project(self, root: Path):
        (root / "project.yaml").write_text(
            "target_length: 15000\ntarget_chapters: 3\ntarget_scenes: 3\n", encoding="utf-8",
        )
        budget = calculate_word_budget(root, target_words=15000, target_chapters=3, target_scenes=3, volumes=1)
        plan = normalize_initial_plan({
            "premise": "一封旧信改变承诺", "central_question": "林昭是否履约？",
            "ending_choice": "承担代价", "volume_obligations": ["兑现旧约"],
            "chapters": [
                {"title": f"第{i}章", "dramatic_turn": f"第{i}次责任转移", "obligation": "推进选择", "reader_question": "谁承担？"}
                for i in range(1, 4)
            ],
            "first_window": [_scene("开端")],
            "characters": [{"name": "林昭", "role": "主角", "importance": "major", "background": "摆渡人", "desire": "守约"}],
            "world_facts": [],
        }, budget, project_digest="test")
        plan["scenes"].extend(normalize_scene_window(
            [_scene("旧信")], budget["chapter_budgets"][1], start_index=2,
        ))
        plan_path = root / "plot" / "lean_project_plan.json"
        budget_path = root / "plot" / "word_budget" / "word_budget.json"
        budget_path.parent.mkdir(parents=True)
        plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        budget_path.write_text(json.dumps(budget, ensure_ascii=False), encoding="utf-8")
        materialize_lean_window(
            root, scenes=plan["scenes"], obligations=chapter_obligations(plan),
            sources=(root / "project.yaml", plan_path, budget_path),
            outline_text=render_outline(plan),
        )
        (root / "workflow" / "scene_commits").mkdir(parents=True)
        (root / "workflow" / "scene_commits" / "scene_0002.json").write_text("{}", encoding="utf-8")
        (root / "drafts" / "scenes").mkdir(parents=True)
        (root / "drafts" / "scenes" / "scene_0002.md").write_text("结尾的承诺没有说破。", encoding="utf-8")
        return plan_path, budget_path

    def test_appends_after_committed_scene_and_preserves_book_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan_path, budget_path = self._project(root)
            old_scene = (root / "scenes" / "scene_0002.yaml").read_bytes()
            gateway = _Gateway()
            result = extend_lean_chapter(
                root, gateway, chapter_id="chapter_0002", additional_scenes=1,
                target_per_scene=3300, direction="承接旧信，不提前揭晓第三章。",
            )
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            budget = json.loads(budget_path.read_text(encoding="utf-8"))
            self.assertEqual(result["appended_scene_ids"], ["scene_0003"])
            self.assertEqual(result["next_uncommitted_scene_id"], "scene_0003")
            self.assertEqual(result["chapter_target_chinese_chars"], 5000)
            self.assertIn("historical", result["checkpoint_state"])
            self.assertEqual([row["chapter_id"] for row in plan["scenes"]], ["chapter_0001", "chapter_0002", "chapter_0002"])
            self.assertEqual((root / "scenes" / "scene_0002.yaml").read_bytes(), old_scene)
            self.assertTrue((root / "scenes" / "scene_0003.yaml").is_file())
            self.assertEqual(budget["totals"]["target_words"], 15000)
            self.assertEqual(budget["chapter_budgets"][1]["scene_count"], 2)
            self.assertGreater(budget["chapter_budgets"][2]["scene_count"], 1)
            self.assertIn("不得把新场景倒插", gateway.prompt)

    def test_uncommitted_scene_cannot_be_extended(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan_path, _ = self._project(root)
            (root / "workflow" / "scene_commits" / "scene_0002.json").unlink()
            previous = plan_path.read_bytes()
            with self.assertRaisesRegex(ValueError, "committed"):
                extend_lean_chapter(
                    root, _Gateway(), chapter_id="chapter_0002", additional_scenes=1,
                    target_per_scene=3300, direction="继续",
                )
            self.assertEqual(plan_path.read_bytes(), previous)

    def test_concurrent_plan_change_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan_path, budget_path = self._project(root)
            original_budget = budget_path.read_bytes()
            with self.assertRaisesRegex(ValueError, "changed while"):
                extend_lean_chapter(
                    root, _ConcurrentGateway(), chapter_id="chapter_0002", additional_scenes=1,
                    target_per_scene=3300, direction="从旧信之后继续。",
                )
            self.assertTrue(plan_path.read_bytes().endswith(b"\n"))
            self.assertEqual(budget_path.read_bytes(), original_budget)
            self.assertFalse((root / "scenes" / "scene_0003.yaml").exists())


if __name__ == "__main__":
    unittest.main()
