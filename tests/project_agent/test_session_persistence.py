from pathlib import Path
from contextlib import closing
import sqlite3
import tempfile
import unittest

from literary_engineering_studio.infrastructure.memory import build_memory_persistence_ports
from literary_engineering_studio.persistence.job_store import JobStore
from literary_engineering_studio.persistence.schema import CORE_SCHEMA_SQL


class ProjectAgentSessionPersistenceTests(unittest.TestCase):
    def test_sqlite_keeps_project_agent_sessions_out_of_advisor_list(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = JobStore(Path(temporary) / "studio.sqlite3")

            advisor = store.create_advisor_session("C:/work", "advisor-digest")
            agent = store.create_conversation_session(
                "C:/work",
                "agent-digest",
                title="长篇项目总控",
                session_kind="project-agent",
            )
            store.append_session_message(agent["session_id"], "user", {"text": "继续第一章"})
            store.append_session_message(agent["session_id"], "assistant", {"text": "我先检查进度。"})

            self.assertEqual([item["session_id"] for item in store.list_advisor_sessions("C:/work")], [advisor["session_id"]])
            self.assertEqual(
                [item["session_id"] for item in store.list_conversation_sessions("C:/work", session_kind="project-agent")],
                [agent["session_id"]],
            )
            restored = store.read_conversation_session(agent["session_id"])
            self.assertEqual(restored["session_kind"], "project-agent")
            self.assertEqual([item["role"] for item in restored["messages"]], ["user", "assistant"])

    def test_memory_adapter_matches_generic_session_contract(self):
        sessions = build_memory_persistence_ports().sessions
        agent = sessions.create_conversation_session(
            "C:/work",
            "agent-digest",
            title="项目 Agent",
            session_kind="project-agent",
        )
        sessions.append_session_message(agent["session_id"], "tool", {"name": "project_overview"})

        restored = sessions.read_conversation_session(agent["session_id"])
        self.assertEqual(restored["messages"][0]["role"], "tool")
        self.assertEqual(sessions.list_advisor_sessions("C:/work"), [])

    def test_schema_v16_advisor_rows_migrate_without_reclassification(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "studio.sqlite3"
            legacy_schema = CORE_SCHEMA_SQL.replace(
                "    session_kind TEXT NOT NULL DEFAULT 'advisor',\n",
                "",
            )
            with closing(sqlite3.connect(database)) as connection:
                connection.executescript(legacy_schema)
                connection.execute(
                    """
                    INSERT INTO advisor_sessions (
                        session_id, project_root, snapshot_digest, title, created_at, updated_at
                    ) VALUES ('advisor-legacy', 'C:/work', 'old', '旧会话', 't0', 't0')
                    """
                )
                connection.execute("PRAGMA user_version = 16")
                connection.commit()

            store = JobStore(database)

            migrated = store.read_advisor_session("advisor-legacy")
            self.assertEqual(migrated["session_kind"], "advisor")
            self.assertTrue(store.health()["ready"])


if __name__ == "__main__":
    unittest.main()
