from pathlib import Path
import json
import tempfile
import unittest

from fastapi.testclient import TestClient

from literary_engineering_studio.api_server import create_app
from literary_engineering_studio.application.style import StyleApplicationService
from literary_engineering_studio.config import default_config
from literary_engineering_studio_engine.style_lab import (
    create_author_project,
    create_author_work,
    import_work_source,
    run_author_style_learning_platform_task,
)


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


if __name__ == "__main__":
    unittest.main()
