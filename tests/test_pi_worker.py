from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import textwrap
from types import SimpleNamespace
import unittest

from literary_engineering_studio.preflight.common import PreflightIssue, PreflightResult
from literary_engineering_studio.runtimes.pi_worker import PiWorkerRuntime
from literary_engineering_studio.runtimes.base import RuntimeResult


FIXTURE_WORKER = r'''\
import json
from pathlib import Path
import sys

if "--version" in sys.argv:
    print("arcvellum-pi-worker fixture")
    raise SystemExit(0)

def option(name):
    index = sys.argv.index(name)
    return sys.argv[index + 1]

workspace = Path(option("--workspace"))
prompt = sys.stdin.read()
(workspace / "result.md").write_text(
    "repaired output" if "Studio Incremental Repair" in prompt else "fixture output",
    encoding="utf-8",
)
(workspace / "worker_args.json").write_text(
    json.dumps({"args": sys.argv[1:], "prompt": prompt}), encoding="utf-8"
)
events = [
    ("runner.ready", {"runner_id": "pi-worker"}),
    ("runner.session.created", {"session_id": "fixture", "ephemeral": True}),
    ("runner.reasoning.started", {"session_id": "fixture"}),
    ("runner.reasoning.activity", {"delta_events": 12, "delta_characters": 420}),
    ("tool.started", {"tool": "write_expected_output", "tool_use_id": "one"}),
    ("tool.completed", {"tool": "write_expected_output", "tool_use_id": "one"}),
    ("agent.message.delta", {"text": "done"}),
    ("usage.updated", {"usage": {"input": 10, "output": 3}, "cost_usd": 0.01}),
    (
        "runner.worker.result",
        {
            "status": "incomplete" if "incomplete" in prompt else "completed",
            "message": "model stopped without calling complete_task" if "incomplete" in prompt else "ready",
            "validationPassed": "incomplete" not in prompt,
            "reasoning_budget": (
                {
                    "requested": {
                        "initial_level": option("--thinking"),
                        "maximum_level": option("--max-thinking-level"),
                        "per_request_tokens": int(option("--reasoning-per-request")),
                        "total_tokens": int(option("--reasoning-total")),
                        "max_provider_requests": int(option("--max-provider-requests")),
                        "max_escalations": int(option("--max-reasoning-escalations")),
                        "over_budget_action": "validate_then_stop",
                    },
                    "provider_support": "partial",
                    "effective_level": "off",
                    "actual_tokens": 3,
                    "actual_characters": 420,
                    "provider_requests": 1,
                    "escalations": [],
                    "stop_reason": "",
                }
                if "--reasoning-total" in sys.argv
                else {}
            ),
        },
    ),
]
for event, data in events:
    print(json.dumps({"event": event, "data": data}), flush=True)
if "incomplete" in prompt:
    raise SystemExit(2)
'''


class PiWorkerRuntimeTests(unittest.TestCase):
    def _fixture(self, root: Path) -> Path:
        target = root / "fixture_worker.py"
        target.write_text(textwrap.dedent(FIXTURE_WORKER), encoding="utf-8")
        return target

    def test_build_command_projects_narrow_worker_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            entrypoint = self._fixture(root)
            workspace = root / "workspace"
            workspace.mkdir()
            runtime = PiWorkerRuntime(
                {
                    "executable": sys.executable,
                    "entrypoint": str(entrypoint),
                    "model": "fixture/model",
                    "auth_path": str(root / "auth.json"),
                    "thinking": "minimal",
                    "max_turns": 4,
                    "max_tool_calls": 7,
                    "max_repair_attempts": 1,
                    "allowed_states": ["candidate-review"],
                }
            )

            command = list(runtime.build_command(workspace))

        self.assertIn("--workspace", command)
        self.assertIn("fixture/model", command)
        self.assertEqual(command[command.index("--thinking") + 1], "minimal")
        self.assertEqual(command[command.index("--max-turns") + 1], "4")
        self.assertEqual(command[command.index("--max-tools") + 1], "7")
        self.assertEqual(command[command.index("--allow-state") + 1], "candidate-review")
        self.assertEqual(
            command[command.index("--first-event-timeout-ms") + 1], "180000"
        )
        self.assertEqual(
            command[command.index("--inter-event-timeout-ms") + 1], "300000"
        )
        self.assertEqual(command[command.index("--provider-max-retries") + 1], "1")

    def test_execution_profile_overrides_reach_worker_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            entrypoint = self._fixture(root)
            workspace = root / "workspace"
            run_root = root / "run"
            workspace.mkdir()
            run_root.mkdir()
            prompt = workspace / "AGENT_TASK.md"
            prompt.write_text("perform fixture", encoding="utf-8")
            events: list[tuple[str, dict[str, object]]] = []
            runtime = PiWorkerRuntime(
                {
                    "executable": sys.executable,
                    "entrypoint": str(entrypoint),
                    "model": "fixture/model",
                }
            )

            result = runtime.execute(
                workspace,
                prompt,
                run_root,
                timeout=10,
                event_sink=lambda event, data: events.append((event, data)),
                reasoning_policy="low",
                reasoning_budget={
                    "initial_level": "low",
                    "maximum_level": "medium",
                    "per_request_tokens": 512,
                    "total_tokens": 2048,
                    "max_provider_requests": 4,
                    "max_escalations": 1,
                    "escalation_triggers": ["semantic_literary_judgment"],
                    "over_budget_action": "validate_then_stop",
                },
                max_turns=2,
                max_tool_calls=3,
                max_repairs=1,
                first_event_timeout=45,
                inter_event_timeout=90,
                allowed_states=("story-architecture-agent-task",),
            )
            invocation = json.loads((workspace / "worker_args.json").read_text(encoding="utf-8"))

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.metadata["worker_result"]["status"], "completed")
        self.assertEqual(invocation["prompt"], "perform fixture")
        self.assertEqual(invocation["args"][invocation["args"].index("--thinking") + 1], "low")
        self.assertEqual(invocation["args"][invocation["args"].index("--max-thinking-level") + 1], "medium")
        self.assertEqual(invocation["args"][invocation["args"].index("--reasoning-total") + 1], "2048")
        self.assertEqual(invocation["args"][invocation["args"].index("--reasoning-per-request") + 1], "512")
        self.assertEqual(invocation["args"][invocation["args"].index("--max-provider-requests") + 1], "4")
        self.assertEqual(result.metadata["reasoning_budget_receipt"]["status"], "matched")
        self.assertEqual(result.metadata["reasoning_budget_receipt"]["provider_support"], "partial")
        self.assertEqual(result.metadata["reasoning_budget_receipt"]["effective_level"], "off")
        self.assertEqual(invocation["args"][invocation["args"].index("--max-turns") + 1], "2")
        self.assertEqual(invocation["args"][invocation["args"].index("--max-tools") + 1], "3")
        self.assertEqual(
            invocation["args"][invocation["args"].index("--first-event-timeout-ms") + 1],
            "45000",
        )
        self.assertEqual(
            invocation["args"][invocation["args"].index("--inter-event-timeout-ms") + 1],
            "90000",
        )
        self.assertEqual(
            invocation["args"][invocation["args"].index("--allow-state") + 1],
            "story-architecture-agent-task",
        )
        self.assertTrue(any(event == "runner.reasoning.activity" for event, _ in events))
        self.assertTrue(any(event == "tool.started" for event, _ in events))
        self.assertTrue(any(event == "usage.updated" for event, _ in events))

    def test_initial_project_repair_enters_repair_mode_on_the_first_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            entrypoint = self._fixture(root)
            workspace = root / "workspace"
            run_root = root / "run"
            workspace.mkdir()
            run_root.mkdir()
            prompt = workspace / "AGENT_TASK.md"
            prompt.write_text("repair exact project targets", encoding="utf-8")
            runtime = PiWorkerRuntime(
                {
                    "executable": sys.executable,
                    "entrypoint": str(entrypoint),
                    "model": "fixture/model",
                }
            )

            result = runtime.execute(
                workspace,
                prompt,
                run_root,
                timeout=10,
                initial_repair_targets=(
                    "canon/timeline.yaml",
                    "scenes/scene_0001.yaml",
                ),
            )
            invocation = json.loads(
                (workspace / "worker_args.json").read_text(encoding="utf-8")
            )["args"]

        self.assertEqual(result.status, "completed")
        self.assertEqual(invocation[invocation.index("--mode") + 1], "repair")
        repair_targets = [
            invocation[index + 1]
            for index, item in enumerate(invocation)
            if item == "--repair-target"
        ]
        self.assertEqual(
            repair_targets,
            ["canon/timeline.yaml", "scenes/scene_0001.yaml"],
        )

    def test_incomplete_worker_result_is_classified_for_studio(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            entrypoint = self._fixture(root)
            workspace = root / "workspace"
            run_root = root / "run"
            workspace.mkdir()
            run_root.mkdir()
            prompt = workspace / "AGENT_TASK.md"
            prompt.write_text("incomplete fixture", encoding="utf-8")
            runtime = PiWorkerRuntime(
                {
                    "executable": sys.executable,
                    "entrypoint": str(entrypoint),
                    "model": "fixture/model",
                }
            )

            result = runtime.execute(workspace, prompt, run_root, timeout=10)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.message, "model stopped without calling complete_task")
        self.assertEqual(result.metadata["failure_kind"], "validation_failure")
        self.assertTrue(result.metadata["retryable"])

    def test_empty_provider_response_is_a_retryable_transport_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "runtime.output.log"
            output.write_text(
                json.dumps(
                    {
                        "event": "runner.worker.result",
                        "data": {
                            "status": "incomplete",
                            "message": "model stopped without calling complete_task",
                            "failureKind": "provider_empty_response",
                            "providerRequests": 1,
                            "toolCalls": 0,
                            "reasoningCharacters": 0,
                            "textCharacters": 0,
                            "writtenOutputs": [],
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = PiWorkerRuntime({})._with_worker_result(
                RuntimeResult("pi-worker", "failed", 2, (), output, "failed")
            )

        self.assertEqual(result.metadata["failure_kind"], "transient_network")
        self.assertEqual(result.metadata["provider_failure_kind"], "provider_empty_response")
        self.assertTrue(result.metadata["retryable"])
        self.assertIn("空响应", result.message)

    def test_provider_quota_error_is_preserved_and_not_retried(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "runtime.output.log"
            output.write_text(
                json.dumps(
                    {
                        "event": "runner.worker.result",
                        "data": {
                            "status": "blocked",
                            "message": "provider request failed",
                            "failureKind": "provider_error",
                            "providerError": "DeepSeek API error (402) Payment Required",
                            "providerRequests": 1,
                            "toolCalls": 0,
                            "reasoningCharacters": 0,
                            "textCharacters": 0,
                            "writtenOutputs": [],
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = PiWorkerRuntime({})._with_worker_result(
                RuntimeResult("pi-worker", "failed", 2, (), output, "failed")
            )

        self.assertEqual(result.metadata["failure_kind"], "provider_quota")
        self.assertFalse(result.metadata["retryable"])
        self.assertIn("余额或额度不足", result.message)

    def test_provider_request_timeout_is_a_retryable_transport_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "runtime.output.log"
            output.write_text(
                json.dumps(
                    {
                        "event": "runner.worker.result",
                        "data": {
                            "status": "blocked",
                            "message": "provider request failed",
                            "failureKind": "provider_error",
                            "providerError": "Request timed out.",
                            "providerRequests": 1,
                            "toolCalls": 0,
                            "reasoningCharacters": 0,
                            "textCharacters": 0,
                            "writtenOutputs": [],
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = PiWorkerRuntime({})._with_worker_result(
                RuntimeResult("pi-worker", "failed", 2, (), output, "failed")
            )

        self.assertEqual(result.metadata["failure_kind"], "transient_network")
        self.assertTrue(result.metadata["retryable"])
        self.assertIn("自动重试", result.message)

    def test_worker_timeout_kind_is_preserved_without_text_reclassification(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "runtime.output.log"
            output.write_text(
                json.dumps(
                    {
                        "event": "runner.worker.result",
                        "data": {
                            "status": "blocked",
                            "message": "provider stream stopped",
                            "failureKind": "idle_timeout",
                            "providerError": "provider stream stopped producing model events",
                            "providerFailureRetryable": True,
                        },
                    }
                ),
                encoding="utf-8",
            )
            result = PiWorkerRuntime({})._with_worker_result(
                RuntimeResult("pi-worker", "failed", 2, (), output, "failed")
            )

        self.assertEqual(result.metadata["failure_kind"], "idle_timeout")
        self.assertEqual(result.metadata["provider_failure_kind"], "idle_timeout")
        self.assertTrue(result.metadata["retryable"])

    def test_studio_preflight_can_request_one_bounded_fresh_process_repair(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            entrypoint = self._fixture(root)
            workspace = root / "workspace"
            run_root = root / "run"
            workspace.mkdir()
            run_root.mkdir()
            prompt = workspace / "AGENT_TASK.md"
            prompt.write_text("perform fixture", encoding="utf-8")
            events: list[tuple[str, dict[str, object]]] = []
            runtime = PiWorkerRuntime(
                {
                    "executable": sys.executable,
                    "entrypoint": str(entrypoint),
                    "model": "fixture/model",
                }
            )

            def validate():
                passed = (workspace / "result.md").read_text(encoding="utf-8") == "repaired output"
                return PreflightResult(
                    passed,
                    () if passed else (
                        PreflightIssue(
                            "fixture-style",
                            "result.md",
                            "fixture needs a bounded repair",
                            "replace only the invalid fixture output",
                        ),
                    ),
                )

            result = runtime.execute(
                workspace,
                prompt,
                run_root,
                timeout=10,
                event_sink=lambda event, data: events.append((event, data)),
                max_repairs=1,
                output_validator=validate,
                repair_prompt_builder=lambda _result, attempt, maximum: SimpleNamespace(
                    prompt=f"# Studio Incremental Repair {attempt}/{maximum}\nfix the fixture output",
                    repair_targets=("result.md",),
                    repair_references=("source.md",),
                    reasoning_level="medium",
                    event_fields=lambda: {"repair_context_digest": "fixture"},
                ),
                repair_turn_finalizer=lambda: {"restored_output_count": 0},
            )
            invocation = json.loads(
                (workspace / "worker_args.json").read_text(encoding="utf-8")
            )["args"]

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.metadata["repair_attempts"], 1)
        self.assertTrue(result.metadata["final_preflight"]["passed"])
        self.assertTrue(any(event == "repair.started" for event, _ in events))
        self.assertTrue(any(event == "validation.failed" for event, _ in events))
        self.assertTrue(any(event == "validation.passed" for event, _ in events))
        self.assertEqual(invocation[invocation.index("--mode") + 1], "repair")
        self.assertEqual(
            invocation[invocation.index("--repair-target") + 1],
            "result.md",
        )
        self.assertEqual(
            invocation[invocation.index("--repair-reference") + 1],
            "source.md",
        )
        self.assertEqual(invocation[invocation.index("--thinking") + 1], "medium")
        self.assertEqual(result.metadata["repair_reasoning_level"], "medium")

    def test_reasoning_budget_exhaustion_is_non_retryable_no_progress(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "runtime.output.log"
            output.write_text(
                json.dumps(
                    {
                        "event": "runner.worker.result",
                        "data": {
                            "status": "blocked",
                            "message": "reasoning_token_budget_exhausted",
                            "reasoning_budget": {
                                "provider_support": "partial",
                                "actual_tokens": 2048,
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            runtime = PiWorkerRuntime({})
            result = runtime._with_worker_result(
                RuntimeResult("pi-worker", "failed", 2, (), output, "blocked")
            )

        self.assertEqual(result.metadata["failure_kind"], "no_progress")
        self.assertFalse(result.metadata["retryable"])

    def test_protocol_parser_omits_raw_invalid_output_and_secret_fields(self):
        runtime = PiWorkerRuntime({})
        malformed = runtime.normalize_output_line("not-json api_key=do-not-repeat")
        secret = runtime.normalize_output_line(
            json.dumps(
                {
                    "event": "runner.warning",
                    "data": {"detail": "safe", "api_key": "do-not-repeat", "nested": {"secret": "x"}},
                }
            )
        )

        self.assertNotIn("do-not-repeat", json.dumps(malformed))
        self.assertEqual(secret[0][1], {"detail": "safe", "nested": {}})

    def test_capabilities_declare_no_general_purpose_tools(self):
        runtime = PiWorkerRuntime({"model": "fixture/model"})
        capabilities = runtime.capabilities()

        self.assertFalse(capabilities.shell_control)
        self.assertFalse(capabilities.web_control)
        self.assertFalse(capabilities.subagent_control)
        self.assertFalse(capabilities.external_directory_control)
        self.assertIn("turn-limit-control", capabilities.capability_ids)
        self.assertIn("tool-limit-control", capabilities.capability_ids)
        self.assertIn("reasoning-budget-control", capabilities.capability_ids)
        self.assertIn("provider-request-limit-control", capabilities.capability_ids)
        self.assertIn("silence-timeout-control", capabilities.capability_ids)
        self.assertIn("provider-error-classification", capabilities.capability_ids)


if __name__ == "__main__":
    unittest.main()
