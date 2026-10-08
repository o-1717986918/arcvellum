from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from literary_engineering_studio.runtimes.scene_review_continuity import (
    formal_review_payload,
    record_review,
    review_continuity,
)


class SceneReviewContinuityTests(unittest.TestCase):
    def test_issue_identity_and_progress_are_ordered_and_bound_to_each_prose(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_prose = "她把碗翻過來放下。湯要進碗時，碗仍扣在桌上。"
            first = record_review(root, first_prose, {
                "summary": "器物動作中斷了閱讀。",
                "major_issues": [{"title": "碗的朝向前后不接", "evidence": "碗仍扣在桌上。",
                    "reader_effect": "讀者無法跟隨盛湯動作", "direction": "補出翻正的動作。"}],
            }, {"decision": "revise", "summary": "碗的朝向影響動作理解。",
                "revision_instructions": ["補出翻正的動作。"], "evidence": ["碗仍扣在桌上。"]},
                "review-1.md")
            identifier = first["issues"][0]["issue_id"]

            second_prose = "她把碗翻過來放下，轉正碗口才盛湯。"
            second = record_review(root, second_prose, {
                "summary": "碗的連續動作已經補上。",
                "issue_progress": [{"issue_id": identifier, "status": "persists", "evidence": "轉正碗口才盛湯。"}],
                "major_issues": [{"title": "碗的朝向前后不接", "evidence": "轉正碗口才盛湯。",
                    "reader_effect": "動作可以連續讀取", "direction": "維持清楚的動作次序。",
                    "prior_issue_id": identifier}],
            }, {"decision": "revise", "summary": "仍需確認器物動線。",
                "revision_instructions": ["維持清楚的動作次序。"], "evidence": ["轉正碗口才盛湯。"]},
                "review-2.md")
            self.assertEqual(second["sequence"], 2)
            self.assertEqual(second["issues"][0]["issue_id"], identifier)

            third_prose = "她将碗口转正，汤落进去时，手还托着碗沿。"
            third = record_review(root, third_prose, {
                "summary": "器物动作和手的位置都能顺着读。",
                "issue_progress": [{"issue_id": identifier, "status": "resolved",
                                    "evidence": "手还托着碗沿。"}],
            }, {"decision": "pass", "summary": "动作线成立。",
                "revision_instructions": [], "evidence": ["手还托着碗沿。"]}, "review-3.md")
            self.assertEqual(third["issues"][0]["status"], "resolved")
            context = review_continuity(root, third_prose)
            self.assertEqual(context["current"]["sequence"], 3)
            self.assertEqual(context["previous"]["sequence"], 2)
            self.assertEqual(context["open_issues"], [])
            self.assertEqual(context["completed_reviews"], 3)

            duplicate = record_review(root, third_prose, {}, {}, "duplicate.md")
            self.assertEqual(duplicate["sequence"], 3)

    def test_unmentioned_prior_issues_remain_uncertain_and_open(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = record_review(root, "雨声停了。", {
                "major_issues": [{"title": "转场时间不明", "evidence": "雨声停了。",
                    "reader_effect": "读者无法判断经过多久", "direction": "补一处时间锚。"}],
            }, {}, "review-1.md")
            latest = record_review(root, "门被推开。", {"summary": "人物位置清楚。"}, {}, "review-2.md")

            self.assertEqual(latest["issues"][0]["issue_id"], first["issues"][0]["issue_id"])
            self.assertEqual(latest["issues"][0]["status"], "uncertain")
            self.assertEqual(review_continuity(root, "门被推开。")["open_issues"][0]["status"], "uncertain")

    def test_legacy_reviews_with_no_order_are_reported_as_ambiguous(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for digest, summary in (("aaaa1111", "旧审读 A"), ("bbbb2222", "旧审读 B")):
                path = root / f"review_result_v2_{digest}.json"
                path.write_text(json.dumps({"summary": summary}, ensure_ascii=False), encoding="utf-8")
            os.utime(root / "review_result_v2_aaaa1111.json", (1, 1))

            result = review_continuity(root, "当前正文")

            self.assertIsNone(result["previous"])
            self.assertEqual(len(result["ambiguous_legacy_reviews"]), 2)

    def test_formal_review_keeps_strengths_repairs_and_explorations_distinct(self):
        formal = formal_review_payload({
            "decision": "revise", "summary": "当前稿有一个动作问题。",
            "strengths": [{"claim": "雨声承接停顿", "evidence": "雨点落在窗沿。"}],
            "major_issues": [{"title": "人物手上物件冲突", "evidence": "她手里仍握着盖子。",
                "reader_effect": "动作状态相互矛盾", "direction": "确认拿起盖子的时点。"}],
            "optional_explorations": [{"question": "停顿是否可以延长", "evidence": "她没有立刻回答。",
                "direction": "让沉默多留一拍。"}],
            "issue_progress": [{"issue_id": "issue-abc", "status": "changed"}],
        })

        self.assertIn("正文已经成立：雨声承接停顿", formal["summary"])
        self.assertIn("主要修订问题：人物手上物件冲突", formal["summary"])
        self.assertIn("可选审美探索：停顿是否可以延长", formal["summary"])
        self.assertEqual(formal["revision_instructions"], ["确认拿起盖子的时点。"])


if __name__ == "__main__":
    unittest.main()
