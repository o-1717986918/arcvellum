from __future__ import annotations

import unittest

from literary_engineering_studio.observability.throughput_metrics import (
    build_throughput_projection,
)


def _event(
    sequence: int,
    event: str,
    at: str,
    *,
    task_id: str = "",
    route: str = "",
    **data,
) -> dict:
    payload = dict(data)
    if task_id:
        payload["task_id"] = task_id
    if route:
        payload["route"] = route
    return {
        "sequence": sequence,
        "event": event,
        "at": at,
        "data": payload,
    }


class ThroughputMetricsTests(unittest.TestCase):
    def test_aggregates_tasks_turns_repairs_usage_and_stage_durations(self):
        events = [
            _event(1, "worker.task.selecting", "2026-07-25T00:00:00Z"),
            _event(
                2,
                "worker.task.opened",
                "2026-07-25T00:00:02Z",
                task_id="task-a",
                route="scene-development",
            ),
            _event(3, "worker.runner.started", "2026-07-25T00:00:03Z", task_id="task-a"),
            _event(
                4,
                "worker.usage.updated",
                "2026-07-25T00:00:04Z",
                usage={"input": 100, "output": 30, "reasoning": 4, "cache": {"read": 20, "write": 2}},
                cost_usd=0.012,
            ),
            _event(
                5,
                "worker.validation.failed",
                "2026-07-25T00:00:08Z",
                kind="sandbox-preflight",
                attempt=0,
            ),
            _event(6, "worker.repair.started", "2026-07-25T00:00:09Z", attempt=1),
            _event(
                7,
                "worker.usage.updated",
                "2026-07-25T00:00:10Z",
                usage={"input": 40, "output": 12, "total": 52},
                cost_usd=0.004,
            ),
            _event(
                8,
                "worker.validation.passed",
                "2026-07-25T00:00:11Z",
                kind="sandbox-preflight",
                attempt=1,
            ),
            _event(9, "worker.runner.completed", "2026-07-25T00:00:12Z"),
            _event(10, "worker.validation.started", "2026-07-25T00:00:13Z"),
            _event(
                11,
                "worker.validation.passed",
                "2026-07-25T00:00:16Z",
                kind="exact-task-gate",
            ),
            _event(12, "worker.task.selecting", "2026-07-25T00:00:20Z"),
            _event(
                13,
                "worker.task.opened",
                "2026-07-25T00:00:21Z",
                task_id="task-b",
                route="scene-development",
            ),
            _event(14, "worker.runner.started", "2026-07-25T00:00:23Z", task_id="task-b"),
            _event(
                15,
                "worker.validation.passed",
                "2026-07-25T00:00:25Z",
                kind="sandbox-preflight",
                attempt=0,
            ),
            _event(16, "worker.runner.completed", "2026-07-25T00:00:28Z"),
            _event(17, "task.recovery_started", "2026-07-25T00:00:29Z", task_id="task-b"),
        ]

        projection = build_throughput_projection(events)

        self.assertEqual(projection["schema"], "arcvellum/throughput-projection/v1")
        self.assertEqual(projection["mode"], "measure-only")
        self.assertEqual(projection["event_count"], 17)
        self.assertEqual(projection["task_count"], 2)
        self.assertEqual(projection["model_turns"], 3)
        self.assertEqual(projection["repairs"], 1)
        self.assertEqual(projection["retries"], 1)
        self.assertEqual(
            projection["first_validation"],
            {
                "evaluated_tasks": 2,
                "passed_first_attempt": 1,
                "failed_first_attempt": 1,
                "pass_rate": 0.5,
            },
        )
        self.assertEqual(projection["usage"]["input_tokens"], 140)
        self.assertEqual(projection["usage"]["output_tokens"], 42)
        self.assertEqual(projection["usage"]["reasoning_tokens"], 4)
        self.assertEqual(projection["usage"]["cache_read_tokens"], 20)
        self.assertEqual(projection["usage"]["cache_write_tokens"], 2)
        self.assertEqual(projection["usage"]["total_tokens"], 186)
        self.assertAlmostEqual(projection["usage"]["cost_usd"], 0.016)
        self.assertEqual(
            projection["stages"]["task_selection"],
            {
                "sample_count": 2,
                "total_seconds": 3.0,
                "average_seconds": 1.5,
                "max_seconds": 2.0,
            },
        )
        self.assertEqual(projection["stages"]["model_execution"]["sample_count"], 2)
        self.assertEqual(projection["stages"]["model_execution"]["total_seconds"], 14.0)
        self.assertEqual(projection["stages"]["validation_writeback"]["total_seconds"], 3.0)
        self.assertEqual(
            [item["task_id"] for item in projection["tasks"]],
            ["task-a", "task-b"],
        )

    def test_ignores_unknown_events_and_malformed_timestamps(self):
        projection = build_throughput_projection(
            [
                {"sequence": "bad", "event": "unknown", "at": "not-a-time", "data": "unsafe"},
                _event(2, "worker.task.opened", "2026-07-25T00:00:00Z", task_id="task-a"),
                _event(3, "worker.runner.started", "bad", task_id="task-a"),
                _event(4, "worker.runner.completed", "also-bad"),
            ]
        )

        self.assertEqual(projection["event_count"], 4)
        self.assertEqual(projection["task_count"], 1)
        self.assertEqual(projection["model_turns"], 1)
        self.assertEqual(projection["stages"]["model_execution"]["sample_count"], 0)
        self.assertIsNone(projection["first_validation"]["pass_rate"])

    def test_revision_is_deterministic_and_changes_with_metrics(self):
        events = [
            _event(1, "worker.task.opened", "2026-07-25T00:00:00Z", task_id="task-a"),
            _event(2, "worker.runner.started", "2026-07-25T00:00:01Z", task_id="task-a"),
        ]
        first = build_throughput_projection(events)
        second = build_throughput_projection(list(events))
        changed = build_throughput_projection(
            events + [_event(3, "worker.repair.started", "2026-07-25T00:00:02Z")]
        )

        self.assertEqual(first["revision"], second["revision"])
        self.assertNotEqual(first["revision"], changed["revision"])

    def test_reopening_the_same_task_counts_as_a_retry(self):
        projection = build_throughput_projection(
            [
                _event(1, "worker.task.opened", "2026-07-25T00:00:00Z", task_id="task-a"),
                _event(2, "task.failed", "2026-07-25T00:00:01Z", task_id="task-a"),
                _event(3, "worker.task.opened", "2026-07-25T00:00:02Z", task_id="task-a"),
                _event(
                    4,
                    "worker.usage.updated",
                    "2026-07-25T00:00:03Z",
                    usage={"input": float("nan"), "output": float("inf")},
                    cost_usd=float("nan"),
                ),
            ]
        )

        self.assertEqual(projection["task_count"], 1)
        self.assertEqual(projection["retries"], 1)
        self.assertEqual(projection["tasks"][0]["retries"], 1)
        self.assertEqual(projection["usage"]["total_tokens"], 0)
        self.assertEqual(projection["usage"]["cost_usd"], 0.0)

    def test_repeated_usage_snapshots_count_only_the_increment(self):
        projection = build_throughput_projection(
            [
                _event(1, "worker.task.opened", "2026-07-25T00:00:00Z", task_id="task-a"),
                _event(
                    2,
                    "worker.usage.updated",
                    "2026-07-25T00:00:01Z",
                    task_id="task-a",
                    usage_id="message-1",
                    usage={"input": 100, "output": 10},
                ),
                _event(
                    3,
                    "worker.usage.updated",
                    "2026-07-25T00:00:02Z",
                    task_id="task-a",
                    usage_id="message-1",
                    usage={"input": 120, "output": 15},
                ),
            ]
        )

        self.assertEqual(projection["usage"]["input_tokens"], 120)
        self.assertEqual(projection["usage"]["output_tokens"], 15)
        self.assertEqual(projection["usage"]["total_tokens"], 135)

    def test_projection_does_not_expose_event_payload_text_paths_or_credentials(self):
        projection = build_throughput_projection(
            [
                _event(
                    1,
                    "worker.task.opened",
                    "2026-07-25T00:00:00Z",
                    task_id="task-a",
                    prompt="hidden instructions",
                    path="C:/private/work/project.yaml",
                    api_key="sk-redacted-not-for-output",
                )
            ]
        )
        serialized = repr(projection)

        self.assertNotIn("hidden instructions", serialized)
        self.assertNotIn("C:/private", serialized)
        self.assertNotIn("sk-redacted", serialized)


if __name__ == "__main__":
    unittest.main()
