from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.narrative_projection import (
    build_narrative_projection,
    projection_delta,
    projection_motion_events,
)


class NarrativeProjectionTests(unittest.TestCase):
    def test_book_projection_aggregates_one_thousand_scenes_by_chapter(self):
        scenes = []
        for index in range(1000):
            chapter = f"chapter_{index // 10 + 1:04d}"
            scenes.append({"id": f"scene_{index + 1:04d}", "title": f"场景 {index + 1}", "subtitle": chapter, "facts": [{"label": "章节", "value": chapter}, {"label": "目标字数", "value": "1400"}]})
        library = {"sections": {"scenes": scenes, "characters": [], "branches": [], "reviews": [], "canon_patches": []}}
        with tempfile.TemporaryDirectory() as temporary, patch("literary_engineering_studio.narrative_projection.build_library", return_value=library), patch("literary_engineering_studio.narrative_projection.build_dashboard", return_value={"next_actions": []}), patch("literary_engineering_studio.narrative_projection.build_reader_manifest", return_value={"units": [], "total_chinese_content_chars": 0}):
            projection = build_narrative_projection({}, Path(temporary), level="book")
        self.assertTrue(projection["summary"]["aggregated"])
        self.assertEqual(projection["summary"]["scene_count"], 1000)
        self.assertEqual(len([node for node in projection["nodes"] if node["type"] == "chapter"]), 100)
        self.assertLessEqual(len(projection["nodes"]), 112)

    def test_projection_delta_is_explicit_and_drives_real_motion_events(self):
        previous = {
            "nodes": [{"node_id": "chapter:1", "type": "chapter", "label": "第一章", "status": "current", "metrics": {"formal_chars": 100}}],
            "edges": [],
        }
        current = {
            "nodes": [
                {"node_id": "chapter:1", "type": "chapter", "label": "第一章", "status": "formal", "metrics": {"formal_chars": 500}},
                {"node_id": "branch:1:A", "type": "branch", "label": "承担代价", "status": "alternative", "metrics": {}},
            ],
            "edges": [{"edge_id": "branch:chapter:1>branch:1:A", "source": "chapter:1", "target": "branch:1:A", "type": "branch", "label": "备选"}],
        }
        delta = projection_delta(previous, current)
        self.assertEqual(delta["added_nodes"], ["branch:1:A"])
        self.assertEqual(delta["updated_nodes"], ["chapter:1"])
        events = projection_motion_events(previous, current, delta)
        self.assertIn("branch-grown", {item["type"] for item in events})
        self.assertIn("joined-canon", {item["type"] for item in events})
        self.assertIn("manuscript-grown", {item["type"] for item in events})

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
        self.assertEqual(projection["schema"], "arcvellum/narrative-projection/v2")
        self.assertEqual(projection["timeline"][0]["node_id"], chapter["node_id"])
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

    def test_chapter_and_scene_focus_unfold_every_scene_in_the_focused_chapter(self):
        scenes = [
            {"id": "scene_0001", "title": "场景一", "path": "scenes/scene_0001.yaml", "facts": [{"label": "章节", "value": "chapter_0001"}, {"label": "读者问题", "value": "信是谁留下的？"}]},
            {"id": "scene_0002", "title": "场景二", "path": "scenes/scene_0002.yaml", "facts": [{"label": "章节", "value": "chapter_0001"}]},
            {"id": "scene_0003", "title": "场景三", "path": "scenes/scene_0003.yaml", "facts": [{"label": "章节", "value": "chapter_0001"}]},
            {"id": "scene_0004", "title": "远处场景", "path": "scenes/scene_0004.yaml", "facts": [{"label": "章节", "value": "chapter_0002"}]},
        ]
        library = {
            "sections": {
                "scenes": scenes,
                "characters": [],
                "branches": [
                    {"id": "scene_0001", "path": "branches/scene_0001/branch_manifest.json", "options": [{"id": "A", "label": "保留秘密", "selected": True}]},
                    {"id": "scene_0002", "path": "branches/scene_0002/branch_manifest.json", "options": [{"id": "B", "label": "直接质问", "selected": True}]},
                ],
                "reviews": [
                    {"id": "scene_0001-review", "title": "场景一审查", "path": "reviews/scene_0001_scene_review.json", "status": "pass"},
                    {"id": "scene_0002-review", "title": "场景二审查", "path": "reviews/scene_0002_scene_review.json", "status": "pass"},
                ],
                "canon_patches": [],
            }
        }
        with tempfile.TemporaryDirectory() as temporary, patch("literary_engineering_studio.narrative_projection.build_library", return_value=library), patch("literary_engineering_studio.narrative_projection.build_dashboard", return_value={"next_actions": []}), patch("literary_engineering_studio.narrative_projection.build_reader_manifest", return_value={"units": [], "total_chinese_content_chars": 0}):
            chapter = build_narrative_projection({}, Path(temporary), level="chapter", focus="chapter_0001")
            scene = build_narrative_projection({}, Path(temporary), level="scene", focus="scene_0002")
        for projection in (chapter, scene):
            node_ids = {str(node["node_id"]) for node in projection["nodes"]}
            self.assertIn("branch:scene_0001:A", node_ids)
            self.assertIn("branch:scene_0002:B", node_ids)
            self.assertIn("branch-pending:scene_0003", node_ids)
            self.assertNotIn("branch-pending:scene_0004", node_ids)
            self.assertIn("review:scene_0001-review", node_ids)
            self.assertIn("review:scene_0002-review", node_ids)
            self.assertIn("review-pending:scene_0003", node_ids)
            self.assertIn("question:scene_0001", node_ids)

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
