from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.narrative_projection_v3 import (
    build_narrative_node_detail_v3,
    build_narrative_projection_v3,
)
from literary_engineering_studio_engine.rhythm_plan import save_rhythm_plan


class NarrativeProjectionV3Tests(unittest.TestCase):
    def setUp(self):
        self.library = {
            "sections": {
                "scenes": [
                    {
                        "id": "scene_0001",
                        "title": "抵达旧码头",
                        "path": "scenes/scene_0001.yaml",
                        "facts": [
                            {"label": "章节", "value": "chapter_0001"},
                            {"label": "参与者", "value": "林澈、闻舟"},
                            {"label": "目标字数", "value": "1800"},
                            {"label": "读者问题", "value": "谁先把信放进了仓库？"},
                        ],
                    },
                    {
                        "id": "scene_0002",
                        "title": "雨夜的选择",
                        "path": "scenes/scene_0002.yaml",
                        "facts": [
                            {"label": "章节", "value": "chapter_0001"},
                            {"label": "参与者", "value": "林澈"},
                            {"label": "目标字数", "value": "2000"},
                            {"label": "承诺回报", "value": "那封信会在卷末改变两人的关系"},
                        ],
                    },
                ],
                "characters": [
                    {"id": "lin", "title": "林澈", "status": "major", "path": "characters/lin.yaml"},
                    {"id": "wen", "title": "闻舟", "status": "major", "path": "characters/wen.yaml"},
                ],
                "branches": [
                    {
                        "id": "scene_0001",
                        "path": "branches/scene_0001/branch_manifest.json",
                        "options": [
                            {"id": "A", "label": "先隐瞒", "summary": "保留关系压力", "selected": True},
                            {"id": "B", "label": "立刻坦白", "summary": "提前引爆冲突", "selected": False},
                        ],
                    }
                ],
                "reviews": [{"id": "review-1", "title": "场景审查", "path": "reviews/scene_0001.json", "status": "pass"}],
                "canon_patches": [],
            }
        }
        self.dashboard = {"next_actions": [{"route": "scene-development", "target": "scene_0001", "next_action": "compose-scene --agent-tasks"}]}
        self.reader = {"units": [], "total_chinese_content_chars": 0}

    def _projection(self, **kwargs):
        with tempfile.TemporaryDirectory() as temporary, patch("literary_engineering_studio.narrative_projection.build_reader_manifest", return_value=self.reader):
            return build_narrative_projection_v3(
                {},
                Path(temporary),
                library_payload=self.library,
                dashboard_payload=self.dashboard,
                **kwargs,
            )

    def test_v3_adds_spatial_semantics_without_coordinates(self):
        projection = self._projection(level="chapter", focus="chapter_0001", grammar="braid")
        self.assertEqual(projection["schema"], "arcvellum/narrative-projection/v3")
        self.assertEqual(projection["spatial_grammar"], "braid")
        self.assertIn("narrative_v2", projection["source_revisions"])
        scene = next(node for node in projection["nodes"] if node["node_id"] == "scene:scene_0001")
        self.assertEqual(scene["world_hint"]["grammar"], "braid")
        self.assertIn(scene["detail_level"], {"near", "mid", "far"})
        self.assertNotIn("x", scene)
        self.assertNotIn("y", scene)
        self.assertGreaterEqual(projection["summary"]["cluster_count"], 1)

    def test_auto_grammar_and_detail_are_safe_and_evidence_bound(self):
        projection = self._projection(level="scene", focus="scene_0001")
        self.assertEqual(projection["spatial_grammar"], "stage")
        with tempfile.TemporaryDirectory() as temporary, patch("literary_engineering_studio.narrative_projection.build_reader_manifest", return_value=self.reader):
            detail = build_narrative_node_detail_v3(
                {},
                Path(temporary),
                "scene:scene_0001",
                level="scene",
                focus="scene_0001",
                library_payload=self.library,
                dashboard_payload=self.dashboard,
            )
        self.assertEqual(detail["schema"], "arcvellum/narrative-node-detail/v1")
        self.assertEqual(detail["node"]["label"], "抵达旧码头")
        self.assertIn("open-detail", {item["id"] for item in detail["available_actions"]})
        self.assertTrue(detail["relationships"])

    def test_v3_is_stable_for_same_evidence_and_requested_grammar(self):
        with tempfile.TemporaryDirectory() as temporary, patch("literary_engineering_studio.narrative_projection.build_reader_manifest", return_value=self.reader):
            root = Path(temporary)
            first = build_narrative_projection_v3(
                {}, root, level="chapter", focus="chapter_0001", grammar="strata",
                library_payload=self.library, dashboard_payload=self.dashboard,
            )
            second = build_narrative_projection_v3(
                {}, root, level="chapter", focus="chapter_0001", grammar="strata",
                library_payload=self.library, dashboard_payload=self.dashboard,
            )
        self.assertEqual(first["revision"], second["revision"])
        self.assertEqual(first["layout_seed"], second["layout_seed"])

    def test_book_projection_aggregates_a_thousand_scene_inventory(self):
        scenes = []
        for index in range(1000):
            scenes.append({
                "id": f"scene_{index + 1:04d}",
                "title": f"场景 {index + 1}",
                "facts": [
                    {"label": "章节", "value": f"chapter_{index // 10 + 1:04d}"},
                    {"label": "目标字数", "value": "1600"},
                ],
            })
        library = {"sections": {"scenes": scenes, "characters": [], "branches": [], "reviews": [], "canon_patches": []}}
        with tempfile.TemporaryDirectory() as temporary, patch("literary_engineering_studio.narrative_projection.build_reader_manifest", return_value=self.reader):
            projection = build_narrative_projection_v3(
                {},
                Path(temporary),
                level="book",
                library_payload=library,
                dashboard_payload={},
            )
        self.assertTrue(projection["summary"]["aggregated"])
        self.assertEqual(projection["summary"]["scene_count"], 1000)
        self.assertLessEqual(len(projection["nodes"]), 112)
        self.assertEqual(projection["lod_summary"]["far"], 100)
        self.assertEqual(set(("dashboard", "library", "reader", "jobs")).issubset(projection["source_revisions"]), True)

    def test_v3_exposes_the_formal_rhythm_plan_as_a_spatial_hint(self):
        with tempfile.TemporaryDirectory() as temporary, patch("literary_engineering_studio.narrative_projection.build_reader_manifest", return_value=self.reader):
            root = Path(temporary)
            (root / "scenes").mkdir()
            (root / "scenes" / "scene_0001.yaml").write_text(
                "scene_id: scene_0001\nchapter_id: chapter_0001\ntitle: 抵达旧码头\nword_count_target: 1800\n",
                encoding="utf-8",
            )
            save_rhythm_plan(root, [{
                "scene_id": "scene_0001",
                "pace": "fast",
                "rhythm_role": "turn",
                "scene_function": ["改变人物选择"],
                "tension_curve": {"entry": 3, "peak": 5, "exit": 4},
                "detail_level": "set_piece",
            }])
            projection = build_narrative_projection_v3(
                {}, root, level="chapter", focus="chapter_0001", grammar="spine",
                library_payload=self.library, dashboard_payload=self.dashboard,
            )
        scene = next(node for node in projection["nodes"] if node["node_id"] == "scene:scene_0001")
        self.assertEqual(scene["rhythm"]["peak"], 5)
        self.assertEqual(scene["rhythm"]["detail_level"], "set_piece")
        self.assertEqual(scene["rhythm"]["source"], "rhythm-plan")


if __name__ == "__main__":
    unittest.main()
