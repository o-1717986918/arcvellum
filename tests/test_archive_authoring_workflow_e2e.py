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
from literary_engineering_studio_engine.context_broker import (
    context_trace_status,
    write_context_trace,
)
from literary_engineering_studio_engine.projects.init import InitOptions, init_work_project


@unittest.skipIf(TestClient is None, "FastAPI test dependencies are not installed")
class ArchiveAuthoringWorkflowE2ETests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        data = Path(self.temporary.name)
        self.root = data / "work"
        init_work_project(
            InitOptions(
                target=self.root,
                title="潮线档案验收",
                target_length=120_000,
                premise="潮汐记录会改变记录者对过去的理解。",
                genre="现实幻想",
            )
        )
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

    def test_author_can_complete_archive_lifecycle_and_formal_candidate_promotion(self):
        asset_id = self._create_character()
        detail = self._asset(asset_id)
        original_content = detail["content"]
        self.assertIn("# 作者保留的资料批注", original_content)

        self._write_dependent_context(asset_id, detail)
        structured = self._post(
            f"/archive/assets/{asset_id}/structure",
            {"project_root": str(self.root), "content": original_content},
        )
        rendered = self._post(
            f"/archive/assets/{asset_id}/render-structured",
            {
                "project_root": str(self.root),
                "content": original_content,
                "source_revision": structured["source_revision"],
                "fields": {"name": "梅汐（修订）"},
            },
        )
        self.assertIn("# 作者保留的资料批注", rendered["content"])
        self.assertEqual(self._asset(asset_id)["content"], original_content)

        structured_commit = self._commit_asset(
            asset_id,
            detail["revision"],
            rendered["content"],
            "作者通过结构化校勘修订人物名称。",
        )
        stale = structured_commit["receipt"]["stale_propagation"]
        self.assertEqual(stale["status"], "propagated")
        self.assertEqual(stale["scene_ids"], ["scene_0001"])
        context = self.root / "memory" / "context_packets" / "scene_0001.md"
        self.assertEqual(context_trace_status(self.root, "scene_0001", context).status, "stale")

        structured_detail = self._asset(asset_id)
        expert_content = structured_detail["content"] + "# 专家源文本往返批注\n"
        validation = self._post(
            f"/archive/assets/{asset_id}/validate",
            {"project_root": str(self.root), "content": expert_content},
        )
        self.assertTrue(validation["validation"]["valid"])
        source_commit = self._commit_asset(
            asset_id,
            structured_detail["revision"],
            expert_content,
            "作者在专家模式补充保留批注。",
        )
        latest_content = self._asset(asset_id)["content"]
        self.assertIn("# 专家源文本往返批注", latest_content)

        history = self.client.get(
            f"/archive/assets/{asset_id}/history",
            params={"project_root": str(self.root)},
        )
        self.assertEqual(history.status_code, 200, history.text)
        revisions = {item["revision"] for item in history.json()["revisions"]}
        self.assertIn(structured_commit["receipt"]["new_revision"], revisions)
        self.assertIn(source_commit["receipt"]["new_revision"], revisions)

        archived = self._post(
            f"/archive/assets/{asset_id}/archive",
            {
                "project_root": str(self.root),
                "base_revision": source_commit["receipt"]["new_revision"],
                "reason": "作者暂时归档以验证可逆工作流。",
            },
        )
        asset_path = self.root / "characters" / "mei.yaml"
        self.assertFalse(asset_path.exists())
        restored = self._post(
            f"/archive/assets/{asset_id}/restore",
            {
                "project_root": str(self.root),
                "entry_id": archived["receipt"]["entry_id"],
                "reason": "作者恢复资料继续开发。",
            },
        )
        self.assertEqual(restored["receipt"]["status"], "restored")
        self.assertEqual(asset_path.read_text(encoding="utf-8"), latest_content)

        candidate = self._write_reviewed_candidate()
        candidate_detail = self.client.get(
            f"/archive/candidates/{candidate.stem}",
            params={"project_root": str(self.root)},
        )
        self.assertEqual(candidate_detail.status_code, 200, candidate_detail.text)
        candidate_projection = candidate_detail.json()["candidate"]
        self.assertTrue(candidate_projection["can_promote"])
        self.assertEqual(candidate_projection["current_step"], "asset-promotion")

        launched = self._post(
            f"/archive/candidates/{candidate.stem}/promote",
            {
                "project_root": str(self.root),
                "preview_digest": candidate_projection["preview_digest"],
            },
        )
        terminal = self._wait_for_job(launched["job_id"])
        self.assertEqual(terminal["status"], "complete", terminal)
        self.assertEqual(terminal["request"]["route"], "character-and-world-assets")

        promoted = self.client.get(
            f"/archive/candidates/{candidate.stem}",
            params={"project_root": str(self.root)},
        )
        self.assertEqual(promoted.status_code, 200, promoted.text)
        promoted_projection = promoted.json()["candidate"]
        self.assertTrue(promoted_projection["promoted"])
        self.assertEqual(promoted_projection["receipt"]["status"], "promoted")
        self.assertTrue((self.root / "characters" / "protagonist.yaml").is_file())
        self.assertNotIn(str(self.root), promoted.text)

    def _create_character(self) -> str:
        options = self.client.get(
            "/archive/creation/options",
            params={"project_root": str(self.root)},
        )
        self.assertEqual(options.status_code, 200, options.text)
        character = next(
            item for item in options.json()["items"] if item["asset_type"] == "character"
        )
        content = str(character["template"]).replace("__ASSET_ID__", "mei")
        content = content.replace('name: ""', 'name: "梅汐"', 1)
        content = "# 作者保留的资料批注\n" + content
        payload = {
            "project_root": str(self.root),
            "asset_type": "character",
            "local_id": "mei",
            "content": content,
            "semantic_review": "waived",
            "reason": "作者建立主要人物资料。",
        }
        preview = self._post("/archive/creation/preview", payload)["preview"]
        self.assertTrue(preview["committable"])
        committed = self._post(
            "/archive/creation/commit",
            {**payload, "preview_digest": preview["preview_digest"]},
        )
        self.assertEqual(committed["asset_id"], "character:mei")
        return str(committed["asset_id"])

    def _write_dependent_context(self, asset_id: str, detail: dict[str, object]) -> None:
        context = self.root / "memory" / "context_packets" / "scene_0001.md"
        context.parent.mkdir(parents=True, exist_ok=True)
        context.write_text("梅汐的人物资料已进入场景上下文。\n", encoding="utf-8")
        loaded = ("project.yaml", "scenes/scene_0001.yaml", str(detail["source_path"]))
        write_context_trace(
            context.with_suffix(".trace.json"),
            {
                "scene_id": "scene_0001",
                "context_packet": "memory/context_packets/scene_0001.md",
                "loaded_files": list(loaded),
                "loaded_sources": [
                    {
                        "relative_path": relative,
                        "sha256": self._sha(self.root / relative),
                    }
                    for relative in loaded
                ],
                "missing_required_context": [],
            },
        )
        self.assertEqual(asset_id, "character:mei")
        self.assertTrue(context_trace_status(self.root, "scene_0001", context).passed)

    def _write_reviewed_candidate(self) -> Path:
        candidate = self.root / "characters" / "candidates" / "protagonist-foundation.json"
        payload = _dry_payload(
            "character",
            candidate.stem,
            self.root,
            "",
            "protagonist",
            None,
        )
        payload["name"] = "林昭"
        candidate.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        candidate.with_suffix(".md").write_text(
            "# 主角候选\n\n林昭承担潮汐档案的核心视角。\n",
            encoding="utf-8",
        )
        creation_task = candidate.with_suffix(".agent_tasks.md")
        creation_task.write_text("# candidate creation\n", encoding="utf-8")
        write_agent_completion_marker(
            creation_task,
            root=self.root,
            handled_by="creator-agent",
        )

        review_dir = self.root / "reviews" / "assets"
        review_dir.mkdir(parents=True, exist_ok=True)
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
        write_agent_completion_marker(
            review_task,
            root=self.root,
            handled_by="independent-reviewer",
        )
        record_workflow_approval(
            self.root,
            candidate.stem,
            "approve",
            subject_sha256=self._sha(candidate),
        )
        return candidate

    def _asset(self, asset_id: str) -> dict[str, object]:
        response = self.client.get(
            f"/archive/assets/{asset_id}",
            params={"project_root": str(self.root)},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn(str(self.root), response.text)
        return response.json()["asset"]

    def _commit_asset(
        self,
        asset_id: str,
        base_revision: str,
        content: str,
        reason: str,
    ) -> dict[str, object]:
        return self._post(
            f"/archive/assets/{asset_id}/commit",
            {
                "project_root": str(self.root),
                "base_revision": base_revision,
                "content": content,
                "semantic_review": "waived",
                "reason": reason,
            },
        )

    def _wait_for_job(self, job_id: str) -> dict[str, object]:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            response = self.client.get(f"/worker/jobs/{job_id}")
            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()
            if payload.get("status") not in {"queued", "running", "stopping"}:
                return payload
            time.sleep(0.05)
        self.fail(f"worker job did not finish: {job_id}")

    def _post(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        response = self.client.post(path, json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    @staticmethod
    def _sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
