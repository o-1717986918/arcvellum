"""Adapter for the embedded bounded ArcVellum Pi Agent Core worker."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
import subprocess
from typing import Any
from collections.abc import Mapping, Sequence

from ..integrations.pi_worker import locate_pi_worker
from ..subprocess_utils import run_hidden
from .base import (
    AgentRunnerCapabilities,
    AgentRuntime,
    RuntimeAvailability,
    RuntimeFailureKind,
    RuntimeResult,
    executable_prefix,
)
from .opencode_failures import classify_model_error
from .pi_worker_repair import run_pi_worker_repairs


_WORKER_EVENTS = frozenset(
    {
        "runner.ready",
        "runner.session.created",
        "runner.session.finished",
        "runner.session.status",
        "runner.provider.request.started",
        "runner.reasoning.started",
        "runner.reasoning.activity",
        "runner.reasoning.completed",
        "agent.message.delta",
        "agent.message.completed",
        "tool.started",
        "tool.completed",
        "tool.denied",
        "usage.updated",
        "file.changed",
        "runner.worker.result",
        "runner.warning",
    }
)
_THINKING_LEVELS = frozenset({"off", "minimal", "low", "medium", "high", "xhigh", "max"})
_DEFAULT_STATES = (
    "asset-creation-agent-task",
    "canon-review-agent-task",
    "candidate-review",
)


class PiWorkerRuntime(AgentRuntime):
    """Run exactly one ArcVellum task through the narrow Pi Worker process."""

    runtime_id = "pi-worker"

    def __init__(self, settings: dict[str, object]):
        super().__init__(settings)
        self._execution_overrides: dict[str, object] = {}

    def availability(self) -> RuntimeAvailability:
        installation = locate_pi_worker(self.settings)
        executable = installation.executable
        if not executable:
            return RuntimeAvailability(self.runtime_id, False, "", "Node.js executable not found")
        entrypoint = installation.entrypoint
        if entrypoint is None or not entrypoint.is_file():
            return RuntimeAvailability(self.runtime_id, False, executable, "ArcVellum Pi Worker entrypoint not found")
        try:
            completed = run_hidden(
                [*executable_prefix(executable), str(entrypoint), "--version"],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return RuntimeAvailability(self.runtime_id, False, executable, f"version probe failed: {exc}")
        detail = (
            completed.stdout.strip()
            or completed.stderr.strip()
            or f"exit code {completed.returncode}"
        ).splitlines()[0]
        return RuntimeAvailability(self.runtime_id, completed.returncode == 0, executable, detail)

    def build_command(self, workspace: Path) -> Sequence[str]:
        installation = locate_pi_worker(self.settings)
        executable = installation.executable
        entrypoint = installation.entrypoint
        if not executable or entrypoint is None:
            raise RuntimeError("ArcVellum Pi Worker installation is incomplete")
        command = [*executable_prefix(executable), str(entrypoint), "--workspace", str(workspace)]
        model = str(self.settings.get("model") or "").strip()
        if model:
            command.extend(["--model", model])
        auth_path = str(self.settings.get("auth_path") or "").strip()
        if auth_path:
            command.extend(["--auth-path", str(Path(auth_path).expanduser().resolve())])
        command.extend(["--thinking", self._thinking_level()])
        command.extend(["--max-turns", str(self._positive_setting("max_turns", 6))])
        command.extend(["--max-tools", str(self._positive_setting("max_tool_calls", 12))])
        command.extend(["--max-repairs", str(self._positive_setting("max_repair_attempts", 1))])
        command.extend(self._reasoning_budget_args())
        for state in self._allowed_states():
            command.extend(["--allow-state", state])
        mode = str(self._execution_overrides.get("worker_mode") or "").strip()
        if mode:
            command.extend(["--mode", mode])
        for target in self._repair_targets():
            command.extend(["--repair-target", target])
        return tuple(command)

    def capabilities(self, availability: RuntimeAvailability | None = None) -> AgentRunnerCapabilities:
        availability = availability or self.availability()
        model = str(self.settings.get("model") or "").strip()
        ready = availability.available and bool(model)
        if not availability.available:
            readiness = "unavailable"
        elif not model:
            readiness = "model-selection-required"
        else:
            readiness = "ready"
        provider = model.split("/", 1)[0] if "/" in model else ""
        return AgentRunnerCapabilities(
            runner_id=self.runtime_id,
            version=availability.detail if availability.available else "",
            available=ready,
            readiness_state=readiness,
            authentication_state="runner-managed-not-probed",
            provider=provider,
            selected_model=model,
            execution_modes=("single-task", "bounded-tools", "jsonl", "embedded"),
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
            detail=availability.detail + "; task-context read/write policy enforced inside the worker",
            tool_calls=True,
            cancellation=True,
            local_execution=True,
            capability_ids=self.execution_control_capabilities(),
        )

    def execution_control_capabilities(self) -> tuple[str, ...]:
        return (
            "bounded-repair",
            "process-cancellation",
            "reasoning-policy-control",
            "reasoning-budget-control",
            "provider-request-limit-control",
            "tool-limit-control",
            "total-timeout-control",
            "turn-limit-control",
        )

    def normalize_output_line(self, line: str) -> tuple[tuple[str, dict[str, Any]], ...]:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return (("runner.warning", {"kind": "worker_protocol", "detail": "non-JSON worker output omitted"}),)
        if not isinstance(payload, dict):
            return (("runner.warning", {"kind": "worker_protocol", "detail": "non-object worker event omitted"}),)
        event = str(payload.get("event") or "")
        if event not in _WORKER_EVENTS:
            return (("runner.warning", {"kind": "worker_protocol", "detail": "unknown worker event omitted"}),)
        data = payload.get("data")
        return ((event, _public_event_data(data if isinstance(data, dict) else {})),)

    def execute(
        self,
        workspace: Path,
        prompt_path: Path,
        run_root: Path,
        *,
        timeout: int,
        event_sink=None,
        cancel_event=None,
        max_repairs: int | None = None,
        reasoning_policy: str | None = None,
        max_turns: int | None = None,
        max_tool_calls: int | None = None,
        reasoning_budget: Mapping[str, object] | None = None,
        output_validator=None,
        repair_prompt_builder=None,
        repair_turn_finalizer=None,
        progress_digest_builder=None,
        allowed_states: Sequence[str] | None = None,
    ) -> RuntimeResult:
        overrides = {
            "max_repair_attempts": max_repairs,
            "reasoning_policy": reasoning_policy,
            "max_turns": max_turns,
            "max_tool_calls": max_tool_calls,
            "reasoning_budget": dict(reasoning_budget) if reasoning_budget is not None else None,
            "allowed_states": tuple(allowed_states) if allowed_states is not None else None,
        }
        self._execution_overrides = {key: value for key, value in overrides.items() if value is not None}
        try:
            result = self._execute_once(
                workspace,
                prompt_path,
                run_root,
                timeout=timeout,
                event_sink=event_sink,
                cancel_event=cancel_event,
            )
            return run_pi_worker_repairs(
                result,
                run_root=run_root,
                output_validator=output_validator,
                max_repairs=int(max_repairs or 0),
                repair_prompt_builder=repair_prompt_builder,
                repair_turn_finalizer=repair_turn_finalizer,
                run_turn=lambda repair_prompt, repair_root, repair_targets: self._execute_once(
                    workspace,
                    repair_prompt,
                    repair_root,
                    timeout=timeout,
                    event_sink=event_sink,
                    cancel_event=cancel_event,
                    repair_targets=repair_targets,
                ),
                emit=event_sink or (lambda _event, _data: None),
            )
        finally:
            self._execution_overrides = {}

    def _execute_once(
        self,
        workspace: Path,
        prompt_path: Path,
        run_root: Path,
        *,
        timeout: int,
        event_sink=None,
        cancel_event=None,
        repair_targets: Sequence[str] = (),
    ) -> RuntimeResult:
        previous = dict(self._execution_overrides)
        if repair_targets:
            self._execution_overrides.update(
                {
                    "worker_mode": "repair",
                    "repair_targets": tuple(repair_targets),
                }
            )
        try:
            result = super().execute(
                workspace,
                prompt_path,
                run_root,
                timeout=timeout,
                event_sink=event_sink,
                cancel_event=cancel_event,
            )
            return self._with_worker_result(result)
        finally:
            self._execution_overrides = previous

    def _with_worker_result(self, result: RuntimeResult) -> RuntimeResult:
        worker_result = _last_worker_result(result.output_path)
        if not worker_result:
            return result
        status = str(worker_result.get("status") or "")
        message = str(worker_result.get("message") or result.message)
        metadata: dict[str, Any] = {
            "worker_result": worker_result,
            "reasoning_budget_receipt": self._reasoning_budget_receipt(worker_result),
        }
        if status != "completed":
            detail = message.lower()
            no_progress = status == "blocked" and any(
                token in detail
                for token in ("no-progress", "budget exhausted", "budget_exhausted")
            )
            provider_error = str(worker_result.get("providerError") or "").strip()
            provider_empty = _provider_empty_response(worker_result)
            if provider_error:
                failure_kind, retryable, public_message = classify_model_error(
                    provider_error
                )
                message = public_message
            elif provider_empty:
                message = (
                    "模型供应商返回了空响应，未产生文本、推理或工具调用；"
                    "ArcVellum 将保留当前任务并按连接故障策略重试。"
                )
            metadata.update(
                {
                    "failure_kind": (
                        failure_kind.value
                        if provider_error
                        else (
                            RuntimeFailureKind.TRANSIENT_NETWORK.value
                            if provider_empty
                            else (
                                RuntimeFailureKind.NO_PROGRESS.value
                                if no_progress
                                else RuntimeFailureKind.VALIDATION_FAILURE.value
                            )
                        )
                    ),
                    "retryable": retryable if provider_error else not no_progress,
                    "provider_failure_kind": (
                        "provider_error"
                        if provider_error
                        else ("provider_empty_response" if provider_empty else "")
                    ),
                }
            )
        return replace(result, message=message, metadata=metadata)

    def _reasoning_budget_args(self) -> list[str]:
        budget = self._execution_overrides.get("reasoning_budget")
        if not isinstance(budget, Mapping):
            return []
        maximum = str(budget.get("maximum_level") or "").strip().lower()
        if maximum not in _THINKING_LEVELS:
            raise ValueError(f"unsupported maximum thinking level: {maximum}")
        return [
            "--max-thinking-level",
            maximum,
            "--reasoning-total",
            str(_positive_budget_value(budget, "total_tokens")),
            "--reasoning-per-request",
            str(_positive_budget_value(budget, "per_request_tokens")),
            "--max-provider-requests",
            str(_positive_budget_value(budget, "max_provider_requests")),
            "--max-reasoning-escalations",
            str(_non_negative_budget_value(budget, "max_escalations")),
        ]

    def _reasoning_budget_receipt(self, worker_result: Mapping[str, Any]) -> dict[str, Any]:
        expected = self._execution_overrides.get("reasoning_budget")
        receipt = worker_result.get("reasoning_budget")
        if not isinstance(expected, Mapping):
            return _public_event_data(receipt) if isinstance(receipt, dict) else {}
        if not isinstance(receipt, dict):
            return {"status": "missing", "provider_support": "unknown"}
        public = _public_event_data(receipt)
        requested = public.get("requested")
        matches = isinstance(requested, dict) and all(
            requested.get(key) == expected.get(key)
            for key in (
                "initial_level",
                "maximum_level",
                "per_request_tokens",
                "total_tokens",
                "max_provider_requests",
                "max_escalations",
                "over_budget_action",
            )
        )
        return {**public, "status": "matched" if matches else "mismatch"}

    def _thinking_level(self) -> str:
        value = str(
            self._execution_overrides.get("reasoning_policy")
            or self.settings.get("thinking")
            or "low"
        ).strip().lower()
        return value if value in _THINKING_LEVELS else "low"

    def _positive_setting(self, name: str, fallback: int) -> int:
        value = self._execution_overrides.get(name, self.settings.get(name))
        try:
            normalized = int(value) if value not in {None, ""} else fallback
        except (TypeError, ValueError):
            return fallback
        return max(1, normalized)

    def _allowed_states(self) -> tuple[str, ...]:
        raw = self._execution_overrides.get("allowed_states", self.settings.get("allowed_states"))
        if not isinstance(raw, (list, tuple)):
            return _DEFAULT_STATES
        values = tuple(str(item).strip() for item in raw if str(item).strip())
        return values or _DEFAULT_STATES

    def _repair_targets(self) -> tuple[str, ...]:
        raw = self._execution_overrides.get("repair_targets")
        if not isinstance(raw, (list, tuple)):
            return ()
        return tuple(str(item).strip() for item in raw if str(item).strip())


def _public_event_data(value: dict[str, Any]) -> dict[str, Any]:
    return {key: _public_value(item) for key, item in value.items() if not _secret_key(key)}


def _public_value(value: Any) -> Any:
    if isinstance(value, dict):
        return _public_event_data(value)
    if isinstance(value, list):
        return [_public_value(item) for item in value[:100]]
    if isinstance(value, str):
        return value[:20_000]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:2_000]


def _secret_key(value: object) -> bool:
    normalized = str(value).lower().replace("-", "_")
    return any(token in normalized for token in ("api_key", "apikey", "password", "secret", "credential", "auth"))


def _last_worker_result(output_path: Path | None) -> dict[str, Any]:
    if output_path is None or not output_path.is_file():
        return {}
    result: dict[str, Any] = {}
    for line in output_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict) or payload.get("event") != "runner.worker.result":
            continue
        data = payload.get("data")
        if isinstance(data, dict):
            result = _public_event_data(data)
    return result


def _provider_empty_response(worker_result: Mapping[str, Any]) -> bool:
    if str(worker_result.get("failureKind") or "") == "provider_empty_response":
        return True
    receipt = worker_result.get("reasoning_budget")
    provider_requests = worker_result.get("providerRequests")
    if provider_requests is None and isinstance(receipt, Mapping):
        provider_requests = receipt.get("provider_requests")
    try:
        request_count = int(provider_requests or 0)
        tool_calls = int(worker_result.get("toolCalls") or 0)
        reasoning_characters = int(worker_result.get("reasoningCharacters") or 0)
        text_characters = int(worker_result.get("textCharacters") or 0)
    except (TypeError, ValueError):
        return False
    written = worker_result.get("writtenOutputs")
    return (
        request_count > 0
        and tool_calls == 0
        and reasoning_characters == 0
        and text_characters == 0
        and (not isinstance(written, list) or not written)
    )


def _positive_budget_value(budget: Mapping[str, object], name: str) -> int:
    try:
        value = int(budget.get(name) or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"reasoning budget {name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"reasoning budget {name} must be positive")
    return value


def _non_negative_budget_value(budget: Mapping[str, object], name: str) -> int:
    try:
        value = int(budget.get(name) or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"reasoning budget {name} must be an integer") from exc
    if value < 0:
        raise ValueError(f"reasoning budget {name} must be non-negative")
    return value
