"""Dedicated bidirectional subprocess runtime for one Project Agent turn."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
import json
import queue
import subprocess
import threading
import time
from typing import Any
from uuid import uuid4

from ..subprocess_utils import popen_hidden
from .contracts import (
    MAX_TOOL_RESULT_BYTES,
    BridgeEnvelope,
    BridgeMessageType,
    ProjectAgentToolCall,
    ProjectAgentToolResult,
    ProjectAgentTurnRequest,
    ProjectAgentTurnResult,
)


ToolHandler = Callable[[ProjectAgentToolCall], Any]
EventSink = Callable[[str, dict[str, Any]], None]


class ProjectAgentRuntime:
    """Run a disposable Pi process and dispatch its typed tool requests."""

    def __init__(self, command: Sequence[str], *, cwd: Path | None = None):
        normalized = tuple(str(item) for item in command if str(item).strip())
        if not normalized:
            raise ValueError("Project Agent command is required")
        self.command = normalized
        self.cwd = cwd

    def run_turn(
        self,
        request: ProjectAgentTurnRequest,
        tool_handler: ToolHandler,
        *,
        timeout: float = 120.0,
        cancel_event: threading.Event | None = None,
        event_sink: EventSink | None = None,
    ) -> ProjectAgentTurnResult:
        if timeout <= 0:
            raise ValueError("Project Agent timeout must be positive")
        cancellation = cancel_event or threading.Event()
        process = popen_hidden(
            list(self.command),
            cwd=self.cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdin is not None and process.stdout is not None and process.stderr is not None
        stdout: queue.Queue[str | None] = queue.Queue()
        stderr_lines: list[str] = []
        stdout_reader = _line_reader(process.stdout, stdout, "project-agent-stdout")
        stderr_reader = _stderr_reader(process.stderr, stderr_lines)
        deadline = time.monotonic() + timeout
        cancel_sent_at: float | None = None
        start_sent = False
        terminal: ProjectAgentTurnResult | None = None
        terminal_received_at: float | None = None
        tool_calls = 0
        allowed = set(request.allowed_tools)

        try:
            while True:
                now = time.monotonic()
                should_cancel = cancellation.is_set() or now >= deadline
                if should_cancel and cancel_sent_at is None and process.poll() is None:
                    reason = "Project Agent turn cancelled" if cancellation.is_set() else "Project Agent turn timed out"
                    _write_envelope(
                        process,
                        BridgeEnvelope(
                            type=BridgeMessageType.TURN_CANCEL,
                            message_id=_message_id(),
                            turn_id=request.turn_id,
                            payload={"reason": reason},
                        ),
                    )
                    cancel_sent_at = now
                if cancel_sent_at is not None and now - cancel_sent_at >= 1.0 and process.poll() is None:
                    _terminate(process)
                if terminal_received_at is not None and now - terminal_received_at >= 1.0 and process.poll() is None:
                    _terminate(process)

                try:
                    line = stdout.get(timeout=0.05)
                except queue.Empty:
                    line = ""
                if line is None:
                    if process.poll() is not None:
                        break
                    continue
                if line:
                    try:
                        envelope = BridgeEnvelope.from_json_line(line)
                        if envelope.type is BridgeMessageType.BRIDGE_READY:
                            if start_sent:
                                raise ValueError("Project Agent emitted bridge.ready more than once")
                            _write_envelope(process, request.start_envelope(_message_id()))
                            start_sent = True
                            _emit(event_sink, "project_agent.bridge.ready", dict(envelope.payload))
                        else:
                            if not start_sent:
                                raise ValueError("Project Agent emitted activity before bridge.ready")
                            if envelope.turn_id != request.turn_id:
                                raise ValueError("Project Agent event belongs to another turn")
                            if envelope.type is BridgeMessageType.AGENT_EVENT:
                                _emit(event_sink, "project_agent.event", dict(envelope.payload))
                            elif envelope.type is BridgeMessageType.TOOL_CALL:
                                call = ProjectAgentToolCall.from_envelope(envelope)
                                if call.name not in allowed:
                                    raise ValueError(f"Project Agent requested an undeclared tool: {call.name}")
                                tool_calls += 1
                                _emit(event_sink, "project_agent.tool.started", {"name": call.name, "request_id": call.request_id})
                                result = _execute_tool(call, tool_handler)
                                _write_envelope(process, result.envelope(_message_id()))
                                finished = {
                                    "name": call.name,
                                    "request_id": call.request_id,
                                    "ok": result.ok,
                                }
                                if result.ok and isinstance(result.result, Mapping):
                                    receipt = result.result.get("receipt")
                                    if isinstance(receipt, Mapping):
                                        finished["receipt"] = dict(receipt)
                                _emit(
                                    event_sink,
                                    "project_agent.tool.finished",
                                    finished,
                                )
                            elif envelope.type is BridgeMessageType.TURN_COMPLETE:
                                if terminal is not None:
                                    raise ValueError("Project Agent emitted more than one terminal result")
                                status = str(envelope.payload.get("status") or "blocked")
                                if status not in {"completed", "blocked", "cancelled"}:
                                    raise ValueError(f"unsupported Project Agent terminal status: {status}")
                                terminal = ProjectAgentTurnResult(
                                    status=status,
                                    answer=str(envelope.payload.get("answer") or ""),
                                    turn_id=request.turn_id,
                                    returncode=None,
                                    tool_calls=tool_calls,
                                    message="Project Agent turn completed",
                                )
                                terminal_received_at = time.monotonic()
                            elif envelope.type is BridgeMessageType.BRIDGE_ERROR:
                                terminal = ProjectAgentTurnResult(
                                    status="failed",
                                    answer="",
                                    turn_id=request.turn_id,
                                    returncode=None,
                                    tool_calls=tool_calls,
                                    message=str(envelope.payload.get("message") or "Project Agent bridge failed"),
                                )
                                terminal_received_at = time.monotonic()
                            else:
                                raise ValueError(f"unexpected Project Agent output: {envelope.type.value}")
                    except (TypeError, ValueError) as exc:
                        terminal = ProjectAgentTurnResult(
                            status="failed",
                            answer="",
                            turn_id=request.turn_id,
                            returncode=None,
                            tool_calls=tool_calls,
                            message=str(exc),
                        )
                        terminal_received_at = time.monotonic()
                        _terminate(process)

                if terminal is not None and process.poll() is None:
                    try:
                        process.stdin.close()
                    except OSError:
                        pass
                if process.poll() is not None and stdout.empty():
                    break

            returncode = process.wait(timeout=2)
            if terminal is None:
                if cancellation.is_set():
                    terminal = ProjectAgentTurnResult("cancelled", "", request.turn_id, returncode, tool_calls, "Project Agent turn cancelled")
                elif time.monotonic() >= deadline:
                    terminal = ProjectAgentTurnResult("timeout", "", request.turn_id, returncode, tool_calls, "Project Agent turn timed out")
                else:
                    detail = " ".join(stderr_lines).strip()[-1200:]
                    terminal = ProjectAgentTurnResult("failed", "", request.turn_id, returncode, tool_calls, detail or "Project Agent exited without a terminal result")
            terminal = replace(terminal, returncode=returncode)
            _emit(event_sink, "project_agent.turn.finished", {"status": terminal.status, "returncode": returncode})
            return terminal
        finally:
            if process.poll() is None:
                _terminate(process)
            for stream in (process.stdin, process.stdout, process.stderr):
                try:
                    stream.close()
                except OSError:
                    pass
            stdout_reader.join(timeout=1)
            stderr_reader.join(timeout=1)


def _execute_tool(call: ProjectAgentToolCall, handler: ToolHandler) -> ProjectAgentToolResult:
    try:
        value = handler(call)
        serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if len(serialized.encode("utf-8")) > MAX_TOOL_RESULT_BYTES:
            raise ValueError(f"Project Agent tool result exceeds {MAX_TOOL_RESULT_BYTES} bytes")
        return ProjectAgentToolResult(call.request_id, call.turn_id, call.name, True, value)
    except Exception as exc:  # The error is returned to Pi as tool evidence.
        return ProjectAgentToolResult(
            call.request_id,
            call.turn_id,
            call.name,
            False,
            None,
            str(exc)[:2000],
        )


def _write_envelope(process: subprocess.Popen[str], envelope: BridgeEnvelope) -> None:
    if process.stdin is None or process.stdin.closed:
        raise RuntimeError("Project Agent input is closed")
    process.stdin.write(envelope.to_json_line())
    process.stdin.flush()


def _line_reader(stream, target: queue.Queue[str | None], name: str) -> threading.Thread:
    def read() -> None:
        try:
            for line in stream:
                target.put(line)
        finally:
            target.put(None)

    thread = threading.Thread(target=read, name=name, daemon=True)
    thread.start()
    return thread


def _stderr_reader(stream, target: list[str]) -> threading.Thread:
    def read() -> None:
        for line in stream:
            if len(target) >= 40:
                del target[0]
            target.append(line.rstrip())

    thread = threading.Thread(target=read, name="project-agent-stderr", daemon=True)
    thread.start()
    return thread


def _terminate(process: subprocess.Popen[str]) -> None:
    try:
        process.terminate()
        process.wait(timeout=1)
    except (OSError, subprocess.TimeoutExpired):
        try:
            process.kill()
            process.wait(timeout=1)
        except (OSError, subprocess.TimeoutExpired):
            pass


def _message_id() -> str:
    return f"message-{uuid4()}"


def _emit(sink: EventSink | None, event: str, data: Mapping[str, Any]) -> None:
    if sink is not None:
        sink(event, dict(data))
