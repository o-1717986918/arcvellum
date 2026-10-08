from __future__ import annotations

import unittest

from literary_engineering_studio_engine.public.literary import (
    parse_scene_material_requests_v3,
    parse_scene_material_requests_v4,
)


def _request(**updates):
    return {
        "kind": "scene-description",
        "target": "当前场面",
        "purpose": "让既有动作在空间里连贯",
        "scene_moment": "人物把碗放到桌面之后",
        "cue": "碗底有修补痕迹",
        "author_prompt": "沿手与桌面的距离组织这一刻。",
        "archive_attachments": [],
        **updates,
    }


class SceneMaterialRequestV4Tests(unittest.TestCase):
    def test_v4_round_trip_carries_creator_context_and_selected_excerpt(self):
        parsed, = parse_scene_material_requests_v4({"material_requests": [_request(
            working_context="阿青已把碗放下；我希望本次只展开这个落点。",
            material_attachments=[{"candidate_id": "v2:actor-call:1", "start_char": 0, "end_char": 9}],
        )]}, ["阿青"])

        self.assertEqual(parsed.working_context, "阿青已把碗放下；我希望本次只展开这个落点。")
        self.assertEqual(parsed.to_dict()["material_attachments"], [{
            "candidate_id": "v2:actor-call:1", "start_char": 0, "end_char": 9,
        }])

    def test_v4_omission_defaults_without_changing_v3_transport(self):
        raw = _request()
        v3, = parse_scene_material_requests_v3({"material_requests": [raw]}, ["阿青"])
        v4, = parse_scene_material_requests_v4({"material_requests": [raw]}, ["阿青"])

        self.assertNotIn("working_context", v3.to_dict())
        self.assertEqual(v4.working_context, "")
        self.assertEqual(v4.material_attachments, ())

    def test_v4_rejects_incomplete_or_invalid_candidate_ranges(self):
        for attachment in (
            {"candidate_id": "v2:actor:1", "start_char": 2},
            {"candidate_id": "v2:actor:1", "start_char": -1, "end_char": 3},
            {"candidate_id": "v2:actor:1", "start_char": 4, "end_char": 4},
        ):
            with self.subTest(attachment=attachment), self.assertRaises(ValueError):
                parse_scene_material_requests_v4({"material_requests": [_request(
                    material_attachments=[attachment],
                )]}, ["阿青"])

    def test_v4_rejects_repeated_candidate_ranges_and_oversized_context(self):
        reference = {"candidate_id": "v2:actor:1"}
        with self.assertRaisesRegex(ValueError, "must not repeat"):
            parse_scene_material_requests_v4({"material_requests": [_request(
                material_attachments=[reference, reference],
            )]}, ["阿青"])
        with self.assertRaisesRegex(ValueError, "working_context"):
            parse_scene_material_requests_v4({"material_requests": [_request(
                working_context="语境" * 3001,
            )]}, ["阿青"])


if __name__ == "__main__":
    unittest.main()
