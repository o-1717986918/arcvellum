from __future__ import annotations

import unittest

from literary_engineering_studio.project_agent import (
    PROJECT_AGENT_BRIDGE_SCHEMA,
    BridgeEnvelope,
    BridgeMessageType,
    ProjectAgentToolCall,
    ProjectAgentTurnRequest,
)


class ProjectAgentContractTests(unittest.TestCase):
    def test_versioned_envelope_roundtrips(self):
        request = ProjectAgentTurnRequest(
            session_id="session-1",
            turn_id="turn-1",
            prompt="项目进行到哪里？",
            system_prompt="根据工具事实自然回答。",
        )
        encoded = request.start_envelope("message-1").to_json_line()
        decoded = BridgeEnvelope.from_json_line(encoded)

        self.assertEqual(decoded.schema, PROJECT_AGENT_BRIDGE_SCHEMA)
        self.assertEqual(decoded.type, BridgeMessageType.TURN_START)
        self.assertEqual(decoded.payload["allowed_tools"], ["project_overview"])
        self.assertNotIn("max_turns", decoded.payload)
        self.assertNotIn("max_tool_calls", decoded.payload)

    def test_unknown_schema_and_message_type_fail_closed(self):
        valid = {
            "schema": PROJECT_AGENT_BRIDGE_SCHEMA,
            "type": "tool.call",
            "message_id": "message-1",
            "turn_id": "turn-1",
            "payload": {"request_id": "request-1", "name": "project_overview", "arguments": {}},
        }
        with self.assertRaisesRegex(ValueError, "unsupported Project Agent bridge schema"):
            BridgeEnvelope.from_dict({**valid, "schema": "legacy"})
        with self.assertRaisesRegex(ValueError, "unsupported bridge message type"):
            BridgeEnvelope.from_dict({**valid, "type": "shell.exec"})

    def test_tool_call_requires_typed_identity_and_object_arguments(self):
        envelope = BridgeEnvelope(
            type=BridgeMessageType.TOOL_CALL,
            message_id="message-1",
            turn_id="turn-1",
            payload={"request_id": "request-1", "name": "project_overview", "arguments": {"focus": "progress"}},
        )
        call = ProjectAgentToolCall.from_envelope(envelope)
        self.assertEqual(call.name, "project_overview")
        self.assertEqual(call.arguments, {"focus": "progress"})


if __name__ == "__main__":
    unittest.main()
