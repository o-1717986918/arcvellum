from __future__ import annotations

import unittest

from literary_engineering_studio.runtimes import RUNTIME_TYPES
from literary_engineering_studio.runtimes.base import AgentRunnerCapabilities
from literary_engineering_studio.runtimes.base import RuntimeAvailability


class RuntimeCapabilityContractTests(unittest.TestCase):
    def test_versioned_projection_preserves_legacy_fields(self):
        capabilities = AgentRunnerCapabilities(
            runner_id="fixture",
            version="1.2.3",
            available=True,
            readiness_state="ready",
            authentication_state="authenticated",
            provider="fixture",
            selected_model="fixture-model",
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
            detail="ready",
            context_window=128_000,
            capability_ids=("project.query", "schema.inspect"),
        )
        payload = capabilities.as_dict()
        self.assertEqual(payload["protocol_version"], "arcvellum/agent-runner-capabilities/v1")
        self.assertEqual(payload["context_window"], 128_000)
        self.assertTrue(payload["tool_calls"])
        self.assertTrue(payload["cancellation"])
        self.assertTrue(payload["local_execution"])
        self.assertEqual(payload["capability_ids"], ["project.query", "schema.inspect"])
        self.assertTrue(payload["read_control"])
        self.assertTrue(payload["stop"])

    def test_host_projection_is_not_misreported_as_local(self):
        capabilities = AgentRunnerCapabilities(
            runner_id="host-agent",
            version="host",
            available=True,
            readiness_state="ready",
            authentication_state="host-owned",
            provider="host",
            selected_model="host",
            execution_modes=("handoff",),
            structured_output=True,
            streaming_events=False,
            model_selection=False,
            read_control=False,
            edit_control=False,
            shell_control=False,
            subagent_control=False,
            web_control=False,
            external_directory_control=False,
            stop=False,
            retry=True,
            resume=False,
            detail="ready",
        )
        payload = capabilities.as_dict()
        self.assertFalse(payload["tool_calls"])
        self.assertFalse(payload["cancellation"])
        self.assertFalse(payload["local_execution"])

    def test_every_registered_runner_projects_the_same_versioned_contract(self):
        for runtime_id, runtime_type in RUNTIME_TYPES.items():
            with self.subTest(runtime_id=runtime_id):
                runtime = runtime_type({})
                payload = runtime.capabilities(
                    RuntimeAvailability(runtime_id, False, "", "contract-only probe")
                ).as_dict()
                self.assertEqual(payload["protocol_version"], "arcvellum/agent-runner-capabilities/v1")
                self.assertIsInstance(payload["capability_ids"], list)
                self.assertIn("tool_calls", payload)
                self.assertIn("cancellation", payload)
                self.assertIn("local_execution", payload)
                self.assertIn("read_control", payload)

    def test_opencode_declares_only_the_execution_controls_it_can_enforce(self):
        runtime_type = RUNTIME_TYPES["opencode"]
        runtime = runtime_type({})
        capabilities = set(runtime.execution_control_capabilities())
        self.assertEqual(capabilities, {"bounded-repair", "silence-timeout-control"})
        self.assertNotIn("reasoning-policy-control", capabilities)
        self.assertNotIn("turn-limit-control", capabilities)
        self.assertNotIn("tool-limit-control", capabilities)


if __name__ == "__main__":
    unittest.main()
