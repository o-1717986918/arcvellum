import tempfile
from pathlib import Path
import unittest

from literary_engineering_studio.application.lean_source_context import imported_source_context
from literary_engineering_studio.application.archaeology.projection import project_archaeology_workbench
from literary_engineering_studio_engine.public.projects import ingest_existing_work


class LeanSourceImportTests(unittest.TestCase):
    def test_import_preserves_evidence_without_legacy_tasks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: 新故事\n", encoding="utf-8")
            result = ingest_existing_work(
                root, text="渡口多年没有开船。林昭一直守着那封信。" * 40,
                title="旧约", work_id="old-promise", mode="continuation",
                emit_legacy_tasks=False,
            )
            count, context = imported_source_context(root)
            self.assertEqual(count, 1)
            self.assertIn("林昭", context)
            self.assertTrue(result.manifest_path.is_file())
            self.assertFalse(result.task_path.exists())
            self.assertFalse(list(result.import_dir.rglob("*.agent_tasks.md")))
            workbench = project_archaeology_workbench(root, "old-promise")
            self.assertEqual(workbench["status"]["status"], "ready")
            self.assertEqual([row["id"] for row in workbench["journey"]], ["source", "segments", "planning"])


if __name__ == "__main__":
    unittest.main()
