from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from literary_engineering_studio.api_server import create_app
from literary_engineering_studio.config import default_config
from literary_engineering_studio.observability.creative_live.contracts import project_channel


class CreativeLiveApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        data_root = Path(self.temporary.name)
        self.project = data_root / "project"
        self.project.mkdir()
        self.project.joinpath("project.yaml").write_text(
            "project:\n  title: Creative Live API Fixture\n  type: novel\n",
            encoding="utf-8",
        )
        config = default_config()
        config["application"]["data_root"] = str(data_root)
        config["application"]["database_path"] = str(data_root / "studio.sqlite3")
        config["application"]["projects_root"] = str(data_root / "projects")
        config["worker"]["runs_root"] = str(data_root / "runs")
        config["agent_runners"]["opencode"]["data_root"] = str(data_root)
        config["agent_runners"]["pi-worker"]["auth_path"] = str(data_root / "pi-auth.json")
        self.client = TestClient(create_app(config))

    def tearDown(self) -> None:
        self.client.close()
        self.temporary.cleanup()

    def test_snapshot_and_revision_endpoints_share_the_same_artifact_identity(self) -> None:
        self._publish_preview("第一段。", revision=1)
        snapshot = self.client.get("/creative-live", params={"project_root": str(self.project)})

        self.assertEqual(snapshot.status_code, 200)
        artifact = snapshot.json()["artifacts"][0]
        self.assertEqual(artifact["identity"], "streaming_preview")
        self.assertEqual(artifact["content"], "第一段。")

        response = self.client.get(
            f"/creative-live/artifacts/{artifact['artifact_id']}/revisions",
            params={"project_root": str(self.project)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["revisions"][0]["artifact_id"], artifact["artifact_id"])

    def test_project_stream_starts_with_snapshot_then_real_event(self) -> None:
        self._publish_preview("流式候选。", revision=1)
        with self.client.stream(
            "GET", "/creative-live/stream",
            params={"project_root": str(self.project), "max_events": 1},
        ) as response:
            body = "".join(response.iter_text())

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: creative.snapshot", body)
        self.assertIn("event: creative.event", body)
        self.assertIn("流式候选", body)

    def _publish_preview(self, content: str, *, revision: int) -> None:
        self.client.app.state.lifecycle.live_events.publish(
            project_channel(self.project),
            "artifact.preview.snapshot",
            {
                "runtime_event_id": f"preview-{revision}",
                "session_id": "session-1",
                "task_id": "scene-1-prose",
                "route": "scene-development",
                "path": "drafts/scenes/scene_0001_candidate.md",
                "kind": "prose",
                "content": content,
                "characters": len(content),
                "revision": revision,
            },
        )


if __name__ == "__main__":
    unittest.main()
