"""Experimental short-lived adapter for Pi coding-agent RPC mode."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import threading
import time
from typing import Any
from collections.abc import Callable, Sequence

from ..integrations.pi_rpc import PiRpcProcess, PiRpcProcessError
from ..subprocess_utils import run_hidden
from .base import AgentRunnerCapabilities, AgentRuntime, RuntimeAvailability, RuntimeResult, resolve_executable


class _PiCancelled(RuntimeError):
    pass


class PiRpcRuntime(AgentRuntime):
    runtime_id = "pi-rpc"

    def build_command(self, workspace: Path) -> Sequence[str]:
        del workspace
        executable = resolve_executable(str(self.settings.get("executable") or ""))
        entrypoint = str(self.settings.get("entrypoint") or "").strip()
        command = [executable]
        if entrypoint:
            command.append(str(Path(entrypoint).expanduser().resolve()))
        command.extend(
            [
                "--mode",
                "rpc",
                "--no-session",
                "--no-extensions",
                "--no-skills",
                "--no-prompt-templates",
            ]
        )
        model = str(self.settings.get("model") or "").strip()
        if model:
            command.extend(["--model", model])
        return tuple(command)

    def availability(self) -> RuntimeAvailability:
        executable = resolve_executable(str(self.settings.get("executable") or ""))
        if not executable:
            return RuntimeAvailability(self.runtime_id, False, "", "Pi RPC executable not found")
        entrypoint_value = str(self.settings.get("entrypoint") or "").strip()
        entrypoint = Path(entrypoint_value).expanduser().resolve() if entrypoint_value else None
        if entrypoint is not None and not entrypoint.is_file():
            return RuntimeAvailability(self.runtime_id, False, executable, "Pi RPC entrypoint not found")
        command = [executable]
        if entrypoint is not None:
            command.append(str(entrypoint))
        command.append("--version")
        try:
            completed = run_hidden(
                command,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return RuntimeAvailability(self.runtime_id, False, executable, f"version probe failed: {exc}")
        detail = (completed.stdout.strip() or completed.stderr.strip() or f"exit code {completed.returncode}").splitlines()[0]
        return RuntimeAvailability(self.runtime_id, completed.returncode == 0, executable, detail)

    def capabilities(self, availability: RuntimeAvailability | None = None) -> AgentRunnerCapabilities:
        availability = availability or self.availability()
        model = str(self.settings.get("model") or "").strip()
        if not availability.available:
            readiness = "unavailable"
        elif not model:
            readiness = "model-selection-required"
        else:
            readiness = "ready-for-experimental-probe"
        return AgentRunnerCapabilities(
            runner_id=self.runtime_id,
            version=availability.detail if availability.available else "",
            available=availability.available and bool(model),
            readiness_state=readiness,
            authentication_state="runner-managed-not-probed",
            provider=model.split("/", 1)[0] if "/" in model else "",
            selected_model=model,
            execution_modes=("single-task", "rpc", "jsonl", "experiment-only"),
            structured_output=True,
            streaming_events=True,
            model_selection=True,
            read_control=False,
            edit_control=False,
            shell_control=False,
            subagent_control=False,
            web_control=False,
            external_directory_control=False,
            stop=True,
            retry=True,
            resume=False,
            detail=availability.detail + "; external read isolation is not enforced",
            tool_calls=True,
            cancellation=True,
            local_execution=True,
            capability_ids=self.execution_control_capabilities(),
        )

    def execution_control_capabilities(self) -> tuple[str, ...]:
        return ("process-cancellation", "total-timeout-control")

    def execute(
        self,
        workspace: Path,
        prompt_path: Path,
        run_root: Path,
        *,
        timeout: int,
        event_sink: Callable[[str, dict[str, Any]], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> RuntimeResult:
        availability = self.availability()
        if not availability.available:
            raise RuntimeError(f"runtime {self.runtime_id} is unavailable: {availability.detail}")
        run_root.mkdir(parents=True, exist_ok=True)
        events_path = run_root / "runtime.events.jsonl"
        output_path = run_root / "runtime.output.log"
        command = tuple(self.build_command(workspace))
        cancellation = cancel_event or threading.Event()
        prompt = self.load_execution_prompt(prompt_path)
        started = time.monotonic()

        with output_path.open("w", encoding="utf-8") as output:
            process = PiRpcProcess(
                command,
                cwd=workspace,
                event_sink=_event_receiver(events_path, output, event_sink),
            )
            try:
                status, message, session, stats = self._run_session(
                    process,
                    events_path=events_path,
                    event_sink=event_sink,
                    prompt=prompt,
                    timeout=timeout,
                    cancellation=cancellation,
                    started=started,
                )
            finally:
                returncode = process.close(timeout=5)

        _emit(
            events_path,
            event_sink,
            "runner.process.completed",
            {"runner_id": self.runtime_id, "status": status, "returncode": returncode},
        )
        return self._result(
            status=status,
            message=message,
            returncode=returncode,
            command=command,
            output_path=output_path,
            session=session,
            stats=stats,
            started=started,
        )

    def _run_session(
        self,
        process: PiRpcProcess,
        *,
        events_path: Path,
        event_sink: Callable[[str, dict[str, Any]], None] | None,
        prompt: str,
        timeout: int,
        cancellation: threading.Event,
        started: float,
    ) -> tuple[str, str, dict[str, Any], dict[str, Any]]:
        session: dict[str, Any] = {}
        stats: dict[str, Any] = {}
        try:
            process.start()
            _emit(events_path, event_sink, "runner.process.started", {"runner_id": self.runtime_id, "pid": process.pid})
            session = dict(
                (
                    process.request(
                        "get_state",
                        timeout=_remaining_timeout(started, timeout, cap=15),
                    ).get("data")
                    or {}
                )
            )
            _emit(
                events_path,
                event_sink,
                "runner.session.created",
                {"session_id": str(session.get("sessionId") or ""), "ephemeral": True},
            )
            process.request(
                "prompt",
                message=prompt,
                timeout=_remaining_timeout(started, timeout, cap=30),
            )
            _emit(events_path, event_sink, "runner.prompt.submitted", {"runner_id": self.runtime_id})
            process.wait_for_event(
                lambda event: event.get("type") == "agent_settled",
                timeout=_remaining_timeout(started, timeout),
                on_wait=lambda: _cancel_if_requested(process, cancellation),
            )
            stats = _session_stats(process)
            if stats:
                _emit(events_path, event_sink, "usage.updated", {"usage": stats.get("tokens") or {}, "cost_usd": stats.get("cost")})
            return "completed", "Pi RPC runtime completed", session, stats
        except _PiCancelled:
            return "cancelled", "Pi RPC runtime cancelled", session, stats
        except TimeoutError:
            process.abort(timeout=2)
            return "timeout", f"Pi RPC runtime timed out after {timeout}s", session, stats
        except (OSError, PiRpcProcessError) as exc:
            return "failed", str(exc), session, stats

    def _result(
        self,
        *,
        status: str,
        message: str,
        returncode: int | None,
        command: tuple[str, ...],
        output_path: Path,
        session: dict[str, Any],
        stats: dict[str, Any],
        started: float,
    ) -> RuntimeResult:
        return RuntimeResult(
            runtime=self.runtime_id,
            status=status,
            returncode=returncode,
            command=command,
            output_path=output_path,
            message=message,
            metadata={
                "session_id": str(session.get("sessionId") or stats.get("sessionId") or ""),
                "model": session.get("model") or {},
                "usage": stats.get("tokens") or {},
                "cost_usd": stats.get("cost"),
                "elapsed_ms": round((time.monotonic() - started) * 1000.0, 3),
                "experiment_only": True,
            },
        )


def _normalize_pi_event(record: dict[str, Any]) -> tuple[tuple[str, dict[str, Any]], ...]:
    handler = _PI_EVENT_HANDLERS.get(str(record.get("type") or ""))
    return handler(record) if handler is not None else ()


def _normalize_message_update(record: dict[str, Any]) -> tuple[tuple[str, dict[str, Any]], ...]:
    update = record.get("assistantMessageEvent") if isinstance(record.get("assistantMessageEvent"), dict) else {}
    update_type = str(update.get("type") or "")
    if update_type == "text_delta":
        return (("agent.message.delta", {"text": str(update.get("delta") or "")}),)
    if update_type in {"thinking_start", "thinking_delta", "thinking_end"}:
        length = len(str(update.get("delta") or update.get("content") or ""))
        return (("reasoning.activity", {"phase": update_type, "characters": length}),)
    return ()


def _normalize_tool_start(record: dict[str, Any]) -> tuple[tuple[str, dict[str, Any]], ...]:
    return (("tool.started", _tool_event_data(record)),)


def _normalize_tool_end(record: dict[str, Any]) -> tuple[tuple[str, dict[str, Any]], ...]:
    return (("tool.completed", {**_tool_event_data(record), "is_error": bool(record.get("isError"))}),)


def _tool_event_data(record: dict[str, Any]) -> dict[str, Any]:
    return {"tool": str(record.get("toolName") or ""), "tool_use_id": str(record.get("toolCallId") or "")}


def _fixed_event(event: str, data: dict[str, Any]) -> Callable[[dict[str, Any]], tuple[tuple[str, dict[str, Any]], ...]]:
    return lambda _record: ((event, data),)


def _activity_event(record: dict[str, Any]) -> tuple[tuple[str, dict[str, Any]], ...]:
    return (("agent.activity", {"phase": str(record.get("type") or "")}),)


_PI_EVENT_HANDLERS = {
    "agent_start": _fixed_event("agent.activity", {"phase": "started"}),
    "agent_settled": _fixed_event("agent.message.completed", {"status": "settled"}),
    "message_update": _normalize_message_update,
    "tool_execution_start": _normalize_tool_start,
    "tool_execution_end": _normalize_tool_end,
    "auto_retry_start": _activity_event,
    "compaction_start": _activity_event,
    "summarization_retry_scheduled": _activity_event,
}


def _event_receiver(
    events_path: Path,
    output,
    event_sink: Callable[[str, dict[str, Any]], None] | None,
) -> Callable[[dict[str, Any]], None]:
    def receive(record: dict[str, Any]) -> None:
        for event, data in _normalize_pi_event(record):
            _append_event(events_path, event, data)
            if event == "agent.message.delta":
                output.write(str(data.get("text") or ""))
                output.flush()
            if event_sink is not None:
                event_sink(event, data)

    return receive


def _cancel_if_requested(process: PiRpcProcess, cancellation: threading.Event) -> None:
    if cancellation.is_set():
        process.abort(timeout=2)
        raise _PiCancelled("Pi RPC runtime cancelled")


def _session_stats(process: PiRpcProcess) -> dict[str, Any]:
    try:
        return dict((process.request("get_session_stats", timeout=5).get("data") or {}))
    except (PiRpcProcessError, TimeoutError):
        return {}


def _remaining_timeout(started: float, total_seconds: int, *, cap: float | None = None) -> float:
    remaining = float(total_seconds) - (time.monotonic() - started)
    if remaining <= 0:
        raise TimeoutError("Pi RPC total timeout elapsed")
    return min(remaining, cap) if cap is not None else remaining


def _append_event(path: Path, event: str, data: dict[str, object]) -> None:
    payload = {"event": event, "at": datetime.now(timezone.utc).isoformat(), **data}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _emit(
    path: Path,
    event_sink: Callable[[str, dict[str, Any]], None] | None,
    event: str,
    data: dict[str, Any],
) -> None:
    _append_event(path, event, data)
    if event_sink is not None:
        event_sink(event, data)
