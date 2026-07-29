from pathlib import Path
import json
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from literary_engineering_studio.api_server import create_app
from literary_engineering_studio.application.style import StyleApplicationService
from literary_engineering_studio.config import default_config
from literary_engineering_studio_engine.literary.style.version import (
    build_style_profile_version,
)
from literary_engineering_studio_engine.style_lab import (
    create_author_project,
    create_author_work,
    import_work_source,
    run_author_style_learning_platform_task,
)
from tests.test_style_profile_version import _formal_reviewed_profile


class StyleApplicationServiceTests(unittest.TestCase):
    def test_projects_sources_and_versions_without_exposing_corpus_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _seed_style_profile(root)

            authors = StyleApplicationService().authors(root)
            self.assertEqual(authors["count"], 1)
            author = authors["authors"][0]
            self.assertEqual(author["rights"]["status"], "declared")
            source = author["works"][0]["sources"][0]
            self.assertEqual(len(source["content_sha256"]), 64)
            self.assertNotIn("content", source)

            versions = StyleApplicationService().version_catalog(root)
            self.assertEqual(versions["count"], 1)
            version = versions["versions"][0]
            self.assertEqual(version["state"], "profile")
            self.assertEqual(len(version["source_hash"]), 64)
            self.assertNotIn(str(root), json.dumps(versions, ensure_ascii=False))

    def test_api_exposes_stable_author_and_version_catalogs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _seed_style_profile(root)
            config = default_config()
            config["application"]["data_root"] = str(root / "data")
            config["application"]["database_path"] = str(root / "data" / "studio.sqlite3")
            config["worker"]["runs_root"] = str(root / "runs")
            client = TestClient(create_app(config))

            authors = client.get("/style-lab/authors", params={"style_library_root": str(root)})
            versions = client.get("/style-lab/versions", params={"style_library_root": str(root)})

            self.assertEqual(authors.status_code, 200)
            self.assertEqual(authors.json()["schema"], "arcvellum/style-author-catalog/v1")
            self.assertEqual(versions.status_code, 200)
            self.assertEqual(versions.json()["schema"], "arcvellum/style-version-catalog/v1")

    def test_workbench_composes_safe_journey_and_empty_library_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            project, profile, target_id = _formal_reviewed_profile(base)
            built = build_style_profile_version(
                project,
                profile,
                target_id=target_id,
            )

            workbench = StyleApplicationService().workbench(
                project,
                base / "missing-library",
            )

            self.assertEqual(
                workbench["schema"],
                "arcvellum/style-atelier-workbench/v1",
            )
            self.assertEqual(workbench["summary"]["built_count"], 1)
            self.assertEqual(workbench["summary"]["reviewed_count"], 1)
            self.assertEqual(
                [item["id"] for item in workbench["journey"]],
                ["sources", "profiles", "evaluation", "review", "versions", "mount"],
            )
            self.assertIn("style library is unavailable", workbench["issues"])
            self.assertNotIn(str(base), json.dumps(workbench, ensure_ascii=False))
            self.assertEqual(
                workbench["versions"][0]["version_id"],
                built.version_id,
            )

            config = default_config()
            config["application"]["data_root"] = str(base / "data")
            config["application"]["database_path"] = str(base / "data" / "studio.sqlite3")
            config["worker"]["runs_root"] = str(base / "runs")
            client = TestClient(create_app(config))
            response = client.get(
                "/style-lab/workbench",
                params={
                    "project_root": str(project),
                    "style_library_root": str(base / "missing-library"),
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.json()["revision"],
                workbench["revision"],
            )

    def test_style_quality_and_copy_risk_are_projected_as_independent_signals(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _seed_style_profile(root)
            evaluation_dir = (
                root
                / "authors"
                / "public-author"
                / "profiles"
                / "default"
                / "evaluation_results"
                / "formal"
            )
            evaluation_dir.mkdir(parents=True, exist_ok=True)
            (evaluation_dir / "style_eval_current.json").write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/style-eval/v0.1",
                        "mode": "blind-review",
                        "overall_score": 88,
                        "risk_level": "high_copy_risk",
                        "candidate_sha256": "a" * 64,
                        "reference_sha256": "b" * 64,
                    }
                ),
                encoding="utf-8",
            )

            evaluation = StyleApplicationService().version_catalog(root)["versions"][0]["evaluations"][0]

            self.assertEqual(evaluation["style_quality_status"], "pass")
            self.assertEqual(evaluation["leakage_risk_status"], "blocked")

    def test_project_version_catalog_and_detail_hide_source_text_and_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            project, profile, target_id = _formal_reviewed_profile(base)
            result = build_style_profile_version(
                project,
                profile,
                target_id=target_id,
            )

            service = StyleApplicationService()
            catalog = service.version_catalog(
                base / "missing-library",
                project_root=project,
            )
            detail = service.version_detail(
                project,
                style_id=result.style_id,
                version_id=result.version_id,
            )
            serialized = json.dumps(
                {"catalog": catalog, "detail": detail},
                ensure_ascii=False,
            )

            self.assertEqual(catalog["count"], 1)
            version = catalog["versions"][0]
            self.assertEqual(version["origin"], "formal-session")
            self.assertEqual(version["state"], "mountable")
            self.assertTrue(version["built"])
            self.assertEqual(detail["integrity"]["status"], "pass")
            self.assertEqual(detail["source_evidence"][0]["rights"]["status"], "declared")
            self.assertNotIn("declaration", detail["source_evidence"][0]["rights"])
            self.assertNotIn(str(project), serialized)
            self.assertNotIn("旧城的钟声", serialized)
            self.assertNotIn("雨停以后", serialized)
            self.assertNotIn("prompt.md\": \"", serialized)

    def test_catalog_preserves_valid_history_when_current_plan_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            project, profile, target_id = _formal_reviewed_profile(base)
            original = build_style_profile_version(
                project,
                profile,
                target_id=target_id,
            )
            review_path = (
                profile
                / "evaluation_results"
                / "formal"
                / "style_semantic_review.json"
            )
            review = json.loads(review_path.read_text(encoding="utf-8"))
            review["summary"] = "新的独立审查摘要形成了新的版本候选。"
            review_path.write_text(
                json.dumps(review, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            versions = StyleApplicationService().version_catalog(
                base / "missing-library",
                project_root=project,
            )["versions"]

            self.assertEqual(len(versions), 2)
            history = next(item for item in versions if item["built"])
            planned = next(item for item in versions if not item["built"])
            self.assertEqual(history["version_id"], original.version_id)
            self.assertEqual(history["state"], "mountable")
            self.assertEqual(planned["state"], "build-ready")
            self.assertNotEqual(
                planned["planned_version_id"],
                original.version_id,
            )

    def test_api_exposes_safe_project_version_detail(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            project, profile, target_id = _formal_reviewed_profile(base)
            result = build_style_profile_version(
                project,
                profile,
                target_id=target_id,
            )
            config = default_config()
            config["application"]["data_root"] = str(base / "data")
            config["application"]["database_path"] = str(
                base / "data" / "studio.sqlite3"
            )
            config["worker"]["runs_root"] = str(base / "runs")
            client = TestClient(create_app(config))

            response = client.get(
                f"/style-lab/versions/{result.style_id}/{result.version_id}",
                params={"project_root": str(project)},
            )

            self.assertEqual(response.status_code, 200)
            detail = response.json()
            self.assertEqual(
                detail["schema"],
                "arcvellum/style-profile-version-detail/v1",
            )
            self.assertEqual(detail["integrity"]["status"], "pass")
            self.assertNotIn(str(project), response.text)

    def test_build_api_runs_current_deterministic_worker_and_projects_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            project, _, _ = _formal_reviewed_profile(base)
            config = default_config()
            config["application"]["data_root"] = str(base / "data")
            config["application"]["database_path"] = str(
                base / "data" / "studio.sqlite3"
            )
            config["worker"]["runs_root"] = str(base / "runs")
            with TestClient(create_app(config)) as client, patch(
                "literary_engineering_studio.worker.build_runtime",
                side_effect=AssertionError(
                    "deterministic style build must not start a model runtime"
                ),
            ):
                started = client.post(
                    "/style-lab/build",
                    json={
                        "project_root": str(project),
                        "author_id": "classic-author",
                        "profile_id": "measured-prose",
                        "runtime": "opencode",
                    },
                )
                self.assertEqual(started.status_code, 200)
                job_id = started.json()["job"]["job_id"]
                job = _wait_for_job(client, job_id)
                self.assertEqual(job["status"], "complete")

                catalog = client.get(
                    "/style-lab/versions",
                    params={
                        "style_library_root": str(base / "missing-library"),
                        "project_root": str(project),
                    },
                )
                self.assertEqual(catalog.status_code, 200)
                version = catalog.json()["versions"][0]
                self.assertTrue(version["built"])
                self.assertEqual(version["state"], "mountable")

    def test_build_api_rejects_nonexistent_profile_with_stable_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            project, _, _ = _formal_reviewed_profile(base)
            config = default_config()
            config["application"]["data_root"] = str(base / "data")
            config["application"]["database_path"] = str(
                base / "data" / "studio.sqlite3"
            )
            config["worker"]["runs_root"] = str(base / "runs")
            client = TestClient(create_app(config))

            response = client.post(
                "/style-lab/build",
                json={
                    "project_root": str(project),
                    "author_id": "classic-author",
                    "profile_id": "missing-profile",
                },
            )

            self.assertEqual(response.status_code, 404)
            self.assertEqual(
                response.json()["detail"]["code"],
                "style_profile_not_found",
            )

    def test_undeclared_package_file_is_projected_as_integrity_conflict(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            project, profile, target_id = _formal_reviewed_profile(base)
            result = build_style_profile_version(
                project,
                profile,
                target_id=target_id,
            )
            (result.version_dir / "unexpected.txt").write_text(
                "not declared by the immutable package\n",
                encoding="utf-8",
            )

            service = StyleApplicationService()
            version = service.version_catalog(
                base / "missing-library",
                project_root=project,
            )["versions"][0]
            detail = service.version_detail(
                project,
                style_id=result.style_id,
                version_id=result.version_id,
            )

            self.assertEqual(version["state"], "conflict")
            self.assertIn("artifact-integrity", version["blocking_reasons"])
            self.assertEqual(detail["integrity"]["status"], "conflict")


def _seed_style_profile(root: Path) -> None:
    create_author_project(
        root,
        name="Public Author",
        author_id="public-author",
        mode="public_domain",
        source_note="Public-domain text verified by the user.",
    )
    create_author_work(root, author_id="public-author", title="Work One", work_id="work-one")
    import_work_source(
        root,
        author_id="public-author",
        work_id="work-one",
        text="第一句。第二句。第三句。",
        filename="work-one.txt",
    )
    run_author_style_learning_platform_task(root, author_id="public-author", profile_id="default")


def _wait_for_job(client: TestClient, job_id: str) -> dict[str, object]:
    deadline = time.time() + 30
    payload: dict[str, object] = {}
    while time.time() < deadline:
        payload = client.get(f"/worker/jobs/{job_id}").json()
        if payload.get("status") not in {"queued", "running", "stopping"}:
            return payload
        time.sleep(0.05)
    raise AssertionError(
        f"style build job did not finish: {job_id}; "
        f"last_status={payload.get('status') or 'unknown'}"
    )


if __name__ == "__main__":
    unittest.main()
