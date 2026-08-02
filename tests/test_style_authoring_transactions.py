from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from literary_engineering_studio.api_server import create_app
from literary_engineering_studio.application.style.transactions import (
    StyleAuthoringService,
    StyleIdentityConflictError,
    StyleRightsRequiredError,
    StyleSourceDuplicateError,
    StyleTransactionError,
)
from literary_engineering_studio_engine.literary.style.session import (
    source_content_digest,
)
from literary_engineering_studio.config import default_config


class StyleAuthoringTransactionTests(unittest.TestCase):
    def test_author_work_and_source_write_receipts_without_source_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = StyleAuthoringService()
            author = service.create_author(
                root,
                author_id="public-author",
                name="Public Author",
                rights_mode="public-domain",
                rights_declaration="Verified public-domain source collection.",
            )
            work = service.create_work(
                root,
                author_id="public-author",
                work_id="work-one",
                title="Work One",
            )
            source = service.import_source(
                root,
                author_id="public-author",
                work_id="work-one",
                filename="第一部.md",
                media_type="text/markdown",
                content="# 第一章\n\n这是一段被授权用于文风学习的正文。",
                rights_mode="public-domain",
                rights_declaration="This exact source is in the public domain.",
            )

            self.assertEqual(author["status"], "committed")
            self.assertEqual(work["status"], "committed")
            self.assertEqual(len(source["evidence"]["content_sha256"]), 64)
            receipts = list((root / "transactions").glob("*/receipt.json"))
            self.assertEqual(len(receipts), 3)
            receipt_text = "\n".join(path.read_text(encoding="utf-8") for path in receipts)
            self.assertNotIn("这是一段被授权", receipt_text)

            source_manifests = list((root / "authors").glob("*/works/*/sources/*.source.json"))
            payload = json.loads(source_manifests[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], "arcvellum/style-source/v1")
            self.assertEqual(payload["media_type"], "text/markdown")
            self.assertEqual(payload["rights"]["mode"], "public-domain")

    def test_conflicts_missing_rights_and_duplicate_content_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = StyleAuthoringService()
            service.create_author(
                root,
                author_id="author-one",
                name="Author One",
                rights_mode="authorized",
                rights_declaration="The user provided written authorization.",
            )
            service.create_work(root, author_id="author-one", work_id="work-one", title="Work One")

            with self.assertRaises(StyleIdentityConflictError):
                service.create_author(
                    root,
                    author_id="author-one",
                    name="Different",
                    rights_mode="authorized",
                    rights_declaration="Another declaration that cannot overwrite.",
                )
            with self.assertRaises(StyleRightsRequiredError):
                service.import_source(
                    root,
                    author_id="author-one",
                    work_id="work-one",
                    filename="source.txt",
                    media_type="text/plain",
                    content="同一份语料。",
                    rights_mode="authorized",
                    rights_declaration="short",
                )

            source_args = {
                "author_id": "author-one",
                "work_id": "work-one",
                "filename": "source.txt",
                "media_type": "text/plain",
                "content": "同一份语料。",
                "rights_mode": "authorized",
                "rights_declaration": "Authorization covers this exact source.",
            }
            service.import_source(root, **source_args)
            with self.assertRaises(StyleSourceDuplicateError):
                service.import_source(root, **{**source_args, "filename": "duplicate.txt"})

            self.assertEqual(
                len(list((root / "authors").glob("*/works/*/sources/*.source.json"))),
                1,
            )
            with self.assertRaises(StyleTransactionError):
                service.import_source(
                    root,
                    **{**source_args, "filename": "../escape.txt", "content": "另一份正文。"},
                )

    def test_replacement_or_nul_source_content_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = StyleAuthoringService()
            service.create_author(
                root,
                author_id="author-one",
                name="Public Domain Writer",
                rights_mode="public-domain",
                rights_declaration="Verified public-domain source collection.",
            )
            service.create_work(
                root,
                author_id="author-one",
                work_id="work-one",
                title="Work One",
            )
            base = {
                "author_id": "author-one",
                "work_id": "work-one",
                "filename": "source.txt",
                "media_type": "text/plain",
                "rights_mode": "public-domain",
                "rights_declaration": "Authorization covers this exact source.",
            }

            for content in ("正文\uFFFD残缺", "正文\x00\x00"):
                with self.assertRaises(StyleTransactionError) as caught:
                    service.import_source(root, **{**base, "content": content})
                self.assertIn(
                    "U+FFFD",
                    str(caught.exception),
                )

    def test_imported_source_digest_matches_normalized_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = StyleAuthoringService()
            service.create_author(
                root,
                author_id="author-one",
                name="Public Domain Writer",
                rights_mode="public-domain",
                rights_declaration="Verified public-domain source collection.",
            )
            service.create_work(
                root,
                author_id="author-one",
                work_id="work-one",
                title="Work One",
            )
            service.import_source(
                root,
                author_id="author-one",
                work_id="work-one",
                filename="多段.txt",
                media_type="text/plain",
                content="第一段第一行\n第一段第二行\n\n第二段内容",
                rights_mode="public-domain",
                rights_declaration="Authorization covers this exact source.",
            )

            manifest_path = next(
                (root / "authors").glob("*/works/*/sources/*.source.json")
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            work_dir = manifest_path.parents[1]
            normalized_path = work_dir / str(manifest["normalized"])

            self.assertEqual(
                manifest["content_sha256"],
                source_content_digest(
                    normalized_path.read_text(encoding="utf-8")
                ),
            )
            self.assertEqual(
                manifest["content_sha256"],
                source_content_digest(
                    "第一段第一行第一段第二行\n\n第二段内容"
                ),
            )

    def test_api_returns_stable_conflict_and_rights_codes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = default_config()
            config["application"]["data_root"] = str(root / "data")
            config["application"]["database_path"] = str(root / "data" / "studio.sqlite3")
            config["worker"]["runs_root"] = str(root / "runs")
            client = TestClient(create_app(config))
            request = {
                "style_library_root": str(root / "library"),
                "author_id": "author-one",
                "name": "Author One",
                "rights_mode": "authorized",
                "rights_declaration": "The user provided written authorization.",
            }

            self.assertEqual(client.post("/style-lab/authors", json=request).status_code, 200)
            conflict = client.post("/style-lab/authors", json=request)
            missing_rights = client.post(
                "/style-lab/authors",
                json={**request, "author_id": "author-two", "rights_declaration": ""},
            )

            self.assertEqual(conflict.status_code, 409)
            self.assertEqual(conflict.json()["detail"]["code"], "style_identity_conflict")
            self.assertEqual(missing_rights.status_code, 400)
            self.assertEqual(missing_rights.json()["detail"]["code"], "style_rights_required")

    def test_engine_failure_leaves_a_failed_audit_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch(
                "literary_engineering_studio.application.style.transactions.create_author_project",
                side_effect=OSError("simulated disk failure"),
            ):
                with self.assertRaises(OSError):
                    StyleAuthoringService().create_author(
                        root,
                        author_id="author-one",
                        name="Author One",
                        rights_mode="authorized",
                        rights_declaration="The user provided written authorization.",
                    )

            receipts = list((root / "transactions").glob("*/receipt.json"))
            self.assertEqual(len(receipts), 1)
            payload = json.loads(receipts[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "failed")
            self.assertEqual(payload["error_type"], "OSError")


if __name__ == "__main__":
    unittest.main()
