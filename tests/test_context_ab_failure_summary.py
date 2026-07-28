from pathlib import Path
import unittest

from literary_engineering_studio.runtime.context_ab_reporting import (
    build_arm_report,
)
from literary_engineering_studio.runtime.worker_results import WorkerRunResult


class _Task:
    expected_outputs: tuple[str, ...] = ()
    payload: dict[str, object] = {}
    project_root = Path(".")


class ContextABFailureSummaryTests(unittest.TestCase):
    def test_runtime_failure_keeps_only_safe_category(self) -> None:
        result = WorkerRunResult(
            status="runtime_failed",
            project_root=Path("."),
            route="scene-development",
            task_id="task-1",
            runtime="opencode",
            run_root=None,
            workspace=None,
            message="secret-bearing provider response",
        )
        report = build_arm_report(
            "bounded",
            result,
            1.0,
            {},
            _Task(),
            {
                "runtime_metadata": {
                    "retryable": True,
                    "diagnostic_error": "must not escape",
                }
            },
        )

        self.assertEqual(
            report["failure"],
            {
                "present": True,
                "category": "streaming_interrupted",
                "retryable": True,
            },
        )
        self.assertNotIn("secret-bearing", str(report))
        self.assertNotIn("must not escape", str(report))


if __name__ == "__main__":
    unittest.main()
