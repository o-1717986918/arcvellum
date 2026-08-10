"""Experimental adapter for the bounded ArcVellum Pi Agent Core worker."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any
from collections.abc import Sequence

from ..subprocess_utils import run_hidden
from .base import (
    AgentRunnerCapabilities,
    AgentRuntime,
    RuntimeAvailability,
    RuntimeResult,
    executable_prefix,
    resolve_executable,
)


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
        executable = resolve_executable(str(self.settings.get("executable") or "node"))
        if not executable:
            return RuntimeAvailability(self.runtime_id, False, "", "Node.js executable not found")
        entrypoint = self._entrypoint()
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
        executable = resolve_executable(str(self.settings.get("executable") or "node"))
        entrypoint = self._entrypoint()
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
        for state in self._allowed_states():
            command.extend(["--allow-state", state])
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
            readiness = "ready-for-experimental-probe"
        provider = model.split("/", 1)[0] if "/" in model else ""
        return AgentRunnerCapabilities(
            runner_id=self.runtime_id,
            version=availability.detail if availability.available else "",
            available=ready,
            readiness_state=readiness,
            authentication_state="runner-managed-not-probed",
            provider=provider,
            selected_model=model,
            execution_modes=("single-task", "bounded-tools", "jsonl", "experiment-only"),
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
    ) -> RuntimeResult:
        overrides = {
            "max_repair_attempts": max_repairs,
            "reasoning_policy": reasoning_policy,
            "max_turns": max_turns,
            "max_tool_calls": max_tool_calls,
        }
        self._execution_overrides = {key: value for key, value in overrides.items() if value is not None}
        try:
            return super().execute(
                workspace,
                prompt_path,
                run_root,
                timeout=timeout,
                event_sink=event_sink,
                cancel_event=cancel_event,
            )
        finally:
            self._execution_overrides = {}

    def _entrypoint(self) -> Path | None:
        value = str(self.settings.get("entrypoint") or "").strip()
        return Path(value).expanduser().resolve() if value else None

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
        raw = self.settings.get("allowed_states")
        if not isinstance(raw, (list, tuple)):
            return _DEFAULT_STATES
        values = tuple(str(item).strip() for item in raw if str(item).strip())
        return values or _DEFAULT_STATES


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
