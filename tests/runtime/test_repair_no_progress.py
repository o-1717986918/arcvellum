from __future__ import annotations

import unittest

from literary_engineering_studio.preflight.common import PreflightIssue, PreflightResult
from literary_engineering_studio.runtimes.opencode_repair import (
    RepairLoopEnvironment,
    run_preflight_repair_loop,
)


class _Client:
    def __init__(self):
        self.prompt_calls = 0

    def prompt_async(self, *_args, **_kwargs):
        self.prompt_calls += 1


class RepairNoProgressTests(unittest.TestCase):
    def test_identical_progress_stops_before_repeating_repair(self):
        client = _Client()
        events: list[str] = []
        preflight = PreflightResult(
            False,
            (PreflightIssue("missing-output", "result.json", "missing", "create"),),
        )
        environment = RepairLoopEnvironment(
            client=client,
            session_id="session-1",
            model="test/model",
            agent_id="test-agent",
            timeout=300,
            cancellation=object(),
            settings={},
            emit=lambda name, _data: events.append(name),
            mark_activity=lambda: None,
            last_activity=lambda: 0.0,
            wait_for_session=lambda *_args, **_kwargs: "completed",
            prompt_builder=None,
            turn_finalizer=None,
            progress_digest_builder=lambda _preflight, _access: {
                "progress_digest": "same",
                "issue_ids": ["missing-output:result.json"],
            },
            context_access_supplier=lambda: {"read_tool_calls": 0},
        )

        result = run_preflight_repair_loop(
            environment,
            output_validator=lambda: preflight,
            max_repairs=2,
        )

        self.assertEqual(result.status, "no_progress")
        self.assertEqual(result.repairs, 1)
        self.assertEqual(client.prompt_calls, 1)
        self.assertIn("repair.no_progress", events)


if __name__ == "__main__":
    unittest.main()
