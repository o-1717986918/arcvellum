from __future__ import annotations

import hashlib
import json
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

    def test_long_prose_snapshot_preserves_thirty_thousand_characters(self) -> None:
        content = "潮声落在舷窗外。" * 3_750
        self.assertEqual(len(content), 30_000)
        self._publish_preview(content, revision=1)

        snapshot = self.client.get(
            "/creative-live", params={"project_root": str(self.project)}
        ).json()

        self.assertEqual(snapshot["artifacts"][0]["content"], content)
        self.assertEqual(snapshot["artifacts"][0]["characters"], 30_000)
        self.assertFalse(snapshot["artifacts"][0]["truncated"])

    def test_project_stream_resumes_after_browser_last_event_id(self) -> None:
        first = self._publish_preview("旧片段。", revision=1)
        self._publish_preview("新片段。", revision=2)
        with self.client.stream(
            "GET", "/creative-live/stream",
            params={"project_root": str(self.project), "max_events": 1},
            headers={"Last-Event-ID": f"live:{first.sequence}"},
        ) as response:
            body = "".join(response.iter_text())

        event_body = body.split("event: creative.event", 1)[1]
        self.assertEqual(response.status_code, 200)
        self.assertIn("preview-2", event_body)
        self.assertNotIn("preview-1", event_body)

    def test_candidate_review_revision_and_promotion_keep_one_artifact_identity(self) -> None:
        candidate_path = "drafts/scenes/scene_0001_candidate.md"
        review_path = "reviews/agent/scene_0001_scene_review.json"
        first_text = "舱外的信号灯亮了。"
        revised_text = "舱外的信号灯亮了。\n她没有立刻回应。"
        first_digest = hashlib.sha256(first_text.encode("utf-8")).hexdigest()
        revised_digest = hashlib.sha256(revised_text.encode("utf-8")).hexdigest()

        self._publish_event("artifact.preview.snapshot", {
            "path": candidate_path, "kind": "prose", "format": "markdown",
            "identity": "streaming_preview", "content": first_text,
            "characters": len(first_text), "revision": 1,
        }, "preview-first")
        self._publish_event("artifact.checkpoint.written", {
            "path": candidate_path, "kind": "prose", "format": "markdown",
            "identity": "candidate_written", "content": first_text,
            "characters": len(first_text), "revision": 1, "sha256": first_digest,
            "validation_passed": True,
        }, "checkpoint-first")
        self._write_review(review_path, first_digest, "pass", [])
        self._publish_event("artifact.checkpoint.written", {
            "path": review_path, "kind": "review", "format": "json",
            "identity": "candidate_written", "sha256": "1" * 64,
            "revision": 1,
        }, "review-first")

        reviewed = self.client.get(
            "/creative-live", params={"project_root": str(self.project)}
        ).json()
        candidate = next(item for item in reviewed["artifacts"] if item["path"] == candidate_path)
        artifact_id = candidate["artifact_id"]
        self.assertEqual(candidate["identity"], "semantic_review_passed")

        self._publish_event("artifact.preview.snapshot", {
            "path": candidate_path, "kind": "prose", "format": "markdown",
            "identity": "streaming_preview", "content": revised_text,
            "characters": len(revised_text), "revision": 2,
            "finding_refs": ["rhythm-1"],
        }, "preview-revised")
        self._publish_event("artifact.checkpoint.written", {
            "path": candidate_path, "kind": "prose", "format": "markdown",
            "identity": "candidate_written", "content": revised_text,
            "characters": len(revised_text), "revision": 2, "sha256": revised_digest,
            "validation_passed": True, "finding_refs": ["rhythm-1"],
        }, "checkpoint-revised")
        self._write_review(review_path, revised_digest, "pass", [
            {"id": "rhythm-1", "message": "修订后场景转向更清晰。"},
        ])
        self._publish_event("artifact.checkpoint.written", {
            "path": review_path, "kind": "review", "format": "json",
            "identity": "candidate_written", "sha256": "2" * 64,
            "revision": 2,
        }, "review-revised")
        self._publish_event("mutation.receipt", {
            "receipt": {
                "target": candidate_path, "action": "formal_promoted",
                "formal_effect": "formal", "preflight_status": "pass",
                "result_sha256": revised_digest,
            },
        }, "promotion-receipt")

        final = self.client.get(
            "/creative-live", params={"project_root": str(self.project)}
        ).json()
        promoted = next(item for item in final["artifacts"] if item["artifact_id"] == artifact_id)
        self.assertEqual(promoted["identity"], "promoted")
        self.assertEqual(promoted["content"], revised_text)
        self.assertTrue(any(item.get("status") == "pass" for item in final["reviews"]))

        revisions = self.client.get(
            f"/creative-live/artifacts/{artifact_id}/revisions",
            params={"project_root": str(self.project)},
        ).json()["revisions"]
        self.assertGreaterEqual(len(revisions), 4)
        self.assertEqual(revisions[-1]["identity"], "promoted")
        details = [
            self.client.get(
                f"/creative-live/artifacts/{artifact_id}/revisions/{item['revision_id']}",
                params={"project_root": str(self.project)},
            ).json()["revision"]
            for item in revisions
        ]
        changed = next(item for item in details if "她没有立刻回应" in item["diff"])
        self.assertIn("rhythm-1", changed["finding_refs"])

    def _publish_preview(self, content: str, *, revision: int) -> dict:
        return self._publish_event(
            "artifact.preview.snapshot",
            {
                "path": "drafts/scenes/scene_0001_candidate.md",
                "kind": "prose", "content": content,
                "characters": len(content), "revision": revision,
            },
            f"preview-{revision}",
        )

    def _publish_event(self, event: str, data: dict, event_id: str) -> dict:
        return self.client.app.state.lifecycle.live_events.publish(
            project_channel(self.project),
            event,
            {
                "runtime_event_id": event_id,
                "run_id": "run-1",
                "session_id": "session-1",
                "task_id": "scene-1-prose",
                "route": "scene-development",
                "attempt_id": "attempt-1",
                **data,
            },
        )

    def _write_review(
        self, relative: str, candidate_digest: str, conclusion: str,
        findings: list[dict[str, str]],
    ) -> None:
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "schema": "scene_review.v1",
            "scene_id": "scene_0001",
            "candidate_sha256": candidate_digest,
            "conclusion": conclusion,
            "summary": "候选稿与当前场景契约一致。",
            "findings": findings,
        }, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
