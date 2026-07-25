import json
import unittest

from literary_engineering_studio.projections.narrative.patches import (
    apply_projection_patch,
    build_projection_patch,
)


class NarrativeProjectionPatchTests(unittest.TestCase):
    def test_patch_round_trip_preserves_order_metadata_and_exact_revision(self):
        previous = _projection("revision-one")
        previous["legacy_hint"] = "remove me"
        current = _projection("revision-two")
        current["summary"] = {"node_count": 2}
        current["nodes"] = [
            {**current["nodes"][1], "label": "更新后的第二章"},
            {"node_id": "chapter:3", "label": "第三章"},
        ]
        current["edges"] = [{"edge_id": "edge:2>3", "source": "chapter:2", "target": "chapter:3"}]
        delta = {
            "initial": False,
            "added_nodes": ["chapter:3"],
            "removed_nodes": ["chapter:1"],
            "updated_nodes": ["chapter:2"],
            "added_edges": ["edge:2>3"],
            "removed_edges": ["edge:1>2"],
            "updated_edges": [],
        }
        patch = build_projection_patch(
            previous,
            current,
            sequence=2,
            delta=delta,
            motion_events=[{"type": "chapter-grown", "node_id": "chapter:3"}],
        )
        rebuilt = apply_projection_patch(previous, patch)
        self.assertEqual(rebuilt["nodes"], current["nodes"])
        self.assertEqual(rebuilt["edges"], current["edges"])
        self.assertEqual(rebuilt["summary"], current["summary"])
        self.assertEqual(rebuilt["revision"], "revision-two")
        self.assertEqual(rebuilt["sequence"], 2)
        self.assertNotIn("legacy_hint", rebuilt)
        self.assertEqual(patch["meta_remove"], ["legacy_hint"])

    def test_patch_rejects_wrong_base_and_invalid_upsert(self):
        previous = _projection("revision-one")
        current = _projection("revision-two")
        patch = build_projection_patch(previous, current, sequence=2, delta={}, motion_events=[])
        patch["base_revision"] = "another-revision"
        with self.assertRaisesRegex(ValueError, "base revision mismatch"):
            apply_projection_patch(previous, patch)
        patch["base_revision"] = "revision-one"
        patch["nodes"]["upsert"] = [{"label": "missing identity"}]
        with self.assertRaisesRegex(ValueError, "node_id upsert is invalid"):
            apply_projection_patch(previous, patch)

    def test_single_node_change_is_smaller_than_a_large_full_projection(self):
        previous = _large_projection("revision-one", 1000)
        current = _large_projection("revision-two", 1000)
        current["nodes"][500]["label"] = "发生语义变化的场景"
        patch = build_projection_patch(
            previous,
            current,
            sequence=2,
            delta={"updated_nodes": ["scene:0501"]},
            motion_events=[],
        )
        full_bytes = len(json.dumps(current, ensure_ascii=False).encode("utf-8"))
        patch_bytes = len(json.dumps(patch, ensure_ascii=False).encode("utf-8"))
        self.assertLess(patch_bytes, full_bytes * 0.1)
        self.assertEqual(apply_projection_patch(previous, patch)["nodes"], current["nodes"])


def _projection(revision: str) -> dict[str, object]:
    return {
        "ok": True,
        "schema": "arcvellum/narrative-projection/v3",
        "project_root": "C:/fixture",
        "revision": revision,
        "projection_revision": revision,
        "sequence": 1,
        "summary": {"node_count": 2},
        "nodes": [
            {"node_id": "chapter:1", "label": "第一章"},
            {"node_id": "chapter:2", "label": "第二章"},
        ],
        "edges": [{"edge_id": "edge:1>2", "source": "chapter:1", "target": "chapter:2"}],
        "delta": {},
        "motion_events": [],
    }


def _large_projection(revision: str, count: int) -> dict[str, object]:
    projection = _projection(revision)
    projection["nodes"] = [
        {"node_id": f"scene:{index + 1:04d}", "label": f"场景 {index + 1}", "metrics": {"order": index + 1}}
        for index in range(count)
    ]
    projection["edges"] = [
        {
            "edge_id": f"edge:{index:04d}>{index + 1:04d}",
            "source": f"scene:{index:04d}",
            "target": f"scene:{index + 1:04d}",
        }
        for index in range(1, count)
    ]
    return projection


if __name__ == "__main__":
    unittest.main()
