from __future__ import annotations

import json
from pathlib import Path
import unittest

from literary_engineering_studio.projections.narrative.characters import (
    CharacterReference,
    CharacterReferenceResolution,
    augment_character_graph,
    build_character_references,
)


FIXTURE = Path(__file__).resolve().parents[2] / "contracts" / "fixtures" / "character_reference.v1.json"


class CharacterReferenceContractTests(unittest.TestCase):
    def test_enum_and_round_trip_match_shared_fixture(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual([item.value for item in CharacterReferenceResolution], fixture["resolutions"])
        for case in fixture["cases"]:
            self.assertEqual(CharacterReference.from_dict(case["payload"]).as_dict(), case["payload"])

    def test_aliases_explicit_ids_ambiguity_and_missing_mentions_are_not_lost(self):
        library = {
            "sections": {
                "characters": [
                    {"id": "lin", "title": "林澈", "aliases": ["阿澈", "老周"], "status": "major", "path": "characters/lin.yaml"},
                    {"id": "wen", "title": "闻舟", "aliases": ["小舟"], "status": "major", "path": "characters/wen.yaml"},
                    {"id": "zhou", "title": "周叔", "aliases": ["老周"], "status": "supporting", "path": "characters/zhou.yaml"},
                ],
                "scenes": [
                    {
                        "id": "scene_0001",
                        "subtitle": "chapter_0001",
                        "participants": ["阿澈", "老周", "无名旅客"],
                        "participant_refs": ["wen"],
                    }
                ],
            }
        }
        references = build_character_references(library)
        by_resolution = {
            resolution: [item for item in references if item.resolution is resolution]
            for resolution in CharacterReferenceResolution
        }
        lin = next(item for item in references if item.character_id == "lin")
        wen = next(item for item in references if item.character_id == "wen")
        self.assertEqual(lin.scene_ids, ("scene_0001",))
        self.assertEqual(wen.matched_names, ("wen",))
        self.assertEqual(len(by_resolution[CharacterReferenceResolution.AMBIGUOUS]), 1)
        self.assertEqual(
            by_resolution[CharacterReferenceResolution.AMBIGUOUS][0].candidate_character_ids,
            ("lin", "zhou"),
        )
        self.assertEqual(by_resolution[CharacterReferenceResolution.UNRESOLVED][0].display_name, "无名旅客")

    def test_graph_augmentation_connects_scene_or_chapter_and_preserves_unresolved_nodes(self):
        library = {
            "sections": {
                "characters": [{"id": "lin", "title": "林澈", "aliases": ["阿澈"], "status": "major"}],
                "scenes": [
                    {"id": "scene_0001", "subtitle": "chapter_0001", "participants": ["阿澈", "陌生人"]}
                ],
            }
        }
        references = build_character_references(library)
        scene_nodes = [{"node_id": "scene:scene_0001", "type": "scene"}]
        nodes, edges = augment_character_graph(scene_nodes, [], references)
        self.assertIn("character:lin", {item["node_id"] for item in nodes})
        self.assertTrue(any(item["node_id"].startswith("character:unresolved:") for item in nodes))
        self.assertEqual({item["target"] for item in edges}, {"scene:scene_0001"})
        chapter_nodes = [{"node_id": "chapter:chapter_0001", "type": "chapter"}]
        _, chapter_edges = augment_character_graph(chapter_nodes, [], references)
        self.assertEqual({item["target"] for item in chapter_edges}, {"chapter:chapter_0001"})


if __name__ == "__main__":
    unittest.main()
