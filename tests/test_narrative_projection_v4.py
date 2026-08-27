from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.projections.narrative_projection_v4 import (
    build_narrative_node_detail_v4,
    build_narrative_projection_v4,
)


class NarrativeProjectionV4Tests(unittest.TestCase):
    def setUp(self):
        self.library = {
            "sections": {
                "scenes": [
                    {
                        "id": "scene_0001",
                        "title": "抵达旧码头",
                        "path": "scenes/scene_0001.yaml",
                        "status": "planned",
                        "facts": [
                            {"label": "章节", "value": "chapter_0001"},
                            {"label": "参与者", "value": "林澈"},
                            {"label": "目标字数", "value": "1800"},
                        ],
                    },
                    {
                        "id": "scene_0002",
                        "title": "越过旧桥",
                        "path": "scenes/scene_0002.yaml",
                        "status": "planned",
                        "facts": [
                            {"label": "章节", "value": "chapter_0002"},
                            {"label": "参与者", "value": "林澈"},
                            {"label": "目标字数", "value": "2200"},
                        ],
                    },
                ],
                "characters": [
                    {"id": "lin", "title": "林澈", "status": "major", "path": "characters/lin.yaml"},
                ],
                "world": [
                    {"id": "harbor", "title": "旧港", "path": "canon/locations/harbor.yaml", "status": "formal"},
                ],
                "style": [
                    {"id": "restrained", "title": "克制叙事", "path": "style/active_style.md", "status": "formal"},
                ],
                "story_architecture": [
                    {"id": "story_architecture", "title": "全书故事架构", "path": "plot/story_architecture.json", "status": "complete"},
                ],
                "word_budget": [
                    {"id": "word_budget", "title": "长篇字数预算", "path": "plot/word_budget/word_budget.json", "status": "complete"},
                ],
                "drafts": [],
                "branches": [{
                    "id": "scene_0001",
                    "path": "branches/scene_0001/branch_manifest.json",
                    "options": [{"id": "A", "label": "隐瞒", "selected": False}],
                }],
                "reviews": [
                    {"id": "scene-review", "title": "场景审查", "path": "reviews/scene_0001.json", "status": "pass"},
                    {"id": "receipt", "title": "机器回执", "path": "reviews/scene_0001.agent_completion.json", "status": "complete"},
                    {"id": "scene-task", "title": "平台 Agent 任务说明：formal scene review scene_0001", "path": "reviews/scene_0001.agent_tasks.md", "status": "blocked"},
                ],
                "decisions": [
                    {"id": "choice-1", "title": "选择叙事方向", "path": "workflow/human_choices/choice-1.json", "status": "waiting_human"},
                ],
                "canon_patches": [],
            }
        }
        self.dashboard = {
            "next_actions": [{
                "route": "scene-development",
                "target": "scene_0001",
                "next_action": "compose-scene --agent-tasks",
            }]
        }
        self.reader = {
            "units": [{
                "unit_id": "chapter_0001",
                "chapter_id": "chapter_0001",
                "title": "第一章",
                "coverage": ["scene_0001"],
                "chinese_content_chars": 1900,
                "body_endpoint": "/reader/units/chapter_0001",
            }],
            "total_chinese_content_chars": 1900,
        }

    def _projection(self, **kwargs):
        with tempfile.TemporaryDirectory() as temporary, patch(
            "literary_engineering_studio.projections.narrative_projection.build_reader_manifest",
            return_value=self.reader,
        ):
            return build_narrative_projection_v4(
                {},
                Path(temporary),
                library_payload=self.library,
                dashboard_payload=self.dashboard,
                **kwargs,
            )

    def test_every_focus_uses_the_same_complete_graph(self):
        book = self._projection(level="book")
        chapter = self._projection(level="chapter", focus="chapter_0001")
        scene = self._projection(level="scene", focus="scene_0001")
        character = self._projection(level="character", focus="character:lin")
        expected = {item["node_id"] for item in book["nodes"]}
        for projection in (chapter, scene, character):
            self.assertEqual({item["node_id"] for item in projection["nodes"]}, expected)
        self.assertTrue(book["summary"]["whole_graph"])

    def test_literary_assets_and_formal_prose_are_interactive_nodes(self):
        projection = self._projection(level="book", grammar="constellation")
        node_ids = {item["node_id"] for item in projection["nodes"]}
        self.assertIn("project:origin", node_ids)
        self.assertIn("world:harbor", node_ids)
        self.assertIn("style:restrained", node_ids)
        self.assertIn("formal-prose:chapter_0001", node_ids)
        self.assertIn("human-decision:choice-1", node_ids)
        self.assertFalse(any(item["type"] == "task" for item in projection["nodes"]))
        self.assertFalse(any("agent_tasks" in item["node_id"] for item in projection["nodes"]))
        self.assertFalse(any("平台 Agent 任务说明" in item["label"] for item in projection["nodes"]))
        self.assertEqual(projection["activities"][0]["target"], "scene_0001")
        self.assertEqual(projection["activities"][0]["status"], "available")
        for item in projection["nodes"]:
            action_kinds = {action["kind"] for action in item["available_actions"]}
            self.assertIn("inspect", action_kinds)
            self.assertIn("focus", action_kinds)

    def test_hierarchy_and_action_risk_are_backend_owned(self):
        projection = self._projection(level="scene", focus="scene_0001")
        scene = next(item for item in projection["nodes"] if item["node_id"] == "scene:scene_0001")
        branch = next(item for item in projection["nodes"] if item["type"] == "branch")
        decision = next(item for item in projection["nodes"] if item["type"] == "human-decision")
        self.assertEqual(scene["parent_id"], "chapter:chapter_0001")
        self.assertEqual(branch["parent_id"], "scene:scene_0001")
        self.assertTrue(any(action["risk_level"] == "formal" for action in branch["available_actions"]))
        self.assertTrue(any(action["requires_confirmation"] for action in decision["available_actions"]))

    def test_node_detail_reuses_projection_action_contract(self):
        with tempfile.TemporaryDirectory() as temporary, patch(
            "literary_engineering_studio.projections.narrative_projection.build_reader_manifest",
            return_value=self.reader,
        ):
            detail = build_narrative_node_detail_v4(
                {},
                Path(temporary),
                "style:restrained",
                level="book",
                library_payload=self.library,
                dashboard_payload=self.dashboard,
            )
        self.assertEqual(detail["schema"], "arcvellum/narrative-node-detail/v2")
        self.assertEqual(detail["workspace_hints"]["preferred_workspace"], "style")
        self.assertTrue(any(action["kind"] == "open-workspace" for action in detail["available_actions"]))


if __name__ == "__main__":
    unittest.main()
