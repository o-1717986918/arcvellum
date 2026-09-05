from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.context_packet import _plot_context, build_context_packet


class ContextPacketCompactionTests(unittest.TestCase):
    def test_context_hard_loads_location_and_organization_canon(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: 星潮\n", encoding="utf-8")
            scene = root / "scenes/scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text("scene_id: scene_0001\nlocation: 盐港\n", encoding="utf-8")
            canon = root / "canon"
            canon.mkdir()
            (canon / "locations.yaml").write_text("盐港:\n  rule: 禁止夜间鸣钟\n", encoding="utf-8")
            (canon / "organizations.yaml").write_text("守潮会:\n  duty: 登记潮汐异常\n", encoding="utf-8")

            result = build_context_packet(root, scene=scene)
            context = result.output_path.read_text(encoding="utf-8")

            self.assertIn("禁止夜间鸣钟", context)
            self.assertIn("登记潮汐异常", context)

    def test_plot_context_keeps_current_and_neighbor_chapters_not_whole_outline(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plot = root / "plot"
            plot.mkdir()
            chapters = []
            for index in range(1, 11):
                chapters.append(
                    f"### Ch {index:04d} — 第{index}章\n\n"
                    f"本章唯一标记 CHAPTER-{index:04d}。\n\n"
                )
            (plot / "outline.md").write_text(
                "# 正式大纲\n\n## 世界设定摘要\n\n世界规则。\n\n## 卷一：开端\n\n卷级节奏。\n\n"
                + "\n".join(chapters),
                encoding="utf-8",
            )
            (plot / "foreshadowing.csv").write_text("id,status\nF1,open\n", encoding="utf-8")

            selected = _plot_context(root, "chapter_id: chapter_0005\n")

            self.assertIn("CHAPTER-0004", selected)
            self.assertIn("CHAPTER-0005", selected)
            self.assertIn("CHAPTER-0006", selected)
            self.assertNotIn("CHAPTER-0001", selected)
            self.assertNotIn("CHAPTER-0010", selected)
            self.assertIn("世界规则", selected)
            self.assertIn("F1,open", selected)


if __name__ == "__main__":
    unittest.main()
