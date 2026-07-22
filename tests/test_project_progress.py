from __future__ import annotations

import unittest

from literary_engineering_studio.project_progress import build_project_progress


class ProjectProgressTests(unittest.TestCase):
    def test_waits_for_word_target_instead_of_inventing_overall_progress(self):
        result = build_project_progress(
            {"summary": {}, "route_audits": []},
            {"project": {"excerpt": "一个可靠的创作方向", "facts": [{"label": "目标长度", "value": "未设置"}]}, "counts": {}},
            {"total_chinese_content_chars": 1200, "warnings": []},
        )
        self.assertEqual(result["status"], "waiting_calibration")
        self.assertIsNone(result["overall_percent"])
        manuscript = next(item for item in result["parts"] if item["id"] == "manuscript")
        self.assertIsNone(manuscript["percent"])

    def test_uses_only_formal_reader_content_and_explicit_gate_evidence(self):
        audits = [
            {"route": "scene-development", "blocking_count": 0},
            {"route": "review-and-audit", "blocking_count": 0},
        ]
        result = build_project_progress(
            {"summary": {"pending_task_count": 0}, "route_audits": audits},
            {
                "project": {"excerpt": "一个可靠的创作方向", "facts": [{"label": "目标长度", "value": "10,000 字"}]},
                "counts": {"world": 1, "characters": 2, "style": 1, "scenes": 12, "word_budget": 1, "rhythm": 12},
            },
            {"total_chinese_content_chars": 5000, "warnings": []},
        )
        self.assertEqual(result["status"], "calibrated")
        self.assertEqual(result["overall_percent"], 70.0)
        manuscript = next(item for item in result["parts"] if item["id"] == "manuscript")
        self.assertEqual(manuscript["percent"], 50.0)


if __name__ == "__main__":
    unittest.main()
