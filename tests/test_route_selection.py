from pathlib import Path
import json
import tempfile
import unittest

from literary_engineering_studio_engine.route_selection import (
    select_asset_state,
    select_export_release_state,
    select_source_ingest_state,
)
from literary_engineering_studio_engine.workflow.state_assets import _asset_states


class RouteSelectionTests(unittest.TestCase):
    def test_identifier_selection_remains_exact_after_route_split(self):
        payload = {
            "assets": [
                {"candidate_id": "hero", "status": "ready"},
                {"candidate_id": "antihero", "status": "pending"},
            ]
        }
        selected = select_asset_state(Path("."), payload, "hero")
        self.assertEqual(selected["candidate_id"], "hero")

    def test_path_selection_can_match_a_route_local_directory_suffix(self):
        payload = {
            "source_ingests": [
                {"work_id": "work-a", "import_dir": "sources/imports/work-a", "status": "pending"}
            ]
        }
        selected = select_source_ingest_state(Path("."), payload, "work-a")
        self.assertEqual(selected["work_id"], "work-a")

    def test_export_identifiers_do_not_match_by_suffix(self):
        payload = {
            "exports": [
                {"chapter_id": "chapter-1", "status": "ready"},
                {"chapter_id": "chapter-11", "status": "pending"},
            ]
        }
        selected = select_export_release_state(Path("."), payload, "chapter-1")
        self.assertEqual(selected["chapter_id"], "chapter-1")

    def test_duplicate_asset_candidate_ids_are_rejected_instead_of_silently_selecting_one(self):
        payload = {
            "assets": [
                {
                    "candidate_id": "shared-foundation",
                    "candidate": "characters/candidates/shared-foundation.json",
                    "status": "pending",
                },
                {
                    "candidate_id": "shared-foundation",
                    "candidate": "canon/candidates/world_rules/shared-foundation.json",
                    "status": "pending",
                },
            ]
        }

        with self.assertRaisesRegex(ValueError, "duplicate asset candidate id"):
            select_asset_state(Path("."), payload, "shared-foundation")

    def test_asset_state_inventory_preserves_cross_directory_identity_conflicts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative, asset_type in (
                ("characters/candidates/shared-foundation.json", "character"),
                ("canon/candidates/world_rules/shared-foundation.json", "world"),
            ):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    json.dumps({"candidate_id": "shared-foundation", "asset_type": asset_type}),
                    encoding="utf-8",
                )

            states = _asset_states(root)

            self.assertEqual(len(states), 2)
            self.assertEqual({str(item["candidate"]) for item in states}, {
                "characters/candidates/shared-foundation.json",
                "canon/candidates/world_rules/shared-foundation.json",
            })


if __name__ == "__main__":
    unittest.main()
