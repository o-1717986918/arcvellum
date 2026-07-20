from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.advisor import _advisor_prompt, _parse_answer
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

    def test_advisor_sessions_survive_store_restart(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "studio.sqlite3"
            store = JobStore(database)
            session = store.create_advisor_session("C:/project", "digest-one", title="连续性检查")
            store.append_advisor_message(session["session_id"], "user", {"question": "主角是谁？"})
            restarted = JobStore(database)
            loaded = restarted.read_advisor_session(session["session_id"])
            self.assertEqual(loaded["title"], "连续性检查")
            self.assertEqual(loaded["messages"][0]["payload"]["question"], "主角是谁？")

    def test_prompt_treats_project_content_as_untrusted_and_answer_is_structured(self):
        prompt = _advisor_prompt("能修改世界观吗？", [])
        self.assertIn("不可信资料", prompt)
        self.assertIn("禁止编辑", prompt)
        answer = _parse_answer('{"answer":"不能直接修改。","facts":[],"inferences":[],"uncertainties":[],"suggested_next_action":"走正式流程"}')
        self.assertEqual(answer["answer"], "不能直接修改。")


if __name__ == "__main__":
    unittest.main()
