"""Event-first replacement of only the unwritten lean-plan suffix."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import hashlib

from ruamel.yaml import YAML

from literary_engineering_studio.application.lean_future_replan import replan_lean_future
from literary_engineering_studio_engine.public.literary import (
    calculate_word_budget,
    chapter_obligations,
    materialize_lean_window,
    normalize_initial_plan,
    normalize_scene_window,
    render_outline,
)

from tests.test_lean_longform_plan import _scene


class _Gateway:
    def __init__(self):
        self.calls = 0
        self.prompts = []

    def run(self, workspace, prompt, *, role, timeout):
        self.prompts.append(prompt)
        chapters = [
            {
                "chapter_id": "chapter_0001",
                "irreversible_change": "债务已经落到林昭名下",
                "scenes": [],
            },
            {
                "chapter_id": "chapter_0002",
                "irreversible_change": "盟友公开站到林昭的对面",
                "scenes": [
                    {
                        **_scene("盟友索偿"),
                        "information_release": "盟友已经向全村公开债务",
                        "consequence": "林昭的私下退路被截断",
                    },
                    {**_scene("证词失效"), "consequence": "林昭失去唯一公开证人"},
                ],
            },
            {
                "chapter_id": "chapter_0003",
                "irreversible_change": "林昭以失去归处为代价履约",
                "scenes": [
                    {**_scene("终局履约"), "consequence": "林昭履约后永久离开故乡"},
                ],
            },
        ]
        answer = json.dumps({"chapters": chapters}, ensure_ascii=False)
        self.calls += 1
        return type("Response", (), {"answer": answer})()


class LeanFutureReplanTests(unittest.TestCase):
    def _project(self, root: Path) -> tuple[Path, Path]:
        project = root / "project.yaml"
        project.write_text(
            "target_length: 12000\ntarget_chapters: 3\ntarget_scenes: 4\n",
            encoding="utf-8",
        )
        budget = calculate_word_budget(
            root, target_words=12000, target_chapters=3, target_scenes=4, volumes=1,
        )
        plan = normalize_initial_plan({
            "premise": "一封旧信改变承诺",
            "central_question": "林昭是否履约？",
            "ending_choice": "承担代价",
            "volume_obligations": ["兑现旧约"],
            "chapters": [
                {
                    "title": f"第{index}章",
                    "dramatic_turn": f"第{index}项责任不可逆转",
                    "obligation": "推进选择",
                    "reader_question": "谁承担？",
                }
                for index in range(1, 4)
            ],
            "first_window": [_scene("收到旧信"), _scene("承担债务")],
            "characters": [{
                "name": "林昭", "role": "主角", "importance": "major",
                "background": "摆渡人", "desire": "守约",
            }],
            "world_facts": [],
        }, budget, project_digest="test")
        plan["scenes"].extend(normalize_scene_window(
            [_scene("重复核对")], budget["chapter_budgets"][1], start_index=3,
        ))
        plan["scenes"].extend(normalize_scene_window(
            [_scene("再次核对")], budget["chapter_budgets"][2], start_index=4,
        ))
        plan_path = root / "plot" / "lean_project_plan.json"
        budget_path = root / "plot" / "word_budget" / "word_budget.json"
        budget_path.parent.mkdir(parents=True)
        plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        budget_path.write_text(json.dumps(budget, ensure_ascii=False), encoding="utf-8")
        materialize_lean_window(
            root,
            scenes=plan["scenes"],
            obligations=chapter_obligations(plan),
            sources=(project, plan_path, budget_path),
            outline_text=render_outline(plan),
        )
        commit_dir = root / "workflow" / "scene_commits"
        draft_dir = root / "drafts" / "scenes"
        commit_dir.mkdir(parents=True)
        draft_dir.mkdir(parents=True)
        for scene_id in ("scene_0001", "scene_0002"):
            (commit_dir / f"{scene_id}.json").write_text("{}\n", encoding="utf-8")
            (draft_dir / f"{scene_id}.md").write_text(f"{scene_id} 已成稿。\n", encoding="utf-8")
        return plan_path, budget_path

    def test_replaces_only_future_and_rebalances_capacity_around_events(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan_path, budget_path = self._project(root)
            committed_contracts = [
                (root / "scenes" / f"scene_{index:04d}.yaml").read_bytes()
                for index in (1, 2)
            ]
            gateway = _Gateway()
            result = replan_lean_future(
                root,
                gateway,
                chapter_scene_counts={
                    "chapter_0001": 2,
                    "chapter_0002": 2,
                    "chapter_0003": 1,
                },
                direction="保留已写两场；后续只写索偿、证词失效和履约代价。",
            )

            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            budget = json.loads(budget_path.read_text(encoding="utf-8"))
            self.assertEqual(result["future_scene_ids"], ["scene_0003", "scene_0004", "scene_0005"])
            self.assertEqual(result["book_scene_count"], 5)
            self.assertEqual(budget["totals"]["target_chinese_chars"], 12000)
            self.assertEqual(budget["target"]["structure_source"], "event_budget_replan")
            project = YAML(typ="safe").load((root / "project.yaml").read_text(encoding="utf-8"))
            self.assertEqual(project["longform_budget"]["target_scenes"], 5)
            self.assertEqual(
                plan["project_digest"],
                hashlib.sha256((root / "project.yaml").read_bytes()).hexdigest(),
            )
            self.assertEqual(len(plan["scenes"]), 5)
            self.assertEqual(
                [
                    (root / "scenes" / f"scene_{index:04d}.yaml").read_bytes()
                    for index in (1, 2)
                ],
                committed_contracts,
            )
            self.assertIn("盟友公开站到林昭的对面", json.dumps(plan["event_budget"], ensure_ascii=False))
            self.assertTrue((root / result["history_path"] / "receipt.json").is_file())
            self.assertEqual(gateway.calls, 1)
            self.assertTrue(all("均不得重演" in prompt for prompt in gateway.prompts))


if __name__ == "__main__":
    unittest.main()
