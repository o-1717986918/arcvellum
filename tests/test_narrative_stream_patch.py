import json
from pathlib import Path
import tempfile
from threading import Lock
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from literary_engineering_studio.api.routers.narrative import (
    NarrativeRouterDependencies,
    _v3_transition,
    build_narrative_router,
)
from literary_engineering_studio.projections.narrative.patches import (
    apply_projection_patch,
    build_projection_patch,
)
from literary_engineering_studio.projections.narrative_projection import (
    projection_delta,
    projection_motion_events,
)


class NarrativeStreamPatchTests(unittest.TestCase):
    def setUp(self):
        self.dependencies = SimpleNamespace(
            spatial_projection_delta=projection_delta,
            spatial_projection_motion_events=projection_motion_events,
            spatial_projection_patch=build_projection_patch,
        )

    def test_first_transition_is_a_complete_snapshot(self):
        current = _projection("revision-one", "第一章")
        event, payload = _v3_transition(self.dependencies, None, current, 1)
        self.assertEqual(event, "narrative.v3.projection")
        self.assertEqual(payload["nodes"], current["nodes"])
        self.assertEqual(payload["sequence"], 1)
        self.assertTrue(payload["delta"]["initial"])

    def test_following_transition_is_a_patch_bound_to_previous_revision(self):
        previous = _projection("revision-one", "第一章")
        current = _projection("revision-two", "修改后的第一章")
        event, patch = _v3_transition(self.dependencies, previous, current, 2)
        self.assertEqual(event, "narrative.v3.patch")
        self.assertEqual(patch["base_revision"], "revision-one")
        self.assertEqual(patch["target_revision"], "revision-two")
        self.assertEqual(apply_projection_patch(previous, patch)["nodes"], current["nodes"])

    def test_route_streams_full_snapshot_then_incremental_patch(self):
        previous = _projection("revision-one", "第一章")
        current = _projection("revision-two", "修改后的第一章")
        projections = iter((previous, current))
        app = FastAPI()
        app.include_router(build_narrative_router(_router_dependencies(projections)))
        with tempfile.TemporaryDirectory() as temporary:
            Path(temporary, "project.yaml").write_text("project:\n  title: fixture\n", encoding="utf-8")
            with TestClient(app) as client, patch(
                "literary_engineering_studio.api.routers.narrative.time.sleep",
                return_value=None,
            ):
                response = client.get(
                    "/narrative/stream/v3",
                    params={"project_root": temporary, "max_events": 2, "interval_seconds": 2},
                )
        self.assertEqual(response.status_code, 200)
        events = _sse_events(response.text)
        self.assertEqual([item["event"] for item in events], [
            "narrative.v3.projection",
            "narrative.v3.patch",
        ])
        self.assertEqual(
            apply_projection_patch(events[0]["data"], events[1]["data"])["nodes"],
            current["nodes"],
        )


def _router_dependencies(projections) -> NarrativeRouterDependencies:
    def projection_v3(*_args, **_kwargs):
        return next(projections)

    return NarrativeRouterDependencies(
        config={},
        cached_read_model=lambda _key, _root, builder: builder(),
        dashboard_snapshot=lambda _root: {},
        narrative_evidence_snapshot=lambda _root: {},
        library_snapshot=lambda _root: {},
        build_projection=lambda *_args, **_kwargs: {},
        projection_delta=projection_delta,
        projection_motion_events=projection_motion_events,
        build_projection_v3=projection_v3,
        build_node_detail_v3=lambda *_args, **_kwargs: {},
        build_projection_v4=projection_v3,
        build_node_detail_v4=lambda *_args, **_kwargs: {},
        spatial_projection_delta=projection_delta,
        spatial_projection_motion_events=projection_motion_events,
        spatial_projection_patch=build_projection_patch,
        v2_stream_state={},
        v3_stream_state={},
        v4_stream_state={},
        stream_lock=Lock(),
        sse=_sse,
    )


def _sse(event: str, payload: dict[str, object], event_id: int | str | None) -> str:
    return f"id: {event_id}\nevent: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _sse_events(text: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for block in text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        events.append({"event": fields["event"], "data": json.loads(fields["data"])})
    return events


def _projection(revision: str, label: str) -> dict[str, object]:
    return {
        "ok": True,
        "schema": "arcvellum/narrative-projection/v3",
        "project_root": "C:/fixture",
        "revision": revision,
        "projection_revision": revision,
        "sequence": 0,
        "summary": {"node_count": 1},
        "nodes": [{"node_id": "chapter:1", "label": label, "status": "planned", "metrics": {}}],
        "edges": [],
        "delta": {},
        "motion_events": [],
    }


if __name__ == "__main__":
    unittest.main()
