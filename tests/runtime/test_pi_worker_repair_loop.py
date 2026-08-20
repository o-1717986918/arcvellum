from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from literary_engineering_studio.preflight.common import PreflightIssue, PreflightResult
from literary_engineering_studio.runtimes.base import RuntimeResult
from literary_engineering_studio.runtimes.pi_worker_repair import run_pi_worker_repairs


class PiWorkerRepairLoopTests(unittest.TestCase):
    def test_one_identical_preflight_gets_an_informed_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calls = 0
            events: list[tuple[str, dict[str, object]]] = []

            def validate():
                nonlocal calls
                passed = calls >= 2
                return PreflightResult(
                    passed,
                    () if passed else (
                        PreflightIssue("style", "result.md", "still unchanged", "rewrite"),
                    ),
                )

            def run_turn(*_args):
                nonlocal calls
                calls += 1
                return RuntimeResult("pi-worker", "completed", 0, (), None, "ready")

            result = run_pi_worker_repairs(
                RuntimeResult("pi-worker", "completed", 0, (), None, "ready"),
                run_root=root,
                output_validator=validate,
                max_repairs=3,
                repair_prompt_builder=lambda _result, attempt, maximum: SimpleNamespace(
                    prompt=f"repair {attempt}/{maximum}",
                    repair_targets=("result.md",),
                    reasoning_level="minimal",
                    event_fields=lambda: {},
                ),
                repair_turn_finalizer=lambda: {},
                run_turn=run_turn,
                emit=lambda event, data: events.append((event, data)),
            )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.metadata["repair_attempts"], 2)
        self.assertEqual(calls, 2)
        stalled = [data for event, data in events if event == "repair.no_progress"]
        self.assertEqual(len(stalled), 1)
        self.assertTrue(stalled[0]["retry_scheduled"])

    def test_two_identical_preflights_stop_the_loop(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calls = 0

            def run_turn(*_args):
                nonlocal calls
                calls += 1
                return RuntimeResult("pi-worker", "completed", 0, (), None, "ready")

            failed = PreflightResult(
                False,
                (PreflightIssue("style", "result.md", "unchanged", "rewrite"),),
            )
            result = run_pi_worker_repairs(
                RuntimeResult("pi-worker", "completed", 0, (), None, "ready"),
                run_root=root,
                output_validator=lambda: failed,
                max_repairs=4,
                repair_prompt_builder=lambda _result, attempt, maximum: SimpleNamespace(
                    prompt=f"repair {attempt}/{maximum}",
                    repair_targets=("result.md",),
                    reasoning_level="minimal",
                    event_fields=lambda: {},
                ),
                repair_turn_finalizer=lambda: {},
                run_turn=run_turn,
                emit=lambda _event, _data: None,
            )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.metadata["failure_kind"], "no_progress")
        self.assertEqual(result.metadata["repair_attempts"], 2)
        self.assertEqual(calls, 2)


if __name__ == "__main__":
    unittest.main()
