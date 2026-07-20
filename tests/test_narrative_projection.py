from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.narrative_projection import build_narrative_projection


class NarrativeProjectionTests(unittest.TestCase):
    def test_book_projection_aggregates_scenes_and_keeps_source_evidence(self):
        library = {
            "sections": {
                "scenes": [
                    {"id": "scene_0001", "title": "场景一", "subtitle": "chapter_0001", "path": "scenes/scene_0001.yaml", "facts": [{"label": "章节", "value": "chapter_0001"}, {"label": "目标字数", "value": "1200"}, {"label": "参与者", "value": "林澈"}]},
                    {"id": "scene_0002", "title": "场景二", "subtitle": "chapter_0001", "path": "scenes/scene_0002.yaml", "facts": [{"label": "章节", "value": "chapter_0001"}, {"label": "目标字数", "value": "1500"}, {"label": "参与者", "value": "林澈"}]},
                ],
                "characters": [{"id": "lin-che", "title": "林澈", "status": "major", "path": "characters/lin-che.yaml"}],
                "branches": [], "reviews": [], "canon_patches": [],
            }
        }
        reader = {"units": [{"coverage": ["scene_0001"], "content_hash": "one", "chapter_id": "chapter_0001", "chinese_content_chars": 1180}], "total_chinese_content_chars": 1180}
        with tempfile.TemporaryDirectory() as temporary, patch("literary_engineering_studio.narrative_projection.build_library", return_value=library), patch("literary_engineering_studio.narrative_projection.build_dashboard", return_value={"next_actions": []}), patch("literary_engineering_studio.narrative_projection.build_reader_manifest", return_value=reader):
            projection = build_narrative_projection({}, Path(temporary), level="book")
        chapter = next(node for node in projection["nodes"] if node["type"] == "chapter")
        self.assertEqual(chapter["metrics"]["word_target"], 2700)
        self.assertEqual(chapter["metrics"]["formal_chars"], 1180)
        self.assertEqual(chapter["source_type"], "scene-catalog")
        self.assertTrue(all(edge["source"] in {node["node_id"] for node in projection["nodes"]} for edge in projection["edges"]))

    def test_scene_projection_exposes_branch_and_review_status(self):
        library = {
            "sections": {
                "scenes": [{"id": "scene_0001", "title": "场景一", "path": "scenes/scene_0001.yaml", "facts": [{"label": "章节", "value": "chapter_0001"}, {"label": "参与者", "value": "林澈"}, {"label": "承诺回报", "value": "那封信将在本卷结尾改写两人的关系"}]}],
                "characters": [{"id": "lin", "title": "林澈", "path": "characters/lin.yaml"}],
                "branches": [{"id": "scene_0001", "path": "branches/scene_0001/branch_manifest.json", "options": [{"id": "A", "label": "承担代价", "selected": True}]}],
                "reviews": [{"id": "scene-review", "title": "场景审查", "path": "reviews/scene_0001.json", "status": "pass"}],
                "canon_patches": [],
            }
        }
        with tempfile.TemporaryDirectory() as temporary, patch("literary_engineering_studio.narrative_projection.build_library", return_value=library), patch("literary_engineering_studio.narrative_projection.build_dashboard", return_value={"next_actions": []}), patch("literary_engineering_studio.narrative_projection.build_reader_manifest", return_value={"units": [], "total_chinese_content_chars": 0}):
            projection = build_narrative_projection({}, Path(temporary), level="scene", focus="scene_0001")
        kinds = {node["type"] for node in projection["nodes"]}
        self.assertIn("branch", kinds)
        self.assertIn("review", kinds)
        self.assertIn("character", kinds)
        self.assertIn("promise", kinds)

    def test_projection_shows_current_state_machine_action(self):
        library = {"sections": {"scenes": [{"id": "scene_0001", "title": "场景一", "subtitle": "chapter_0001", "facts": [{"label": "章节", "value": "chapter_0001"}]}], "characters": [], "branches": [], "reviews": [], "canon_patches": []}}
        dashboard = {"next_actions": [{"route": "scene-development", "target": "scene_0001", "next_action": "先完成角色推演。"}]}
        with tempfile.TemporaryDirectory() as temporary, patch("literary_engineering_studio.narrative_projection.build_library", return_value=library), patch("literary_engineering_studio.narrative_projection.build_dashboard", return_value=dashboard), patch("literary_engineering_studio.narrative_projection.build_reader_manifest", return_value={"units": [], "total_chinese_content_chars": 0}):
            projection = build_narrative_projection({}, Path(temporary), level="book")
        task = next(node for node in projection["nodes"] if node["type"] == "task")
        self.assertEqual(task["status"], "queued")
        self.assertTrue(any(edge["type"] == "workflow" for edge in projection["edges"]))


if __name__ == "__main__":
    unittest.main()
