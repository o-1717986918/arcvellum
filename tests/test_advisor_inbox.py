from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.advisor_inbox import inbox_snapshot, refresh_advisor_inbox, save_inbox_settings
from literary_engineering_studio.jobs import JobStore


class AdvisorInboxStoreTests(unittest.TestCase):
    def test_notices_are_persistent_deduplicated_and_readable(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "studio.sqlite3"
            store = JobStore(database)
            first = store.upsert_advisor_inbox(
                "C:/work",
                dedupe_key="reader:scene-1:hash",
                kind="prose_promoted",
                severity="success",
                title="新正文",
                message="第一场可以阅读了。",
            )
            second = store.upsert_advisor_inbox(
                "C:/work",
                dedupe_key="reader:scene-1:hash",
                kind="prose_promoted",
                severity="success",
                title="重复",
                message="不会重复插入。",
            )
            self.assertTrue(first["inserted"])
            self.assertFalse(second["inserted"])
            self.assertEqual(len(store.advisor_inbox("C:/work")), 1)
            self.assertEqual(store.advisor_inbox("C:/work")[0]["title"], "重复")
            store.mark_advisor_inbox_read(first["item_id"])
            restarted = JobStore(database)
            self.assertFalse(restarted.advisor_inbox("C:/work")[0]["unread"])

    def test_active_mode_adds_deduplicated_next_action_notice(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            data_root = Path(temporary) / "data"
            store = JobStore(data_root / "studio.sqlite3")
            config = {"application": {"data_root": str(data_root)}}
            save_inbox_settings(data_root, root, {"mode": "active", "quiet_start": "22:30", "quiet_end": "08:00"})
            dashboard = {
                "route_audits": [],
                "next_actions": [
                    {"route": "scene-development", "target": "scene_0002", "next_action": "准备第二场的角色推演。"}
                ],
            }
            with patch("literary_engineering_studio.advisor_inbox.current_choices", return_value={"items": []}), patch(
                "literary_engineering_studio.advisor_inbox.build_dashboard", return_value=dashboard
            ), patch("literary_engineering_studio.advisor_inbox.build_reader_manifest", return_value={"units": []}):
                first = refresh_advisor_inbox(config, store, root)
                second = refresh_advisor_inbox(config, store, root)

            matching = [item for item in first["items"] if item["kind"] == "next_action_ready"]
            self.assertEqual(len(matching), 1)
            self.assertEqual(len(second["items"]), 1)

    def test_standard_mode_does_not_send_next_action_notice(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            data_root = Path(temporary) / "data"
            store = JobStore(data_root / "studio.sqlite3")
            config = {"application": {"data_root": str(data_root)}}
            dashboard = {
                "route_audits": [],
                "next_actions": [{"route": "scene-development", "target": "scene_0002", "next_action": "继续创作。"}],
            }
            with patch("literary_engineering_studio.advisor_inbox.current_choices", return_value={"items": []}), patch(
                "literary_engineering_studio.advisor_inbox.build_dashboard", return_value=dashboard
            ), patch("literary_engineering_studio.advisor_inbox.build_reader_manifest", return_value={"units": []}):
                snapshot = refresh_advisor_inbox(config, store, root)

            self.assertFalse(any(item["kind"] == "next_action_ready" for item in snapshot["items"]))

    def test_snapshot_humanizes_legacy_workflow_messages(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            store = JobStore(Path(temporary) / "studio.sqlite3")
            store.upsert_advisor_inbox(
                str(root.resolve()),
                dedupe_key="legacy-longform",
                kind="workflow_blocked",
                severity="blocking",
                title="创作流程在等待补齐",
                message="目标达到中长篇规模或正在执行 longform-planning；先运行 word-budget / longform-budget。",
            )

            snapshot = inbox_snapshot(store, root)

            self.assertEqual(snapshot["items"][0]["message"], "先完成全书到场景的字数预算。")
            self.assertNotIn("word-budget", snapshot["items"][0]["message"])


if __name__ == "__main__":
    unittest.main()
