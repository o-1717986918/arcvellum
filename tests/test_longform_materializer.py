from pathlib import Path
import json
import tempfile
import unittest

from literary_engineering_studio_engine.longform_materializer import (
    longform_materialization_status,
    materialize_longform_plan,
    planned_longform_outputs,
)


class LongformMaterializerTests(unittest.TestCase):
    def test_reviewed_inventory_materializes_formal_outline_and_scene_contracts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_inputs(root)
            scaffold = root / "scenes" / "scene_0001.yaml"
            scaffold.parent.mkdir(parents=True)
            scaffold.write_text('scene_id: ""\nchapter_id: ""\n', encoding="utf-8")

            result = materialize_longform_plan(root)

            self.assertEqual(len(result.scene_paths), 2)
            first = (root / "scenes/scene_0001.yaml").read_text(encoding="utf-8")
            second = (root / "scenes/scene_0002.yaml").read_text(encoding="utf-8")
            self.assertIn('scene_id: "scene_0001"', first)
            self.assertIn('chapter_id: "chapter_0001"', first)
            self.assertIn("word_count_target: 1200", first)
            self.assertIn("林昭", first)
            self.assertIn("tension_curve:\n    entry: 1\n    peak: 3\n    exit: 2", first)
            self.assertIn('incoming_pressure: "全书开场：人物原有生活秩序即将被当前事件打破。"', first)
            self.assertIn('scene_id: "scene_0002"', second)
            self.assertIn('incoming_pressure: "林昭带着疑问入学"', second)
            self.assertIn("正式长篇大纲", result.outline_path.read_text(encoding="utf-8"))
            passed, message = longform_materialization_status(root)
            self.assertTrue(passed, message)
            self.assertEqual(
                planned_longform_outputs(root),
                [
                    "plot/outline.md",
                    "scenes/scene_0001.yaml",
                    "scenes/scene_0002.yaml",
                    "workflow/longform_materialization.json",
                ],
            )

    def test_materializer_refuses_to_overwrite_developed_scene(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_inputs(root)
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text('scene_id: "scene_0001"\nscene_goal: "already developed"\n', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                materialize_longform_plan(root)

    def test_materializer_adopts_matching_formal_scenes_after_planning_digest_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_inputs(root)
            materialize_longform_plan(root)
            scene_path = root / "scenes/scene_0001.yaml"
            outline_path = root / "plot/outline.md"
            original_scene = scene_path.read_text(encoding="utf-8")
            original_outline = outline_path.read_text(encoding="utf-8")
            expansion = root / "plot/candidates/outlines/word_budget_expansion.md"
            expansion.write_text(expansion.read_text(encoding="utf-8") + "\n<!-- revised planning note -->\n", encoding="utf-8")

            result = materialize_longform_plan(root)

            self.assertEqual(scene_path.read_text(encoding="utf-8"), original_scene)
            self.assertEqual(outline_path.read_text(encoding="utf-8"), original_outline)
            payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["materialization_mode"], "adopted-existing")
            passed, message = longform_materialization_status(root)
            self.assertTrue(passed, message)

    def test_materializer_refuses_to_adopt_conflicting_formal_scene_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_inputs(root)
            materialize_longform_plan(root)
            scene_path = root / "scenes/scene_0001.yaml"
            scene_path.write_text(
                scene_path.read_text(encoding="utf-8").replace("word_count_target: 1200", "word_count_target: 9999"),
                encoding="utf-8",
            )
            expansion = root / "plot/candidates/outlines/word_budget_expansion.md"
            expansion.write_text(expansion.read_text(encoding="utf-8") + "\n<!-- revised planning note -->\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "manual reconciliation required"):
                materialize_longform_plan(root)

    def test_card_inventory_from_earlier_studio_runs_is_materialized(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_inputs(root)
            inventory = root / "plot/candidates/scenes/word_budget_scene_inventory.md"
            inventory.write_text(
                """# 场景库存候选

### chapter_0001 | 初入迷城

#### s_01_01 | 告别

| 字段 | 内容 |
| --- | --- |
| **目标汉字字符** | 1200 |
| **功能** | mainline_action |
| **节奏角色** | setup |
| **参与角色** | 林昭、林正 |
| **冲突** | 父子必须分离 |
| **信息释放** | 父亲知道学院秘密 |
| **行动后果** | 林昭带着疑问入学 |
| **设置伏笔** | 父亲的秘密 |
| **读者义务** | 建立分离与秘密 |

#### s_01_02 | 测试

| 字段 | 内容 |
| --- | --- |
| **目标汉字字符** | 1200 |
| **功能** | information_release |
| **节奏角色** | escalation |
| **参与角色** | 林昭、周瑾 |
| **冲突** | 测试结果被隐藏 |
| **信息释放** | 周瑾知道异常 |
| **行动后果** | 林昭被暗中标记 |
| **设置伏笔** | 能力异常 |
| **读者义务** | 建立能力谜题 |
""",
                encoding="utf-8",
            )
            scaffold = root / "scenes/scene_0001.yaml"
            scaffold.parent.mkdir(parents=True)
            scaffold.write_text('scene_id: ""\nchapter_id: ""\n', encoding="utf-8")

            result = materialize_longform_plan(root)

            self.assertEqual(len(result.scene_paths), 2)
            first = (root / "scenes/scene_0001.yaml").read_text(encoding="utf-8")
            self.assertIn('title: "告别"', first)
            self.assertIn('chapter_id: "chapter_0001"', first)

    def test_scoped_status_allows_a_staged_active_scene_without_copying_full_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_inputs(root)
            scaffold = root / "scenes" / "scene_0001.yaml"
            scaffold.parent.mkdir(parents=True)
            scaffold.write_text('scene_id: ""\nchapter_id: ""\n', encoding="utf-8")
            materialize_longform_plan(root)

            (root / "scenes" / "scene_0002.yaml").unlink()
            full_passed, _ = longform_materialization_status(root)
            scoped_passed, scoped_message = longform_materialization_status(
                root,
                scene_path=root / "scenes" / "scene_0001.yaml",
            )

            self.assertFalse(full_passed)
            self.assertTrue(scoped_passed, scoped_message)
            self.assertIn("scenes/scene_0001.yaml", scoped_message)

    @staticmethod
    def _write_inputs(root: Path) -> None:
        files = {
            "project.yaml": "project:\n  title: 测试作品\n",
            "plot/candidates/outlines/word_budget_expansion.md": "# 三卷故事扩展\n\n第一章从告别开始，第二章让秘密产生代价。\n" * 8,
            "plot/candidates/scenes/word_budget_scene_inventory.md": """# 场景库存

## 卷一：开端

### Ch 0001 — 星辰之门 | 目标 2400

| scene_id | name | target_chars | function | participants | conflict | information_release | consequence | setup_payoff_role | rhythm_role | obligation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SC-001 | 告别 | 1200 | mainline | 林昭、林正 | 父子必须分离 | 父亲知道学院秘密 | 林昭带着疑问入学 | setup：父亲秘密 | setup | 建立分离与秘密 |
| SC-002 | 测试 | 1200 | information | 林昭、周瑾 | 测试结果被隐藏 | 周瑾知道异常 | 林昭被暗中标记 | setup：能力异常 | escalation | 建立能力谜题 |
""",
            "plot/candidates/chapters/chapter_obligation_plan.md": """# 章节义务

### Ch 0001 — 星辰之门

| 字段 | 内容 |
| --- | --- |
| 读者进入问题 | 学院为什么带走林昭？ |
| 承诺回报 | 看见能力测试的真实代价 |
| 暂扣信息 | 父亲的身份；周瑾的目的 |
| 兑现/延迟 | 延迟到第八章兑现 |
| 反摘要要求 | 必须写出分离与测试两个独立场面 |
| 章末钩子 | 北楼传来不应存在的哭声 |
""",
            "plot/word_budget/word_budget.json": json.dumps(
                {"schema": "literary-engineering-workbench/word-budget/v1", "totals": {"scene_count": 2}},
                ensure_ascii=False,
            ),
        }
        for rel, content in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
