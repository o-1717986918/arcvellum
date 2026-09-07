from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.application.config import default_config
from literary_engineering_studio.integrations.runner_probe import (
    probe_agent_runner,
)
from literary_engineering_studio.runtimes.base import (
    AgentRunnerCapabilities,
    RuntimeResult,
)


class _RuntimeWithoutOutput:
    def __init__(self):
        self.worker_mode = "unset"

    def capabilities(self):
        return AgentRunnerCapabilities(
            runner_id="pi-worker",
            version="fixture",
            available=True,
            readiness_state="ready",
            authentication_state="runner-managed",
            provider="fixture",
            selected_model="fixture/model",
            execution_modes=("single-task",),
            structured_output=True,
            streaming_events=True,
            model_selection=True,
            read_control=True,
            edit_control=True,
            shell_control=False,
            subagent_control=False,
            web_control=False,
            external_directory_control=False,
            stop=True,
            retry=True,
            resume=False,
            detail="fixture",
        )

    def execute(self, _workspace, _prompt, run_root, **_kwargs):
        self.worker_mode = _kwargs.get("worker_mode")
        return RuntimeResult(
            runtime="pi-worker",
            status="timeout",
            returncode=None,
            command=(),
            output_path=Path(run_root) / "runtime.output.log",
            message="timed out before output",
        )


class RunnerProbeTests(unittest.TestCase):
    def test_missing_runtime_output_preserves_original_failure(self):
        runtime = _RuntimeWithoutOutput()
        with tempfile.TemporaryDirectory():
            with patch(
                "literary_engineering_studio.integrations.runner_probe.build_runtime",
                return_value=runtime,
            ):
                result = probe_agent_runner(
                    default_config(),
                    "pi-worker",
                    timeout=10,
                )

        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["message"], "timed out before output")
        self.assertEqual(result["diagnostic_output_tail"], "")
        self.assertEqual(runtime.worker_mode, "conversation")


if __name__ == "__main__":
    unittest.main()
