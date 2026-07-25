from __future__ import annotations

import json
from pathlib import Path
import unittest

from literary_engineering_studio.projections.narrative.contracts import (
    NarrativeFocusLevel,
    NarrativeFocusScope,
)
from literary_engineering_studio.projections.narrative.focus import resolve_narrative_focus_scope


FIXTURE = Path(__file__).resolve().parents[2] / "contracts" / "fixtures" / "narrative_focus_scope.v1.json"


def _node(node_id: str, node_type: str, order: int = 0, chapter_id: str = "") -> dict[str, object]:
    return {
        "node_id": node_id,
        "type": node_type,
        "order": order,
        "metrics": {"chapter_id": chapter_id} if chapter_id else {},
    }


class NarrativeFocusContractTests(unittest.TestCase):
    def setUp(self):
        self.nodes = [
            _node("scene:scene_0001", "scene", 0, "chapter_0001"),
            _node("scene:scene_0002", "scene", 1, "chapter_0001"),
            _node("scene:scene_0003", "scene", 2, "chapter_0002"),
            _node("character:lin", "character"),
            _node("character:wen", "character"),
        ]
        self.edges = [
            {"source": "character:lin", "target": "scene:scene_0001"},
            {"source": "character:lin", "target": "scene:scene_0002"},
            {"source": "character:wen", "target": "scene:scene_0001"},
        ]

    def test_enum_values_and_json_round_trip_match_shared_fixture(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual([item.value for item in NarrativeFocusLevel], fixture["levels"])
        for case in fixture["cases"]:
            contract = NarrativeFocusScope.from_dict(case["payload"])
            self.assertEqual(contract.as_dict(), case["payload"])

    def test_legacy_level_and_focus_payload_remains_readable(self):
        contract = NarrativeFocusScope.from_dict({"level": "scene", "focus": "scene_0007"})
        self.assertEqual(contract.level, NarrativeFocusLevel.SCENE)
        self.assertEqual(contract.focus_id, "scene_0007")
        self.assertEqual(contract.scene_ids, ())

    def test_chapter_scope_contains_every_scene_and_keeps_the_book_context(self):
        scope = resolve_narrative_focus_scope("chapter", "chapter_0001", self.nodes, self.edges)
        self.assertEqual(scope.scene_ids, ("scene_0001", "scene_0002"))
        self.assertEqual(scope.character_ids, ("lin", "wen"))
        self.assertEqual(scope.anchor_node_ids, ("scene:scene_0001", "scene:scene_0002"))
        self.assertIn("scene:scene_0003", scope.context_node_ids)

    def test_scene_scope_keeps_adjacent_scenes_and_parent_chapter(self):
        scope = resolve_narrative_focus_scope("scene", "scene:scene_0002", self.nodes, self.edges)
        self.assertEqual(scope.focus_id, "scene_0002")
        self.assertEqual(scope.chapter_ids, ("chapter_0001",))
        self.assertEqual(scope.scene_ids, ("scene_0001", "scene_0002"))
        self.assertEqual(scope.anchor_node_ids, ("scene:scene_0002",))

    def test_character_scope_only_changes_focus_and_preserves_other_nodes(self):
        scope = resolve_narrative_focus_scope("character", "character:lin", self.nodes, self.edges)
        self.assertEqual(scope.character_ids, ("lin",))
        self.assertEqual(scope.scene_ids, ("scene_0001", "scene_0002"))
        self.assertEqual(scope.chapter_ids, ("chapter_0001",))
        self.assertEqual(len(scope.anchor_node_ids) + len(scope.context_node_ids), len(self.nodes))


if __name__ == "__main__":
    unittest.main()
