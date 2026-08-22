from __future__ import annotations

import unittest

from literary_engineering_studio_engine.public.projections import (
    final_body_from_workbench_text,
)


class DraftTextProjectionTests(unittest.TestCase):
    def test_scene_revision_workbench_preamble_is_not_prose(self) -> None:
        source = """# 场景修订稿：scene_0005（对质与两份日志）

> 修订目标：兑现「事故真相是什么」并达到目标字数。

---

## 对质与两份日志

记录卡被推过桌沿。林桓接住了它。
"""

        body = final_body_from_workbench_text(source)

        self.assertEqual(body, "记录卡被推过桌沿。林桓接住了它。")
        self.assertNotIn("「", body)
        self.assertNotIn("修订目标", body)

    def test_literary_markdown_titles_are_preserved(self) -> None:
        source = """# 第一章 归航

## 冬夜

雪落在旧站台上。
"""

        body = final_body_from_workbench_text(source)

        self.assertIn("# 第一章 归航", body)
        self.assertIn("## 冬夜", body)
        self.assertIn("雪落在旧站台上。", body)


if __name__ == "__main__":
    unittest.main()
