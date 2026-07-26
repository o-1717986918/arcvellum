from __future__ import annotations

import base64
from pathlib import Path
import tempfile
import unittest

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover
    TestClient = None

from literary_engineering_studio.api_server import create_app
from literary_engineering_studio.application.archaeology import (
    ArchaeologyApplicationService,
    ArchaeologyImportSpec,
)
from literary_engineering_studio.config import default_config


class ArchaeologyApplicationTests(unittest.TestCase):
    def test_import_exposes_safe_workbench_and_all_supported_modes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = _project(Path(temporary))
            service = ArchaeologyApplicationService()

            for mode in ("continuation", "rewrite", "adaptation", "analysis"):
                spec = ArchaeologyImportSpec.create(
                    filename=f"{mode}.md",
                    text="# 第一章\n林昭在白塔发现一封被删改的信。\n",
                    title=f"{mode} work",
                    work_id=f"{mode}-work",
                    mode=mode,
                    rights_declaration="Authorized test source.",
                    chunk_size=1000,
                )
                imported = service.import_source(root, spec)
                workbench = imported["workbench"]
                self.assertEqual(workbench["mode"]["id"], mode)
                self.assertEqual(len(workbench["sources"]), 1)
                self.assertEqual(workbench["sources"][0]["filename"], f"{mode}.md")
                self.assertEqual(workbench["journey"][0]["status"], "complete")
                self.assertEqual(workbench["journey"][2]["status"], "active")
                self.assertNotIn(str(root), str(imported))

            catalog = service.catalog(root)
            self.assertEqual(catalog["count"], 4)
            self.assertEqual(
                {item["mode"]["id"] for item in catalog["imports"]},
                {"continuation", "rewrite", "adaptation", "analysis"},
            )
            self.assertTrue(all(item["source_count"] == 1 for item in catalog["imports"]))

    def test_import_contract_rejects_ambiguous_or_unsafe_input(self):
        common = {
            "filename": "source.md",
            "title": "source",
            "work_id": "source",
            "mode": "continuation",
            "rights_declaration": "Authorized test source.",
        }
        with self.assertRaisesRegex(ValueError, "exactly one"):
            ArchaeologyImportSpec.create(
                **common,
                text="正文",
                content_base64=base64.b64encode("正文".encode()).decode(),
            )
        with self.assertRaisesRegex(ValueError, "rights declaration"):
            ArchaeologyImportSpec.create(
                **{**common, "rights_declaration": ""},
                text="正文",
            )
        with self.assertRaisesRegex(ValueError, "supported extension"):
            ArchaeologyImportSpec.create(
                **{**common, "filename": "../../source.exe"},
                text="正文",
            )
        with self.assertRaisesRegex(ValueError, "DOCX source"):
            ArchaeologyImportSpec.create(
                **{**common, "filename": "source.docx"},
                text="正文",
            )
        with self.assertRaisesRegex(ValueError, "content_base64 is invalid"):
            ArchaeologyImportSpec.create(
                **common,
                content_base64="not-base64",
            )

    def test_catalog_reports_recoverable_interrupted_transactions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = _project(Path(temporary))
            imports = root / "sources" / "imports"
            (imports / ".stalled.importing").mkdir(parents=True)
            (imports / ".stable.backup").mkdir()

            recovery = ArchaeologyApplicationService().catalog(root)["recovery"]

            self.assertEqual(
                {(item["work_id"], item["kind"]) for item in recovery},
                {("stalled", "staging"), ("stable", "backup")},
            )
            self.assertNotIn(str(root), str(recovery))


@unittest.skipIf(TestClient is None, "FastAPI test dependencies are not installed")
class ArchaeologyApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        data = Path(self.temporary.name)
        self.root = _project(data)
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

    def test_import_and_workbench_routes_continue_into_engine_state_machine(self):
        options = self.client.get("/archaeology/options")
        self.assertEqual(options.status_code, 200)
        self.assertEqual(len(options.json()["modes"]), 4)

        response = self.client.post(
            "/archaeology/imports",
            json={
                "project_root": str(self.root),
                "filename": "旧作.md",
                "text": "# 第一章\n林昭抵达白塔。\n",
                "title": "旧作",
                "work_id": "legacy-work",
                "mode": "continuation",
                "rights_declaration": "Authorized test source.",
                "chunk_size": 1000,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["receipt"]["work_id"], "legacy-work")
        self.assertEqual(
            payload["workbench"]["status"]["current_step"],
            "chunk-extraction-agent-task",
        )
        self.assertNotIn(str(self.root), response.text)

        catalog = self.client.get(
            "/archaeology/imports",
            params={"project_root": str(self.root)},
        )
        self.assertEqual(catalog.status_code, 200)
        self.assertEqual(catalog.json()["count"], 1)

        workbench = self.client.get(
            "/archaeology/workbench/legacy-work",
            params={"project_root": str(self.root)},
        )
        self.assertEqual(workbench.status_code, 200)
        self.assertEqual(workbench.json()["segmentation"]["chunk_count"], 1)
        self.assertNotIn(str(self.root), workbench.text)

    def test_import_route_returns_structured_validation_errors(self):
        response = self.client.post(
            "/archaeology/imports",
            json={
                "project_root": str(self.root),
                "filename": "source.md",
                "text": "正文",
                "mode": "analysis",
                "rights_declaration": "",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"]["code"],
            "archaeology_import_invalid",
        )


def _project(base: Path) -> Path:
    root = base / "work"
    root.mkdir(exist_ok=True)
    (root / "project.yaml").write_text(
        "schema: test-project\ntitle: Project Archaeology\n",
        encoding="utf-8",
    )
    return root


if __name__ == "__main__":
    unittest.main()
