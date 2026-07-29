from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.config import default_config
from literary_engineering_studio.runtimes import build_runtime
from literary_engineering_studio.runtimes.opencode import (
    OpenCodeRuntime,
    _is_transient_stream_failure,
)
from literary_engineering_studio.task_preflight import PreflightIssue, PreflightResult


class _Client:
    def __init__(self):
        self.prompts = []
        self.status_reads = 0
        self.aborted = False

    def health(self):
        return {"version": "fixture"}

    def create_session(self, _title):
        return {"id": "session-fixed"}

    def events(self, _stop):
        return iter(())

    def prompt_async(self, session_id, *, text, model, agent):
        self.prompts.append({"session_id": session_id, "text": text, "model": model, "agent": agent})
        self.status_reads = 0

    def session_status(self):
        self.status_reads += 1
        return {"session-fixed": {"type": "busy" if self.status_reads == 1 else "idle"}}

    def messages(self, _session_id):
        return [{"info": {"role": "assistant"}, "parts": [{"type": "text", "text": "修复完成"}]}]

    def diff(self, _session_id):
        return []

    def abort(self, _session_id):
        self.aborted = True


class _Pool:
    def __init__(self, client):
        self.client = client
        self.acquires = 0
        self.roles = []
        self.releases = 0

    def acquire(self, role, workspace, *, model):
        self.acquires += 1
        self.roles.append(role)
        return SimpleNamespace(
            role=role,
            client=self.client,
            component_id="opencode-worker",
            generation=3,
            reused=True,
        )

    def release(self, _lease):
        self.releases += 1


class _RepairingValidator:
    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.calls == 1:
            return PreflightResult(
                False,
                (PreflightIssue("invalid-json", "output.json", "JSON 无法解析。", "修正 JSON。"),),
            )
        return PreflightResult(True, ())


class _StreamingFailureClient(_Client):
    def messages(self, _session_id):
        return [
            {
                "info": {
                    "role": "assistant",
                    "error": {"name": "UnknownError", "data": {"message": '"Streaming response failed"'}},
                },
                "parts": [],
            }
        ]


class _PreparedRepair:
    prompt = "# Bounded Repair"

    @staticmethod
    def event_fields():
        return {
            "repair_context_digest": "a" * 64,
            "repair_prompt_characters": len(_PreparedRepair.prompt),
        }


class OpenCodeRuntimeExecutionTests(unittest.TestCase):
    def test_provider_aborted_message_is_retryable(self):
        self.assertTrue(
            _is_transient_stream_failure(
                '{"name":"MessageAbortedError","data":{"message":"Aborted"}}'
            )
        )

    def test_runtime_builder_applies_role_without_mutating_persisted_settings(self):
        config = default_config()
        runtime = build_runtime("opencode", config, role="reviewer")
        self.assertIsInstance(runtime, OpenCodeRuntime)
        self.assertEqual(runtime.settings["role"], "reviewer")
        self.assertNotIn("role", config["agent_runners"]["opencode"])

    def test_failed_preflight_is_repaired_in_the_same_session(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            run_root = root / "run"
            workspace.mkdir()
            run_root.mkdir()
            prompt = root / "prompt.md"
            prompt.write_text("执行正式任务", encoding="utf-8")
            client = _Client()
            pool = _Pool(client)
            validator = _RepairingValidator()
            events = []
            runtime = OpenCodeRuntime({"model": "fixture/model", "models": {"worker": "fixture/model"}})
            runtime.runtime_pool = pool

            with patch(
                "literary_engineering_studio.runtimes.opencode.locate_opencode",
                return_value=Path("opencode.exe"),
            ):
                result = runtime.execute(
                    workspace,
                    prompt,
                    run_root,
                    timeout=10,
                    event_sink=lambda event, data: events.append((event, data)),
                    output_validator=validator,
                    max_repairs=2,
                )

            self.assertEqual(result.status, "completed")
            self.assertEqual(pool.acquires, 1)
            self.assertEqual(pool.releases, 1)
            self.assertEqual(validator.calls, 2)
            self.assertEqual(len(client.prompts), 2)
            self.assertEqual({item["session_id"] for item in client.prompts}, {"session-fixed"})
            self.assertIn("Studio Preflight Repair 1/2", client.prompts[1]["text"])
            self.assertEqual(result.metadata["repairs"], 1)
            self.assertTrue(result.metadata["service_reused"])
            self.assertFalse(client.aborted)
            finished = [data for event, data in events if event == "runner.session.finished"]
            self.assertEqual(finished[-1]["session_id"], "session-fixed")
            self.assertEqual(finished[-1]["status"], "complete")

    def test_bounded_repair_callbacks_keep_session_and_finalize_guard(
        self,
    ):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            run_root = root / "run"
            workspace.mkdir()
            run_root.mkdir()
            prompt = root / "prompt.md"
            prompt.write_text("执行正式任务", encoding="utf-8")
            client = _Client()
            pool = _Pool(client)
            validator = _RepairingValidator()
            built = []
            finalized = []
            events = []
            runtime = OpenCodeRuntime(
                {
                    "model": "fixture/model",
                    "models": {"worker": "fixture/model"},
                }
            )
            runtime.runtime_pool = pool

            def build_repair(result, attempt, maximum):
                built.append((result, attempt, maximum))
                return _PreparedRepair()

            def finalize_repair():
                finalized.append(True)
                return {
                    "repair_context_digest": "a" * 64,
                    "protected_output_count": 1,
                    "restored_output_count": 1,
                    "restored_outputs": ["passed.md"],
                }

            with patch(
                "literary_engineering_studio.runtimes.opencode.locate_opencode",
                return_value=Path("opencode.exe"),
            ):
                result = runtime.execute(
                    workspace,
                    prompt,
                    run_root,
                    timeout=10,
                    event_sink=lambda event, data: events.append(
                        (event, data)
                    ),
                    output_validator=validator,
                    max_repairs=2,
                    repair_prompt_builder=build_repair,
                    repair_turn_finalizer=finalize_repair,
                )

            self.assertEqual(result.status, "completed")
            self.assertEqual(len(built), 1)
            self.assertEqual(finalized, [True])
            self.assertEqual(client.prompts[1]["text"], "# Bounded Repair")
            self.assertEqual(
                {item["session_id"] for item in client.prompts},
                {"session-fixed"},
            )
            started = [
                data for event, data in events if event == "repair.started"
            ]
            self.assertEqual(
                started[0]["repair_context_digest"],
                "a" * 64,
            )
            guarded = [
                data
                for event, data in events
                if event == "repair.output_guard.finalized"
            ]
            self.assertEqual(guarded[0]["restored_output_count"], 1)

    def test_repair_timeout_still_finalizes_output_guard(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            run_root = root / "run"
            workspace.mkdir()
            run_root.mkdir()
            prompt = root / "prompt.md"
            prompt.write_text("执行正式任务", encoding="utf-8")
            client = _Client()
            pool = _Pool(client)
            validator = _RepairingValidator()
            finalized = []
            runtime = OpenCodeRuntime(
                {
                    "model": "fixture/model",
                    "models": {"worker": "fixture/model"},
                }
            )
            runtime.runtime_pool = pool

            def finalize_repair():
                finalized.append(True)
                return {
                    "repair_context_digest": "b" * 64,
                    "protected_output_count": 1,
                    "restored_output_count": 0,
                    "restored_outputs": [],
                }

            with (
                patch(
                    "literary_engineering_studio.runtimes.opencode.locate_opencode",
                    return_value=Path("opencode.exe"),
                ),
                patch(
                    "literary_engineering_studio.runtimes.opencode._wait_for_session",
                    side_effect=["completed", "timeout"],
                ),
            ):
                result = runtime.execute(
                    workspace,
                    prompt,
                    run_root,
                    timeout=10,
                    output_validator=validator,
                    max_repairs=1,
                    repair_prompt_builder=(
                        lambda _result, _attempt, _maximum: _PreparedRepair()
                    ),
                    repair_turn_finalizer=finalize_repair,
                )

            self.assertEqual(result.status, "timeout")
            self.assertEqual(finalized, [True])
            self.assertTrue(client.aborted)

    def test_streaming_failure_is_presented_as_retryable_user_safe_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            run_root = root / "run"
            workspace.mkdir()
            run_root.mkdir()
            prompt = root / "prompt.md"
            prompt.write_text("执行正式任务", encoding="utf-8")
            client = _StreamingFailureClient()
            pool = _Pool(client)
            events = []
            runtime = OpenCodeRuntime({"model": "fixture/model", "models": {"worker": "fixture/model"}})
            runtime.runtime_pool = pool

            with patch(
                "literary_engineering_studio.runtimes.opencode.locate_opencode",
                return_value=Path("opencode.exe"),
            ):
                result = runtime.execute(
                    workspace,
                    prompt,
                    run_root,
                    timeout=10,
                    event_sink=lambda event, data: events.append((event, data)),
                )

            self.assertEqual(result.status, "failed")
            self.assertTrue(result.metadata["retryable"])
            self.assertIn("自动重试", result.message)
            finished = [data for event, data in events if event == "runner.session.finished"]
            self.assertEqual(finished[-1]["reason"], "streaming_interrupted")

    def test_planner_role_uses_an_isolated_profile_and_worker_model_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            run_root = root / "run"
            workspace.mkdir()
            run_root.mkdir()
            prompt = root / "prompt.md"
            prompt.write_text("生成计划候选 JSON", encoding="utf-8")
            client = _Client()
            pool = _Pool(client)
            runtime = OpenCodeRuntime(
                {
                    "role": "planner",
                    "model": "fixture/default",
                    "models": {"worker": "fixture/worker"},
                }
            )
            runtime.runtime_pool = pool

            with patch(
                "literary_engineering_studio.runtimes.opencode.locate_opencode",
                return_value=Path("opencode.exe"),
            ):
                result = runtime.execute(workspace, prompt, run_root, timeout=10)

            self.assertEqual(result.status, "completed")
            self.assertEqual(client.prompts[0]["agent"], "orchestration-planner")
            self.assertEqual(client.prompts[0]["model"], "fixture/worker")
            self.assertEqual(pool.roles, ["planner"])
            self.assertEqual(result.metadata["role"], "planner")


if __name__ == "__main__":
    unittest.main()
