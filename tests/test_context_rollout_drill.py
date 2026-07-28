from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.runtime.context_rollout_drill import (
    CONTEXT_ROLLBACK_DRILL_SCHEMA,
    run_context_rollout_rollback_drill,
)


class ContextRolloutDrillTests(unittest.TestCase):
    def test_canary_rolls_back_without_mutating_task_contracts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ready = _task(
                root,
                "candidate-review",
                "bounded-ready",
            )
            shadow = _task(
                root,
                "candidate-revision",
                "shadow-ready",
            )

            report = run_context_rollout_rollback_drill(
                [ready, shadow],
                canary_config={
                    "mode": "shadow",
                    "bounded_rollout": {
                        "enabled": True,
                        "routes": ["scene-development"],
                        "states": ["candidate-review"],
                        "contract_statuses": ["bounded-ready"],
                    },
                },
            )

            self.assertEqual(
                report["schema"],
                CONTEXT_ROLLBACK_DRILL_SCHEMA,
            )
            self.assertTrue(report["passed"])
            self.assertEqual(
                [item["effective_mode"] for item in report["canary"]],
                ["bounded", "shadow"],
            )
            self.assertEqual(
                [item["effective_mode"] for item in report["rollback"]],
                ["shadow", "shadow"],
            )


def _task(
    root: Path,
    state: str,
    contract_status: str,
) -> TaskPackage:
    payload = {
        "task_id": f"scene-{state}",
        "route": "scene-development",
        "current_state": state,
        "task_type": "platform-agent-review",
        "context_contract_status": contract_status,
    }
    return TaskPackage(
        project_root=root,
        task_json_path=root / f"{state}.json",
        task_markdown_path=root / f"{state}.md",
        payload=payload,
    )


if __name__ == "__main__":
    unittest.main()
