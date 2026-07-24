import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.anti_ai_style import style_lint_gate
from literary_engineering_studio_engine.init_project import InitOptions, init_work_project
from literary_engineering_studio_engine.task_contract_audit import build_task_contract_audit
from literary_engineering_studio_engine.task_registry import issue_next_task


CATALOG = Path(__file__).parent / "fixtures" / "golden_projects" / "catalog.json"


class GoldenProjectCatalogTests(unittest.TestCase):
    def test_catalog_covers_required_longform_shapes_and_boots_formal_task_contracts(self):
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        projects = catalog["projects"]
        self.assertEqual(len(projects), 6)
        self.assertEqual(len({item["id"] for item in projects}), 6)
        self.assertEqual(catalog["schema"], "arcvellum/golden-project-catalog/v1")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for fixture in projects:
                project = root / fixture["id"]
                init_work_project(
                    InitOptions(
                        target=project,
                        title=fixture["title"],
                        work_type=fixture["work_type"],
                        target_length=fixture["target_length"],
                        premise=fixture["premise"],
                    )
                )
                task = issue_next_task(project, route="character-and-world-assets")
                self.assertEqual(task.status, "issued")
                audit = build_task_contract_audit(project)
                self.assertEqual(audit.error_count, 0, fixture["id"])
                gate = style_lint_gate(fixture["inject"])
                self.assertEqual(gate["status"], "blocking", fixture["id"])
                self.assertTrue(any(item["rule"] == "mechanical-contrast-frame" for item in gate["blocking"]))


if __name__ == "__main__":
    unittest.main()
