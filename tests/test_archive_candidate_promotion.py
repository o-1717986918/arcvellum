from __future__ import annotations

import hashlib
import json
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
from literary_engineering_studio_engine.agent_tasks import write_agent_completion_marker
from literary_engineering_studio_engine.approval import record_workflow_approval
from literary_engineering_studio_engine.asset_workshop import _dry_payload
from literary_engineering_studio_engine.context_broker import write_context_trace


@unittest.skipIf(TestClient is None, "FastAPI test dependencies are not installed")
class ArchiveCandidatePromotionApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        data = Path(self.temporary.name)
        self.root = data / "work"
        self.root.mkdir()
        (self.root / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
        config = default_config()
        config["application"]["data_root"] = str(data / "data")
        config["application"]["database_path"] = str(data / "data" / "studio.sqlite3")
        config["application"]["projects_root"] = str(data)
        config["worker"]["runs_root"] = str(data / "runs")
        config["agent_runners"]["opencode"]["data_root"] = str(data / "data")
        self.client = TestClient(create_app(config))

    def tearDown(self):
        self.client.close()
        self.temporary.cleanup()

    def test_candidate_projection_is_safe_and_blocks_incomplete_evidence(self):
        candidate = self._write_candidate()

        listing = self.client.get(
            "/archive/candidates",
            params={"project_root": str(self.root)},
        )
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["count"], 1)
        self.assertNotIn(str(self.root), listing.text)

        detail = self.client.get(
            f"/archive/candidates/{candidate.stem}",
            params={"project_root": str(self.root)},
        )
        self.assertEqual(detail.status_code, 200)
        payload = detail.json()["candidate"]
        self.assertEqual(payload["candidate_id"], candidate.stem)
        self.assertEqual(payload["current_step"], "asset-review-task-file")
        self.assertFalse(payload["can_promote"])
        self.assertTrue(payload["promotion_blockers"])
        self.assertIn("林昭", payload["content"])
        self.assertNotIn(str(self.root), detail.text)

        blocked = self.client.post(
            f"/archive/candidates/{candidate.stem}/promote",
            json={
                "project_root": str(self.root),
                "preview_digest": payload["preview_digest"],
            },
        )
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.json()["detail"]["code"], "promotion_not_ready")

    def test_promotion_confirmation_is_content_bound_and_worker_executes_formal_route(self):
        candidate = self._write_candidate()
        self._write_review(candidate)
        self._approve(candidate)
        formal = self.root / "characters" / "protagonist.yaml"
        formal.write_text("character_id: protagonist\nname: 旧设定\n", encoding="utf-8")
        context = self.root / "memory" / "context_packets" / "scene_0001.md"
        context.parent.mkdir(parents=True)
        context.write_text("旧人物设定已进入场景上下文。\n", encoding="utf-8")
        write_context_trace(
            context.with_suffix(".trace.json"),
            {
                "scene_id": "scene_0001",
                "context_packet": "memory/context_packets/scene_0001.md",
                "loaded_files": ["project.yaml", "characters/protagonist.yaml"],
                "loaded_sources": [
                    {
                        "relative_path": relative,
                        "sha256": self._sha(self.root / relative),
                    }
                    for relative in ("project.yaml", "characters/protagonist.yaml")
                ],
                "missing_required_context": [],
            },
        )

        detail = self.client.get(
            f"/archive/candidates/{candidate.stem}",
            params={"project_root": str(self.root)},
        )
        self.assertEqual(detail.status_code, 200)
        candidate_projection = detail.json()["candidate"]
        self.assertTrue(candidate_projection["can_promote"])
        self.assertEqual(candidate_projection["current_step"], "asset-promotion")
        self.assertEqual(
            candidate_projection["impact"]["formal_outputs"][0]["path"],
            "characters/protagonist.yaml",
        )
        self.assertTrue(candidate_projection["impact"]["formal_outputs"][0]["exists"])
        self.assertEqual(candidate_projection["impact"]["formal_outputs"][0]["effect"], "replace")
        self.assertEqual(candidate_projection["impact"]["stale"]["status"], "would-propagate")

        stale = self.client.post(
            f"/archive/candidates/{candidate.stem}/promote",
            json={
                "project_root": str(self.root),
                "preview_digest": "sha256:" + ("0" * 64),
            },
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.json()["detail"]["code"], "promotion_preview_stale")

        launched = self.client.post(
            f"/archive/candidates/{candidate.stem}/promote",
            json={
                "project_root": str(self.root),
                "preview_digest": candidate_projection["preview_digest"],
            },
        )
        self.assertEqual(launched.status_code, 200)
        job_id = launched.json()["job_id"]
        terminal = self._wait_for_job(job_id)
        self.assertEqual(terminal["status"], "complete", terminal)
        request = terminal["request"]
        self.assertEqual(request["route"], "character-and-world-assets")
        self.assertEqual(request["scene"], candidate.stem)
        self.assertEqual(request["task_id"], "")
        self.assertTrue((self.root / "characters" / "protagonist.yaml").is_file())

        promoted = self.client.get(
            f"/archive/candidates/{candidate.stem}",
            params={"project_root": str(self.root)},
        )
        self.assertEqual(promoted.status_code, 200)
        promoted_payload = promoted.json()["candidate"]
        self.assertTrue(promoted_payload["promoted"])
        self.assertFalse(promoted_payload["can_promote"])
        self.assertEqual(promoted_payload["receipt"]["status"], "promoted")
        self.assertEqual(promoted_payload["impact"]["stale"]["status"], "propagated")
        self.assertEqual(promoted_payload["impact"]["stale"]["scene_ids"], ["scene_0001"])
        self.assertNotIn(str(self.root), promoted.text)

    def test_duplicate_candidate_ids_are_a_stable_conflict(self):
        self._write_candidate()
        duplicate = self.root / "canon" / "candidates" / "world_rules" / "protagonist-foundation.json"
        duplicate.parent.mkdir(parents=True)
        duplicate.write_text(
            json.dumps(
                {
                    "schema": "literary-engineering-workbench/world-candidate/v0.1",
                    "candidate_id": "protagonist-foundation",
                    "asset_type": "world",
                    "world_rules": [],
                }
            ),
            encoding="utf-8",
        )

        response = self.client.get(
            "/archive/candidates/protagonist-foundation",
            params={"project_root": str(self.root)},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["code"], "candidate_identity_conflict")
        self.assertNotIn(str(self.root), response.text)

    def _write_candidate(self) -> Path:
        candidate = self.root / "characters" / "candidates" / "protagonist-foundation.json"
        candidate.parent.mkdir(parents=True, exist_ok=True)
        payload = _dry_payload("character", candidate.stem, self.root, "", "protagonist", None)
        payload["name"] = "林昭"
        candidate.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        candidate.with_suffix(".md").write_text("# 主角候选\n\n林昭的人物基础设定。\n", encoding="utf-8")
        creation_task = candidate.with_suffix(".agent_tasks.md")
        creation_task.write_text("# candidate creation\n", encoding="utf-8")
        write_agent_completion_marker(creation_task, root=self.root, handled_by="creator-agent")
        return candidate

    def _write_review(self, candidate: Path) -> None:
        review_dir = self.root / "reviews" / "assets"
        review_dir.mkdir(parents=True)
        review_json = review_dir / f"{candidate.stem}_review.json"
        review_report = review_json.with_suffix(".md")
        review_task = review_json.with_suffix(".agent_tasks.md")
        review_task.write_text("# independent review\n", encoding="utf-8")
        review_json.write_text(
            json.dumps(
                {
                    "schema": "literary-engineering-workbench/candidate-asset-review/v0.1",
                    "candidate": candidate.relative_to(self.root).as_posix(),
                    "candidate_id": candidate.stem,
                    "candidate_sha256": self._sha(candidate),
                    "asset_type": "character",
                    "status": "pass",
                    "blocking_issues": [],
                    "warnings": [],
                    "revision_actions": [],
                    "promotion_risks": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        review_report.write_text("# 独立审查\n\n结论：通过。\n", encoding="utf-8")
        write_agent_completion_marker(review_task, root=self.root, handled_by="independent-reviewer")

    def _approve(self, candidate: Path) -> None:
        record_workflow_approval(
            self.root,
            candidate.stem,
            "approve",
            subject_sha256=self._sha(candidate),
        )

    def _wait_for_job(self, job_id: str) -> dict[str, object]:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            payload = self.client.get(f"/worker/jobs/{job_id}").json()
            if payload.get("status") not in {"queued", "running", "stopping"}:
                return payload
            time.sleep(0.05)
        self.fail(f"worker job did not finish: {job_id}")

    @staticmethod
    def _sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
