from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.api.streaming import stream_typed_events
from literary_engineering_studio.api_server import create_app
from literary_engineering_studio.application.strategy_projection import (
    strategy_projection,
    typed_plan_events,
)
from literary_engineering_studio.config import default_config
from literary_engineering_studio.orchestration import (
    OrchestrationMode,
    OrchestrationSettings,
    StrategyPreset,
)


def _app(root: Path):
    config = default_config()
    config["application"]["data_root"] = str(root)
    config["application"]["database_path"] = str(root / "studio.sqlite3")
    config["application"]["projects_root"] = str(root / "projects")
    config["worker"]["runs_root"] = str(root / "runs")
    config["agent_runners"]["opencode"]["data_root"] = str(root)
    return create_app(config)


def _work_project(root: Path) -> Path:
    (root / "project.yaml").write_text(
        "project:\n  title: test\n",
        encoding="utf-8",
    )
    return root


def _settings(**overrides):
    base = dict(
        enabled=False,
        configured_mode=OrchestrationMode.FIXED,
        effective_mode=OrchestrationMode.FIXED,
        strategy_preset=StrategyPreset.BALANCED,
        constitution_version="1",
    )
    base.update(overrides)
    return OrchestrationSettings(**base)


class StrategyProjectionTests(unittest.TestCase):
    def test_default_projection_is_fixed_and_read_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = _work_project(Path(temporary))

            projection = strategy_projection(root, _settings())

            self.assertEqual(projection["schema"], "arcvellum/strategy-projection/v1")
            self.assertEqual(projection["settings"]["mode"], "fixed")
            self.assertFalse(projection["settings"]["enabled"])
            self.assertIsNone(projection["active_plan"])

    def test_active_plan_summary_is_read_from_projection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = _work_project(Path(temporary))
            path = root / "workflow" / "orchestration"
            path.mkdir(parents=True)
            (path / "active_plan.json").write_text(
                json.dumps(
                    {
                        "plan_id": "plan-1",
                        "revision": 3,
                        "status": "active",
                        "scope": {"kind": "chapter", "key": "chapter_01"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            projection = strategy_projection(root, _settings())

            self.assertEqual(projection["active_plan"]["plan_id"], "plan-1")
            self.assertEqual(projection["active_plan"]["revision"], 3)
            self.assertEqual(
                projection["active_plan"]["scope_key"],
                "chapter_01",
            )

    def test_typed_plan_events_are_ordered_and_safe(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = _work_project(Path(temporary))
            run = root / "workflow" / "orchestration" / "runs" / "run-1"
            run.mkdir(parents=True)
            (run / "events.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "event_id": "e2",
                                "type": "plan.candidate.completed",
                                "plan_id": "plan-1",
                                "revision": 2,
                                "created_at": "2026-07-30T02:00:00+00:00",
                            },
                            ensure_ascii=False,
                        ),
                        "not-json",
                        json.dumps(
                            {
                                "event_id": "e1",
                                "type": "plan.candidate.started",
                                "plan_id": "plan-1",
                                "revision": 1,
                                "created_at": "2026-07-30T01:00:00+00:00",
                            },
                            ensure_ascii=False,
                        ),
                    ]
                ),
                encoding="utf-8",
            )

            events = typed_plan_events(root)

            self.assertEqual(
                [event["event_id"] for event in events],
                ["e1", "e2"],
            )
            self.assertEqual(events[1]["event_type"], "plan.candidate.completed")

    def test_missing_event_id_gets_stable_content_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = _work_project(Path(temporary))
            run = root / "workflow" / "orchestration" / "runs" / "run-1"
            run.mkdir(parents=True)
            payload = {
                "type": "plan.review.completed",
                "plan_id": "plan-1",
                "revision": 2,
                "created_at": "2026-07-30T02:00:00+00:00",
            }
            (run / "events.jsonl").write_text(
                json.dumps(payload, ensure_ascii=False) + "\n"
                + json.dumps(payload, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            first = typed_plan_events(root)
            second = typed_plan_events(root)

            self.assertEqual(len(first), 1)
            self.assertEqual(first, second)
            self.assertTrue(first[0]["event_id"].startswith("plan-"))


class StrategyApiTests(unittest.TestCase):
    def test_strategy_endpoint_returns_read_only_projection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = _work_project(Path(temporary))
            from fastapi.testclient import TestClient

            with TestClient(_app(root)) as client:
                response = client.get(
                    "/project/strategy",
                    params={"project_root": str(root)},
                )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload["ok"])
            self.assertEqual(
                payload["strategy"]["settings"]["mode"],
                "fixed",
            )

    def test_events_endpoint_streams_typed_plan_events(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = _work_project(Path(temporary))
            run = root / "workflow" / "orchestration" / "runs" / "run-1"
            run.mkdir(parents=True)
            (run / "events.jsonl").write_text(
                json.dumps(
                    {
                        "event_id": "e1",
                        "type": "plan.candidate.completed",
                        "plan_id": "plan-1",
                        "revision": 1,
                        "created_at": "2026-07-30T01:00:00+00:00",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            from fastapi.testclient import TestClient

            with TestClient(_app(root)) as client:
                response = client.get(
                    "/project/strategy/events",
                    params={"project_root": str(root)},
                )

            self.assertEqual(response.status_code, 200)
            self.assertIn("text/event-stream", response.headers["content-type"])
            self.assertIn("event: plan-event", response.text)
            self.assertIn("plan.candidate.completed", response.text)
            self.assertIn("stream complete", response.text)
            self.assertIn("event: stream.terminal", response.text)

    def test_events_follow_mode_resets_unknown_cursor_and_stops_at_limit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = _work_project(Path(temporary))
            run = root / "workflow" / "orchestration" / "runs" / "run-1"
            run.mkdir(parents=True)
            (run / "events.jsonl").write_text(
                json.dumps(
                    {
                        "event_id": "e1",
                        "type": "plan.candidate.completed",
                        "plan_id": "plan-1",
                        "revision": 1,
                        "created_at": "2026-07-30T01:00:00+00:00",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            from fastapi.testclient import TestClient

            with TestClient(_app(root)) as client:
                response = client.get(
                    "/project/strategy/events",
                    params={
                        "project_root": str(root),
                        "follow": "true",
                        "max_events": 1,
                    },
                    headers={"Last-Event-ID": "unknown-event"},
                )

            self.assertEqual(response.status_code, 200)
            self.assertIn("event: stream.reset", response.text)
            self.assertIn("id: e1", response.text)
            self.assertIn('"status": "max-events"', response.text)

    def test_route_surface_includes_strategy_endpoints(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = _work_project(Path(temporary))
            app = _app(root)

        paths = set(app.openapi()["paths"])
        self.assertEqual(
            paths & {"/project/strategy", "/project/strategy/events"},
            {"/project/strategy", "/project/strategy/events"},
        )


class StreamTypedEventsTests(unittest.TestCase):
    def test_stream_emits_typed_events_without_pacing(self):
        import asyncio

        response = stream_typed_events(
            "plan-event",
            [
                {"event_id": "a", "event_type": "one", "plan_id": "p"},
                {"event_id": "b", "event_type": "two", "plan_id": "p"},
            ],
            interval_seconds=0.0,
        )

        async def collect():
            return b"".join(
                [
                    chunk.encode("utf-8")
                    async for chunk in response.body_iterator
                ]
            )

        joined = asyncio.run(collect()).decode("utf-8")
        self.assertIn("id: a", joined)
        self.assertIn("id: b", joined)
        self.assertEqual(joined.count("event: plan-event"), 2)
        self.assertIn("stream complete", joined)


if __name__ == "__main__":
    unittest.main()
