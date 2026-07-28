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

    def test_projects_bounded_repair_metrics_without_output_content(self):
        projection = build_throughput_projection(
            [
                _event(
                    1,
                    "worker.task.opened",
                    "2026-07-25T00:00:00Z",
                    task_id="task-a",
                ),
                _event(
                    2,
                    "worker.repair.started",
                    "2026-07-25T00:00:01Z",
                    repair_context_digest="a" * 64,
                    repair_prompt_characters=900,
                    repair_excerpt_characters=240,
                    repair_target_count=1,
                    repair_protected_count=2,
                    repair_write_scope_mode="targeted",
                    unsafe_excerpt="正文不得进入投影",
                ),
                _event(
                    3,
                    "worker.repair.output_guard.finalized",
                    "2026-07-25T00:00:02Z",
                    restored_output_count=1,
                    restored_outputs=["private/output.md"],
                ),
            ]
        )

        self.assertEqual(
            projection["repair_context"],
            {
                "prompt_characters": 900,
                "excerpt_characters": 240,
                "targeted_turns": 1,
                "fallback_turns": 0,
                "protected_outputs": 2,
                "restored_outputs": 1,
            },
        )
        self.assertTrue(
            projection["coverage"]["incremental_repair_context"]
        )
        self.assertEqual(
            projection["tasks"][0]["repair_context_digest"],
            "a" * 64,
        )
        self.assertNotIn(
            "正文不得进入投影",
            str(projection),
        )
        self.assertNotIn("private/output.md", str(projection))

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

    def test_attributes_usage_and_context_budget_without_exposing_context_text(self):
        projection = build_throughput_projection(
            [
                _event(
                    1,
                    "worker.task.opened",
                    "2026-07-25T00:00:00Z",
                    task_id="scene-review",
                    route="scene-development",
                    scene_id="scene_0004",
                    agent_role="main-review-agent",
                ),
                _event(
                    2,
                    "worker.sandbox.context_ready",
                    "2026-07-25T00:00:01Z",
                    task_id="scene-review",
                    context_ledger_digest="context-digest-4",
                    context_budget={
                        "mode": "shadow",
                        "requested_mode": "shadow",
                        "task_kind": "review",
                        "risk_level": "high",
                        "contract_status": "bounded-ready",
                        "rollout_reason": "rollout-disabled",
                        "rollout_policy_digest": "c" * 64,
                        "target_inline_characters": 126500,
                        "enforced_inline_characters": 180000,
                        "first_turn_visible_characters": 140000,
                        "exact_on_demand_characters": 24000,
                        "excluded_characters": 0,
                        "authorized_characters": 164000,
                        "mandatory_characters": 18000,
                        "included_file_count": 8,
                        "on_demand_file_count": 2,
                        "excluded_file_count": 0,
                        "budget_overage_count": 1,
                        "budget_overage_characters": 13500,
                        "digest": "budget-digest-4",
                    },
                ),
                _event(
                    3,
                    "worker.usage.updated",
                    "2026-07-25T00:00:02Z",
                    task_id="scene-review",
                    role="reviewer",
                    provider="zhipuai",
                    model="glm-5",
                    context_ledger_digest="context-digest-4",
                    usage={"input": 1200, "output": 300, "cache": {"read": 900}},
                ),
            ]
        )

        self.assertEqual(projection["usage"]["non_cached_input_tokens"], 1200)
        self.assertEqual(projection["context"]["reported_tasks"], 1)
        self.assertEqual(projection["context"]["budget_overage_count"], 1)
        self.assertTrue(projection["coverage"]["scene_attribution"])
        self.assertTrue(projection["coverage"]["context_budget"])
        context = projection["tasks"][0]["context"]
        self.assertEqual(context["requested_mode"], "shadow")
        self.assertEqual(context["contract_status"], "bounded-ready")
        self.assertEqual(context["rollout_reason"], "rollout-disabled")
        self.assertEqual(context["rollout_policy_digest"], "c" * 64)
        task = projection["tasks"][0]
        self.assertEqual(task["scene_id"], "scene_0004")
        self.assertEqual(task["role"], "main-review-agent")
        self.assertEqual(task["runtime_role"], "reviewer")
        self.assertEqual(task["model_identity"], "zhipuai/glm-5")
        self.assertEqual(task["context_digest"], "context-digest-4")
        self.assertEqual(projection["attribution"]["by_scene"][0]["key"], "scene_0004")
        self.assertEqual(
            projection["attribution"]["by_runtime_role"][0]["key"],
            "reviewer",
        )
        self.assertEqual(
            projection["attribution"]["by_model"][0]["usage"]["cache_read_tokens"],
            900,
        )
        self.assertNotIn("context text", repr(projection))

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
