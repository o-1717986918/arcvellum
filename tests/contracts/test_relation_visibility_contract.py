from __future__ import annotations

import json
from pathlib import Path
import unittest

from literary_engineering_studio.projections.narrative.contracts import (
    NarrativeFocusLevel,
    NarrativeFocusScope,
    RelationFamily,
    RelationFocusState,
    RelationLodMode,
    RelationVisibilityProfile,
)
from literary_engineering_studio.projections.narrative.relations import (
    apply_relation_focus,
    build_relation_profiles,
    normalize_relation_edges,
)


FIXTURE = Path(__file__).resolve().parents[2] / "contracts" / "fixtures" / "relation_visibility_profile.v1.json"


class RelationVisibilityContractTests(unittest.TestCase):
    def setUp(self):
        self.nodes = [
            {"node_id": "scene:one", "type": "scene"},
            {"node_id": "scene:two", "type": "scene"},
            {"node_id": "branch:one:A", "type": "branch"},
            {"node_id": "review:one", "type": "review"},
            {"node_id": "character:lin", "type": "character"},
        ]
        self.edges = [
            {"edge_id": "bridge", "source": "scene:one", "target": "scene:two", "type": "bridge"},
            {"edge_id": "branch", "source": "scene:one", "target": "branch:one:A", "type": "branch"},
            {"edge_id": "review", "source": "scene:one", "target": "review:one", "type": "review"},
            {"edge_id": "character", "source": "character:lin", "target": "scene:one", "type": "participates"},
        ]

    def test_enums_and_profile_round_trip_match_shared_fixture(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual([item.value for item in RelationFamily], fixture["families"])
        self.assertEqual([item.value for item in RelationLodMode], fixture["lod_modes"])
        self.assertEqual([item.value for item in RelationFocusState], fixture["focus_states"])
        profile = RelationVisibilityProfile.from_dict(fixture["sample"])
        self.assertEqual(profile.as_dict(), fixture["sample"])

    def test_normalization_classifies_without_dropping_valid_edges(self):
        normalized = normalize_relation_edges(self.edges, self.nodes)
        self.assertEqual([item["edge_id"] for item in normalized], [item["edge_id"] for item in self.edges])
        families = {item["edge_id"]: item["relation_family"] for item in normalized}
        self.assertEqual(families["bridge"], "narrative-spine")
        self.assertEqual(families["branch"], "scene-branch")
        self.assertEqual(families["review"], "scene-review")
        self.assertEqual(families["character"], "character-scene")

    def test_focus_marks_internal_attached_and_context_relations(self):
        scope = NarrativeFocusScope(
            level=NarrativeFocusLevel.CHAPTER,
            focus_id="chapter_0001",
            anchor_node_ids=("scene:one", "scene:two"),
        )
        focused = apply_relation_focus(normalize_relation_edges(self.edges, self.nodes), scope)
        states = {item["edge_id"]: item["focus_state"] for item in focused}
        self.assertEqual(states["bridge"], "internal")
        self.assertEqual(states["branch"], "attached")
        self.assertEqual(states["character"], "attached")

    def test_profiles_include_zero_count_families_for_a_stable_legend(self):
        scope = NarrativeFocusScope(
            level=NarrativeFocusLevel.SCENE,
            focus_id="one",
            anchor_node_ids=("scene:one",),
        )
        edges = apply_relation_focus(normalize_relation_edges(self.edges, self.nodes), scope)
        profiles = build_relation_profiles(edges)
        self.assertEqual(len(profiles), len(RelationFamily))
        by_family = {item.family: item for item in profiles}
        self.assertEqual(by_family[RelationFamily.SCENE_BRANCH].edge_count, 1)
        self.assertEqual(by_family[RelationFamily.SCENE_BRANCH].focused_edge_count, 1)
        self.assertEqual(by_family[RelationFamily.SCENE_PROMISE_PAYOFF].edge_count, 0)


if __name__ == "__main__":
    unittest.main()
