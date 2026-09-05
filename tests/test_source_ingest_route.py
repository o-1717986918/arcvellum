from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.source_ingest_route import build_task_payload, validate_task


class SourceIngestRouteTests(unittest.TestCase):
    def test_extraction_review_task_keeps_candidate_only_contract_and_revision_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            import_dir = root / "sources/imports/work-a"
            chunk = import_dir / "chunks/chunk_0001.md"
            candidate = root / "plot/candidates/extracted/work-a_outline.md"
            review = root / "reviews/source_ingest/work-a_extraction_review.md"
            for path in (chunk, candidate, review):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture\n", encoding="utf-8")
            (import_dir / "source_manifest.json").write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/source-ingest/v1",
                        "work_id": "work-a",
                        "chunks": [{"path": "sources/imports/work-a/chunks/chunk_0001.md"}],
                        "candidate_outputs": {
                            "outline": "plot/candidates/extracted/work-a_outline.md",
                            "review": "reviews/source_ingest/work-a_extraction_review.md",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = build_task_payload(
                root,
                "source-ingest",
                {"work_id": "work-a", "import_dir": "sources/imports/work-a", "current_step": "extraction-review"},
            )
            self.assertEqual(payload["task_type"], "platform-agent-revision")
            self.assertEqual(payload["expected_outputs"], ["plot/candidates/extracted/work-a_outline.md", "reviews/source_ingest/work-a_extraction_review.md"])
            self.assertEqual(payload["repair_targets"], ["plot/candidates/extracted/work-a_outline.md"])
            self.assertIn("plot/candidates/extracted/work-a_outline.md", payload["repair_target_sha256_before_revision"])
            self.assertNotIn("canon/world_rules.yaml", payload["expected_outputs"])
            self.assertTrue(
                any("migration-only" in item for item in payload["hard_constraints"])
            )

    def test_legacy_extraction_reads_chunks_without_claiming_an_archaeology_aggregate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            import_dir = root / "sources/imports/work-a"
            import_dir.mkdir(parents=True)
            (import_dir / "source_manifest.json").write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/source-ingest/v1",
                        "work_id": "work-a",
                        "chunks": [
                            {"path": "sources/imports/work-a/chunks/chunk_0001.md"}
                        ],
                        "candidate_outputs": {
                            "review": "reviews/source_ingest/work-a_extraction_review.md"
                        },
                    }
                ),
                encoding="utf-8",
            )

            payload = build_task_payload(
                root,
                "source-ingest",
                {
                    "work_id": "work-a",
                    "import_dir": "sources/imports/work-a",
                    "current_step": "extraction-agent-task",
                },
            )

            constraints = "\n".join(payload["hard_constraints"])
            self.assertIn("legacy source chunks", constraints)
            self.assertIn("migration-only", constraints)
            self.assertNotIn("ready archaeology aggregate", constraints)

    def test_validation_requires_completion_and_clean_review_before_route_can_advance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            import_dir = root / "sources/imports/work-a"
            import_dir.mkdir(parents=True)
            (import_dir / "source_manifest.json").write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/source-ingest/v1",
                        "work_id": "work-a",
                        "chunks": [{"path": "sources/imports/work-a/chunks/chunk_0001.md"}],
                        "candidate_outputs": {"review": "reviews/source_ingest/work-a_extraction_review.md"},
                    }
                ),
                encoding="utf-8",
            )
            (import_dir / "source_ingest.md").write_text("report\n", encoding="utf-8")
            (import_dir / "extract_project_files.agent_tasks.md").write_text("# task\n", encoding="utf-8")

            errors, notes = validate_task(root, {"current_state": "extraction-agent-task", "work_id": "work-a"})
            self.assertTrue(errors)
            self.assertEqual(notes, [])
            self.assertTrue(any("sidecar is incomplete" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
