from pathlib import Path
import unittest

from literary_engineering_studio_engine.route_selection import (
    select_asset_state,
    select_export_release_state,
    select_source_ingest_state,
)


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


if __name__ == "__main__":
    unittest.main()
