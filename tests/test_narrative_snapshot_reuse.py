import asyncio
from dataclasses import replace
from pathlib import Path
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from literary_engineering_studio.api_server import _narrative_dependencies
from literary_engineering_studio.api.routers.narrative import build_narrative_router, _v4_streaming_response
from literary_engineering_studio.projections.read_model_cache import ReadModelCache
from literary_engineering_studio.projections import read_model_cache
from literary_engineering_studio.projections.api_read_models import ProjectReadModels


class NarrativeSnapshotReuseTests(unittest.TestCase):
    def test_source_snapshot_is_shared_across_views_and_rebuilt_after_canon_invalidation(self):
        with tempfile.TemporaryDirectory() as temporary, patch(
            "literary_engineering_studio.projections.api_read_models.build_reader_manifest", return_value={"units": []}
        ) as reader, patch(
            "literary_engineering_studio.projections.api_read_models.build_rhythm_hints", return_value={"scenes": {}, "chapters": {}}
        ) as rhythm:
            root, cache = Path(temporary), ReadModelCache()
            models = ProjectReadModels({}, SimpleNamespace(read_models=cache), None)
            first = models.narrative_sources(root)
            first["reader"]["units"].append("consumer mutation")
            self.assertEqual(models.narrative_sources(root)["reader"]["units"], [])
            self.assertEqual((reader.call_count, rhythm.call_count), (1, 1))
            cache.invalidate(root, reason="canon-applied")
            models.narrative_sources(root)
            self.assertEqual((reader.call_count, rhythm.call_count), (2, 2))

    def dependencies(self, root):
        cache = ReadModelCache()
        snapshot = {"ok": True, "schema": "arcvellum/narrative-projection/v4", "project_root": str(root),
                    "revision": "first", "nodes": [{"node_id": "scene:1", "available_actions": [{"kind": "inspect"}]}], "edges": []}
        build = Mock(side_effect=lambda *_a, **_kw: snapshot)
        deps = _narrative_dependencies({}, cache.get, lambda _r: {}, lambda _r: {}, lambda _r: {},
                                       lambda _r: {"reader": {}, "rhythm": {}}, {}, {}, {}, threading.Lock())
        return replace(deps, build_projection_v4=build), cache, snapshot, build

    def test_http_detail_reuses_projection_and_refreshes_after_invalidation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "project.yaml").write_text("project:\n  title: fixture\n", encoding="utf-8")
            deps, cache, snapshot, build = self.dependencies(root)
            app = FastAPI()
            app.include_router(build_narrative_router(deps))
            with TestClient(app) as client:
                params = {"project_root": str(root)}
                self.assertEqual(client.get("/narrative/projection/v4", params=params).status_code, 200)
                first = client.get("/narrative/projection/v4/nodes/scene:1", params=params)
                self.assertEqual(first.status_code, 200)
                self.assertEqual(first.json()["projection_revision"], "first")
                self.assertEqual(build.call_count, 1)
                self.assertEqual(client.get("/narrative/projection/v4/nodes/absent", params=params).status_code, 404)
                snapshot["revision"] = "second"
                cache.invalidate(root)
                self.assertEqual(client.get("/narrative/projection/v4/nodes/scene:1", params=params).json()["projection_revision"], "second")
                self.assertEqual(build.call_count, 2)

    def test_unchanged_sse_tick_does_not_clone_the_full_projection(self):
        async def consume(deps, root):
            response = _v4_streaming_response(deps, root, "book", "", "auto", 0, 2)
            iterator = response.body_iterator
            first = await anext(iterator)
            self.assertIn("narrative.v4.projection", first)
            with patch.object(read_model_cache, "deepcopy", wraps=read_model_cache.deepcopy) as clone:
                heartbeat = await anext(iterator)
                self.assertIn("heartbeat", heartbeat)
                self.assertEqual(clone.call_count, 1)
                self.assertIsNone(clone.call_args.args[0])
            await iterator.aclose()
        with tempfile.TemporaryDirectory() as temporary, patch("literary_engineering_studio.api.routers.narrative.time.sleep"):
            root = Path(temporary).resolve()
            deps, _cache, _snapshot, build = self.dependencies(root)
            asyncio.run(consume(deps, root))
            self.assertEqual(build.call_count, 1)
