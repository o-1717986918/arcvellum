from __future__ import annotations

import json
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

    def test_character_actor_rejects_legacy_single_prompt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            gateway = RoleConversationGateway({}, data_root=root)
            with self.assertRaisesRegex(ValueError, "initialized conversation"):
                gateway.run(root, "旧角色整包提示", role="character-actor", timeout=30)

    def test_environment_initialization_uses_two_turns_and_returns_only_scene_answer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = _ConversationRuntime()
            config = {"agent_runners": {"pi-worker": {"model": "fixture/model"}}}
            prompt = json.dumps({"schema": "arcvellum/environment-conversation/v1",
                                 "initialization": "【SCENE_LOAD】\nSCENE_CLAIM_LANDSCAPE_DESCRIBER",
                                 "prompt": "# Independent Environment Writing\n写本场环境。"}, ensure_ascii=False)
            with patch("literary_engineering_studio.runtime.role_conversation.build_runtime", return_value=runtime):
                result = RoleConversationGateway(config, data_root=root).run(
                    root, prompt, role="environment-writer", timeout=30,
                )
        self.assertEqual(runtime.options["max_turns"], 2)
        self.assertEqual(runtime.options["conversation_role"], "environment-writer")
        self.assertEqual(result.answer, "后备回答")
        self.assertEqual(json.loads(runtime.prompt)["initialization"], "【SCENE_LOAD】\nSCENE_CLAIM_LANDSCAPE_DESCRIBER")

    def test_character_sequence_accepts_followups_and_returns_only_latest_answer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = _ConversationRuntime()
            config = {"agent_runners": {"pi-worker": {"model": "fixture/model", "thinking": "high"}}}
            with patch("literary_engineering_studio.runtime.role_conversation.build_runtime", return_value=runtime):
                result = RoleConversationGateway(config, data_root=root).run_sequence(
                    root, ("你是甲。\n\n【角色沉浸要求】", "# 本场角色任务单", "# 角色后续追问"),
                    role="character-actor", timeout=30,
                )
        self.assertEqual(result.answer, "后备回答")
        self.assertEqual(runtime.options["max_turns"], 3)
        self.assertEqual(runtime.options["conversation_role"], "character-actor")
        self.assertEqual(json.loads(runtime.prompt), {
            "schema": "arcvellum/actor-conversation/v1",
            "messages": ["你是甲。\n\n【角色沉浸要求】", "# 本场角色任务单", "# 角色后续追问"],
        })

    def test_actor_turn_serializes_prior_answers_without_rerunning_them(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = _ConversationRuntime()
            config = {"agent_runners": {"pi-worker": {"model": "fixture/model", "thinking": "high"}}}
            with patch("literary_engineering_studio.runtime.role_conversation.build_runtime", return_value=runtime):
                result = RoleConversationGateway(config, data_root=root).run_actor_turn(
                    root, initialization="【PERSONA_LOAD】\nSELF_CLAIM_LIN",
                    initialization_answer="", history=(("第一轮", "我等你。"),),
                    prompt="第二轮", timeout=30,
                )
        self.assertEqual(result.answer, "后备回答")
        self.assertEqual(runtime.options["max_turns"], 1)
        self.assertEqual(json.loads(runtime.prompt)["history"], [{"prompt": "第一轮", "answer": "我等你。"}])


if __name__ == "__main__":
    unittest.main()
