from pathlib import Path
import tempfile
import time
import unittest

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover
    TestClient = None

from literary_engineering_studio.api_server import create_app
from literary_engineering_studio.config import default_config
from literary_engineering_studio.project_agent import ProjectAgentDependencies, ProjectAgentTurnResult


class _Runtime:
    def run_turn(self, request, _tool_handler, **kwargs):
        kwargs["event_sink"]("project_agent.event", {"kind": "text.delta", "text": "正在读取"})
        return ProjectAgentTurnResult(
            "completed",
            "第一章正在准备。",
            request.turn_id,
            0,
            0,
            "complete",
        )


@unittest.skipIf(TestClient is None, "FastAPI test dependencies are not installed")
class ProjectAgentApiTests(unittest.TestCase):
    def test_workspace_session_and_queued_turn_stop_without_a_selected_work(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = default_config()
            config["application"]["data_root"] = str(root / "data")
            config["application"]["projects_root"] = str(root / "Works")
            config["application"]["database_path"] = str(root / "studio.sqlite3")
            config["worker"]["runs_root"] = str(root / "runs")

            with TestClient(create_app(config)) as client:
                service = client.app.state.project_agent
                dependencies = service.dependencies
                service.dependencies = ProjectAgentDependencies(
                    dependencies.project_overview,
                    dependencies.project_search,
                    dependencies.creation_observe,
                    workspace_catalog=lambda _root, _args: {"works": [], "count": 0},
                )
                created = client.post(
                    "/project-agent/sessions",
                    json={"project_root": "", "title": "作品库总控"},
                )
                self.assertEqual(created.status_code, 200)
                job = client.app.state.lifecycle.persistence.worker.create({
                    "kind": "project-agent-turn",
                    "project_root": str(root / "Works"),
                    "session_id": created.json()["session_id"],
                    "turn_id": "turn-stop",
                })

                stopped = client.post(f"/project-agent/jobs/{job['job_id']}/stop")

                self.assertEqual(stopped.status_code, 200)
                self.assertEqual(stopped.json()["status"], "cancelled")
                self.assertEqual(
                    client.get(f"/project-agent/jobs/{job['job_id']}").json()["status"],
                    "cancelled",
                )

    def test_session_turn_and_durable_event_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()
            project.joinpath("project.yaml").write_text("project:\n  title: test\n", encoding="utf-8")
            config = default_config()
            config["application"]["data_root"] = str(root / "data")
            config["application"]["database_path"] = str(root / "studio.sqlite3")
            config["worker"]["runs_root"] = str(root / "runs")

            with TestClient(create_app(config)) as client:
                service = client.app.state.project_agent
                service.dependencies = ProjectAgentDependencies(
                    project_overview=lambda _root, _args: {"stage": "planning"},
                    project_search=lambda _root, _args: {},
                    creation_observe=lambda _root, _args: {},
                )
                service.runtime_factory = lambda _config, _root: _Runtime()
                created = client.post(
                    "/project-agent/sessions",
                    json={"project_root": str(project), "title": "项目总控"},
                )
                self.assertEqual(created.status_code, 200)
                session_id = created.json()["session_id"]

                started = client.post(
                    f"/project-agent/sessions/{session_id}/turns",
                    json={"message": "现在进展如何？", "timeout": 30},
                )
                self.assertEqual(started.status_code, 200)
                job_id = started.json()["job_id"]
                for _ in range(100):
                    job = client.get(f"/project-agent/jobs/{job_id}").json()
                    if job.get("status") == "complete":
                        break
                    time.sleep(0.01)
                self.assertEqual(job["status"], "complete")

                events = client.get(
                    f"/project-agent/jobs/{job_id}/events",
                    params={"max_events": 100},
                )
                self.assertEqual(events.status_code, 200)
                self.assertIn("event: project_agent.event", events.text)
                self.assertIn("event: project_agent.result", events.text)
                self.assertIn("event: stream.terminal", events.text)

                session = client.get(f"/project-agent/sessions/{session_id}").json()
                self.assertEqual([item["role"] for item in session["messages"]], ["user", "assistant"])


if __name__ == "__main__":
    unittest.main()
