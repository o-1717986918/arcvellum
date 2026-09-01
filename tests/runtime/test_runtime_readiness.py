from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from literary_engineering_studio.runtime.readiness import (
    require_runtime_ready,
    runtime_readiness_error,
)
from literary_engineering_studio.automation.support import (
    _validate_autopilot_runtime,
)


class RuntimeReadinessTests(unittest.TestCase):
    def test_partial_embedding_config_defers_to_worker(self):
        self.assertEqual(runtime_readiness_error({}, "pi-worker"), "")

    def test_missing_model_has_actionable_message(self):
        runtime = MagicMock()
        availability = MagicMock(available=True, detail="embedded")
        runtime.availability.return_value = availability
        runtime.capabilities.return_value = MagicMock(
            available=False,
            readiness_state="model-selection-required",
            detail="embedded",
        )
        config = {"agent_runners": {"pi-worker": {"enabled": True}}}

        with patch(
            "literary_engineering_studio.runtime.readiness.build_runtime",
            return_value=runtime,
        ):
            error = runtime_readiness_error(config, "pi-worker", role="worker")
            with self.assertRaisesRegex(ValueError, "连接与模型"):
                require_runtime_ready(config, "pi-worker", role="worker")

        self.assertIn("正文与项目任务", error)
        self.assertIn("选择模型", error)

    def test_ready_runtime_passes(self):
        runtime = MagicMock()
        availability = MagicMock(available=True, detail="embedded")
        runtime.availability.return_value = availability
        runtime.capabilities.return_value = MagicMock(
            available=True,
            readiness_state="ready",
            detail="embedded",
        )
        config = {"agent_runners": {"pi-worker": {"enabled": True}}}

        with patch(
            "literary_engineering_studio.runtime.readiness.build_runtime",
            return_value=runtime,
        ):
            require_runtime_ready(config, "pi-worker", role="worker")

    def test_full_auto_checks_worker_and_steward_roles(self):
        config = {
            "agent_runtime_roles": {"steward": "pi-worker"},
            "agent_runners": {"pi-worker": {"enabled": True}},
        }

        with patch(
            "literary_engineering_studio.automation.support.require_runtime_ready"
        ) as require:
            _validate_autopilot_runtime(config, "pi-worker", mode="full_auto")

        self.assertEqual(
            require.call_args_list,
            [
                unittest.mock.call(config, "pi-worker", role="worker"),
                unittest.mock.call(config, "pi-worker", role="steward"),
            ],
        )

    def test_supervised_mode_checks_only_worker_role(self):
        config = {
            "agent_runtime_roles": {"steward": "pi-worker"},
            "agent_runners": {"pi-worker": {"enabled": True}},
        }

        with patch(
            "literary_engineering_studio.automation.support.require_runtime_ready"
        ) as require:
            _validate_autopilot_runtime(config, "pi-worker", mode="supervised_auto")

        require.assert_called_once_with(config, "pi-worker", role="worker")


if __name__ == "__main__":
    unittest.main()
