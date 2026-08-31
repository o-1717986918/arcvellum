from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.runtime.role_conversation import RoleConversationGateway
from literary_engineering_studio.runtime.runtime_selection import (
    DEFAULT_CREATIVE_RUNTIME,
    runtime_for_role,
)
from literary_engineering_studio.runtimes.base import RuntimeResult


class _ConversationRuntime:
    def __init__(self) -> None:
        self.options: dict[str, object] = {}
        self.prompt = ""

    def execute(self, workspace, prompt_path, run_root, **options):
        self.options = options
        self.prompt = Path(prompt_path).read_text(encoding="utf-8")
        options["event_sink"]("agent.message.delta", {"text": "流式"})
        options["event_sink"]("agent.message.delta", {"text": "回答"})
        return RuntimeResult(
            runtime="pi-worker",
            status="completed",
            returncode=0,
            command=("pi-worker",),
            output_path=None,
            message="conversation completed",
            metadata={
                "worker_result": {
                    "taskId": "arcvellum-conversation-fixture",
                    "answer": "后备回答",
                }
            },
        )


class RoleConversationGatewayTests(unittest.TestCase):
    def test_roles_default_to_embedded_pi_worker(self):
        self.assertEqual(DEFAULT_CREATIVE_RUNTIME, "pi-worker")
        self.assertEqual(runtime_for_role({}, "advisor"), "pi-worker")
        self.assertEqual(
            runtime_for_role(
                {"agent_runtime_roles": {"advisor": "opencode"}}, "advisor"
            ),
            "opencode",
        )

    def test_tool_free_conversation_uses_one_turn_and_streams_answer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "snapshot"
            workspace.mkdir()
            runtime = _ConversationRuntime()
            config = {
                "agent_runtime_roles": {"advisor": "pi-worker"},
                "agent_runners": {
                    "pi-worker": {
                        "enabled": True,
                        "model": "fixture/model",
                        "thinking": "minimal",
                    }
                },
            }
            with patch(
                "literary_engineering_studio.runtime.role_conversation.build_runtime",
                return_value=runtime,
            ):
                result = RoleConversationGateway(config, data_root=root).run(
                    workspace,
                    "只读回答这个问题",
                    role="advisor",
                    timeout=30,
                )

        self.assertEqual(result.answer, "流式回答")
        self.assertEqual(result.run_id, "arcvellum-conversation-fixture")
        self.assertEqual(runtime.prompt, "只读回答这个问题")
        self.assertEqual(runtime.options["worker_mode"], "conversation")
        self.assertEqual(runtime.options["max_turns"], 1)
        self.assertEqual(runtime.options["max_tool_calls"], 1)
        self.assertEqual(runtime.options["max_repairs"], 0)

    def test_non_pi_role_is_rejected_before_starting_a_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "snapshot"
            workspace.mkdir()
            config = {
                "agent_runtime_roles": {"advisor": "opencode"},
                "agent_runners": {"pi-worker": {"model": "fixture/model"}},
            }
            with self.assertRaisesRegex(RuntimeError, "unsupported by runtime"):
                RoleConversationGateway(config, data_root=root).run(
                    workspace,
                    "question",
                    role="advisor",
                    timeout=30,
                )


if __name__ == "__main__":
    unittest.main()
