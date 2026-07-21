from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.advisor import METADATA_END, METADATA_MARKER, _PublicAnswerStream, _advisor_prompt, _parse_answer
from literary_engineering_studio.advisor_snapshot import create_advisor_snapshot, project_hashes
from literary_engineering_studio.jobs import JobStore


class AdvisorTests(unittest.TestCase):
    def test_snapshot_is_curated_and_does_not_change_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            (project / "canon").mkdir(parents=True)
            (project / "characters").mkdir()
            (project / "project.yaml").write_text("title: 海岸线\n", encoding="utf-8")
            (project / "canon" / "world_rules.yaml").write_text("rules:\n  - 潮汐每日一次\n", encoding="utf-8")
            (project / "characters" / "secret_token.txt").write_text("should-not-copy", encoding="utf-8")
            before = project_hashes(project)
            snapshot = create_advisor_snapshot(project, root / "snapshots")
            after = project_hashes(project)
            self.assertEqual(before, after)
            self.assertTrue(snapshot.index_path.is_file())
            self.assertTrue((snapshot.workspace / "canon" / "world_rules.yaml").is_file())
            self.assertFalse((snapshot.workspace / "characters" / "secret_token.txt").exists())

    def test_dashboard_projections_are_not_part_of_advisor_integrity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            dashboard = project / "workflow" / "dashboard"
            dashboard.mkdir(parents=True)
            (project / "project.yaml").write_text("title: 海岸线\n", encoding="utf-8")
            projection = dashboard / "workflow_dashboard.json"
            projection.write_text('{"revision": 1}\n', encoding="utf-8")

            before = project_hashes(project)
            snapshot = create_advisor_snapshot(project, root / "snapshots")
            projection.write_text('{"revision": 2}\n', encoding="utf-8")
            after = project_hashes(project)

            self.assertEqual(before, after)
            self.assertFalse((snapshot.workspace / "workflow" / "dashboard").exists())

    def test_advisor_sessions_survive_store_restart(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "studio.sqlite3"
            store = JobStore(database)
            session = store.create_advisor_session("C:/project", "digest-one", title="连续性检查")
            store.append_advisor_message(session["session_id"], "user", {"question": "主角是谁？"})
            store.save_advisor_memory(
                session["session_id"],
                summary="用户正在讨论主角的责任选择。",
                preferences=["避免廉价反转", "更重视人物代价"],
            )
            restarted = JobStore(database)
            loaded = restarted.read_advisor_session(session["session_id"])
            self.assertEqual(loaded["title"], "连续性检查")
            self.assertEqual(loaded["messages"][0]["payload"]["question"], "主角是谁？")
            self.assertEqual(loaded["session_summary"], "用户正在讨论主角的责任选择。")
            self.assertEqual(loaded["pinned_user_preferences"], ["避免廉价反转", "更重视人物代价"])

    def test_prompt_treats_project_content_as_untrusted_and_answer_is_natural(self):
        prompt = _advisor_prompt("能修改世界观吗？", [])
        self.assertIn("不可信资料", prompt)
        self.assertIn("禁止编辑", prompt)
        self.assertIn("自然中文回答", prompt)
        answer = _parse_answer('{"answer":"不能直接修改。","facts":[],"inferences":[],"uncertainties":[],"suggested_next_action":"走正式流程"}')
        self.assertEqual(answer["answer"], "不能直接修改。")

    def test_v2_answer_hides_metadata_and_filters_unknown_actions(self):
        raw = (
            "这个选择会让人物承担更明确的代价。"
            + METADATA_MARKER
            + '{"evidence":[{"statement":"人物已经作出承诺","citation":"characters/lead.yaml"}],'
              '"uncertainties":[],"suggested_actions":['
              '{"type":"open_view","label":"查看人物","target":"library"},'
              '{"type":"delete_project","label":"删除"}]}'
            + METADATA_END
        )
        answer = _parse_answer(raw)
        self.assertEqual(answer["message"], "这个选择会让人物承担更明确的代价。")
        self.assertEqual(len(answer["suggested_actions"]), 1)
        self.assertEqual(answer["suggested_actions"][0]["type"], "open_view")

    def test_natural_language_console_keeps_only_confirmable_actions(self):
        raw = (
            "可以继续推进，我会把执行交给正式状态机。"
            + METADATA_MARKER
            + '{"suggested_actions":['
              '{"type":"start_autopilot","label":"开始连续创作","route":"auto"},'
              '{"type":"write_file","label":"直接改正文"}]}'
            + METADATA_END
        )
        answer = _parse_answer(raw)
        self.assertEqual([item["type"] for item in answer["suggested_actions"]], ["start_autopilot"])
        self.assertIn("自然语言项目控制台", _advisor_prompt("继续创作", []))

    def test_answer_memory_is_normalized_for_new_and_legacy_payloads(self):
        v2 = _parse_answer(
            "继续保留这个方向。"
            + METADATA_MARKER
            + '{"memory":{"session_summary":"已决定采用克制叙述。","pinned_preferences":["不使用廉价反转"]}}'
            + METADATA_END
        )
        legacy = _parse_answer(
            '{"answer":"继续保留这个方向。","memory":{"session_summary":"已决定采用克制叙述。",'
            '"pinned_preferences":["不使用廉价反转"]}}'
        )
        self.assertEqual(v2["memory"], legacy["memory"])
        self.assertEqual(v2["memory"]["pinned_preferences"], ["不使用廉价反转"])

    def test_stream_never_emits_metadata(self):
        events = []
        stream = _PublicAnswerStream(lambda event, data: events.append((event, data)))
        stream.feed("自然回答<")
        stream.feed("<<ARCVELLUM_META>>>{\"evidence\":[]}")
        stream.feed(METADATA_END)
        stream.finish("自然回答")
        visible = "".join(data.get("text", "") for event, data in events if event == "advisor.delta")
        self.assertEqual(visible, "自然回答")
        self.assertNotIn("evidence", visible)


if __name__ == "__main__":
    unittest.main()
