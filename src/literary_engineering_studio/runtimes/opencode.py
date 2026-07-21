"""Bundled OpenCode headless-server Agent Runner."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import threading
import time
from typing import Any
from collections.abc import Callable, Sequence

from ..config import default_data_root
from ..opencode_binary import bundle_manifest, locate_opencode
from ..opencode_server import OpenCodeServer
from ..process_manager import ProcessManager
from ..runtime_events import normalize_opencode_event
from ..subprocess_utils import run_hidden
from .base import AgentRunnerCapabilities, AgentRuntime, RuntimeAvailability, RuntimeResult


class OpenCodeRuntime(AgentRuntime):
    runtime_id = "opencode"

    def __init__(self, settings: dict[str, object]):
        super().__init__(settings)
        self.runtime_pool = None

    def build_command(self, workspace: Path) -> Sequence[str]:
        executable = locate_opencode(self.settings)
        return (str(executable or "opencode"), "serve", "--pure", "--hostname", "127.0.0.1", "--port", "0")

    def availability(self) -> RuntimeAvailability:
        executable = locate_opencode(self.settings)
        if executable is None:
            return RuntimeAvailability(self.runtime_id, False, "", "pinned OpenCode binary is not installed")
        try:
            completed = run_hidden(
                [str(executable), "--version"],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return RuntimeAvailability(self.runtime_id, False, str(executable), f"version probe failed: {exc}")
        version = (completed.stdout.strip() or completed.stderr.strip()).splitlines()[0]
        expected = str(bundle_manifest()["version"])
        detail = version if version == expected else f"{version}; pinned version is {expected}"
        return RuntimeAvailability(self.runtime_id, completed.returncode == 0, str(executable), detail)

    def capabilities(self, availability: RuntimeAvailability | None = None) -> AgentRunnerCapabilities:
        availability = availability or self.availability()
        model = str(self.settings.get("model") or "").strip()
        if not availability.available:
            readiness = "unavailable"
        elif not model:
            readiness = "model-connection-required"
        else:
            readiness = "ready-for-live-probe"
        return AgentRunnerCapabilities(
            runner_id=self.runtime_id,
            version=availability.detail if availability.available else "",
            available=availability.available and bool(model),
            readiness_state=readiness,
            authentication_state="runner-managed" if model else "connection-required",
            provider=model.split("/", 1)[0] if "/" in model else "",
            selected_model=model,
            execution_modes=("single-task", "headless-server", "sse"),
            structured_output=True,
            streaming_events=True,
            model_selection=True,
            read_control=True,
            edit_control=True,
            shell_control=True,
            subagent_control=True,
            web_control=True,
            external_directory_control=True,
            stop=True,
            retry=True,
            resume=False,
            detail=availability.detail + ("" if model else "; select a provider/model connection"),
        )

    def execute(
        self,
        workspace: Path,
        prompt_path: Path,
        run_root: Path,
        *,
        timeout: int,
        event_sink: Callable[[str, dict[str, Any]], None] | None = None,
        cancel_event: threading.Event | None = None,
        output_validator: Callable[[], Any] | None = None,
        max_repairs: int = 0,
    ) -> RuntimeResult:
        executable = locate_opencode(self.settings)
        if executable is None:
            raise RuntimeError("pinned OpenCode binary is not installed")
        models = self.settings.get("models") if isinstance(self.settings.get("models"), dict) else {}
        model = str(models.get("worker") or self.settings.get("worker_model") or self.settings.get("model") or "").strip()
        if "/" not in model:
            raise RuntimeError("OpenCode requires an explicit provider/model-id connection")
        cancellation = cancel_event or threading.Event()
        data_root = Path(str(self.settings.get("data_root") or default_data_root())).expanduser().resolve()
        manager = ProcessManager(run_root / "sidecar-logs") if self.runtime_pool is None else None
        server = OpenCodeServer(manager, executable=executable, shared_data_root=data_root) if manager is not None else None
        component_id = "opencode-" + re.sub(r"[^a-z0-9]+", "-", run_root.name.lower())[-40:].strip("-")
        output_path = run_root / "runtime.output.log"
        events_path = run_root / "runtime.events.jsonl"
        session_path = run_root / "opencode.session.json"
        diff_path = run_root / "opencode.diff.json"
        handle = None
        lease = None
        client = None
        event_stop = threading.Event()
        event_thread: threading.Thread | None = None
        session_id = ""
        errors: list[str] = []
        tool_states: dict[str, str] = {}
        execution_started = time.monotonic()
        first_public_event = False
        first_public_event_ms = 0
        first_text_ms = 0
        first_tool_ms = 0
        usage_summary: dict[str, Any] = {}

        def emit(name: str, data: dict[str, Any]) -> None:
            _append_event(events_path, name, data)
            if event_sink:
                event_sink(name, data)

        try:
            if self.runtime_pool is not None:
                lease = self.runtime_pool.acquire("worker", workspace, model=model)
                client = lease.client
                component_id = lease.component_id
            else:
                assert server is not None
                handle = server.start(
                    component_id=component_id,
                    workspace=workspace,
                    run_root=run_root,
                    role="worker",
                    model=model,
                )
                client = handle.client
            health = client.health()
            emit(
                "runner.process.started",
                {
                    "runner_id": self.runtime_id,
                    "version": health.get("version", ""),
                    "component_id": component_id,
                    "reused": bool(lease.reused) if lease is not None else False,
                    "generation": lease.generation if lease is not None else 1,
                    "elapsed_ms": round((time.monotonic() - execution_started) * 1000),
                },
            )
            session = client.create_session(f"Studio task {run_root.name}")
            session_id = str(session.get("id") or "")
            if not session_id:
                raise RuntimeError("OpenCode did not return a session id")
            session_path.write_text(json.dumps(session, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            emit(
                "runner.session.created",
                {"session_id": session_id, "elapsed_ms": round((time.monotonic() - execution_started) * 1000)},
            )

            def consume_events() -> None:
                nonlocal first_public_event, first_public_event_ms, first_text_ms, first_tool_ms
                try:
                    for raw in client.events(event_stop):
                        for name, data in normalize_opencode_event(raw, session_id=session_id, tool_states=tool_states):
                            if name in {"agent.message.delta", "tool.started"} and not first_public_event:
                                first_public_event = True
                                first_public_event_ms = round((time.monotonic() - execution_started) * 1000)
                                emit(
                                    "runner.first_event",
                                    {"session_id": session_id, "elapsed_ms": first_public_event_ms},
                                )
                            if name == "agent.message.delta" and not first_text_ms:
                                first_text_ms = round((time.monotonic() - execution_started) * 1000)
                                emit("runner.first_text", {"session_id": session_id, "elapsed_ms": first_text_ms})
                            if name == "tool.started" and not first_tool_ms:
                                first_tool_ms = round((time.monotonic() - execution_started) * 1000)
                                emit("runner.first_tool", {"session_id": session_id, "elapsed_ms": first_tool_ms})
                            if name == "usage.updated":
                                usage_summary.update(data)
                            emit(name, data)
                            if name == "runner.warning" and data.get("kind") == "session.error":
                                errors.append(json.dumps(data.get("detail") or {}, ensure_ascii=False))
                except RuntimeError as exc:
                    if not event_stop.is_set():
                        emit("runner.warning", {"session_id": session_id, "kind": "event-stream", "detail": str(exc)})

            event_thread = threading.Thread(target=consume_events, name=f"les-opencode-events-{session_id}", daemon=True)
            event_thread.start()
            prompt = self.load_execution_prompt(prompt_path)
            client.prompt_async(session_id, text=prompt, model=model, agent="literary-worker")
            emit("runner.session.started", {"runner_id": self.runtime_id, "session_id": session_id, "model": model})
            deadline = time.monotonic() + max(1, int(timeout))
            wait_status = _wait_for_session(client, session_id, deadline, cancellation)
            if wait_status == "cancelled":
                emit("run.stopped", {"session_id": session_id, "reason": "cancelled"})
                return RuntimeResult(self.runtime_id, "cancelled", None, self.build_command(workspace), output_path, "runtime cancelled")
            if wait_status == "timeout":
                client.abort(session_id)
                return RuntimeResult(self.runtime_id, "timeout", None, self.build_command(workspace), output_path, f"timed out after {timeout}s")

            repairs = 0
            final_preflight = None
            if output_validator is not None and not errors:
                while True:
                    final_preflight = output_validator()
                    payload = final_preflight.as_dict() if hasattr(final_preflight, "as_dict") else {"passed": bool(final_preflight)}
                    payload.update({"attempt": repairs, "maximum_repairs": max(0, int(max_repairs))})
                    emit("validation.passed" if payload.get("passed") else "validation.failed", {"kind": "sandbox-preflight", **payload})
                    if payload.get("passed"):
                        break
                    if repairs >= max(0, int(max_repairs)):
                        messages = client.messages(session_id)
                        assistant_text, _ = _assistant_result(messages)
                        output_path.write_text(assistant_text, encoding="utf-8")
                        emit("runner.process.completed", {"runner_id": self.runtime_id, "status": "preflight_failed"})
                        return RuntimeResult(
                            self.runtime_id,
                            "preflight_failed",
                            2,
                            self.build_command(workspace),
                            output_path,
                            "sandbox output still fails deterministic preflight",
                            {"session_id": session_id, "repairs": repairs, "preflight": payload},
                        )
                    repairs += 1
                    repair_prompt = final_preflight.repair_prompt(repairs, max(1, int(max_repairs)))
                    emit("repair.started", {"attempt": repairs, "issue_count": payload.get("issue_count", 0), "session_id": session_id})
                    client.prompt_async(session_id, text=repair_prompt, model=model, agent="literary-worker")
                    repair_deadline = time.monotonic() + min(300, max(60, int(timeout) // 3))
                    wait_status = _wait_for_session(client, session_id, repair_deadline, cancellation)
                    if wait_status != "completed":
                        client.abort(session_id)
                        status = "cancelled" if wait_status == "cancelled" else "timeout"
                        return RuntimeResult(self.runtime_id, status, None, self.build_command(workspace), output_path, f"repair {status}")
                    emit("repair.completed", {"attempt": repairs, "session_id": session_id})

            messages = client.messages(session_id)
            assistant_text, message_error = _assistant_result(messages)
            if message_error:
                errors.append(message_error)
            output_path.write_text(assistant_text, encoding="utf-8")
            diff = client.diff(session_id)
            diff_path.write_text(json.dumps(diff, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            if errors:
                emit("runner.process.completed", {"runner_id": self.runtime_id, "status": "failed", "errors": errors})
                return RuntimeResult(self.runtime_id, "failed", 1, self.build_command(workspace), output_path, errors[0])
            emit("agent.message.completed", {"session_id": session_id, "text": assistant_text})
            emit("runner.process.completed", {"runner_id": self.runtime_id, "status": "completed"})
            return RuntimeResult(
                self.runtime_id,
                "completed",
                0,
                self.build_command(workspace),
                output_path,
                "runtime completed",
                {
                    "session_id": session_id,
                    "component_id": component_id,
                    "service_reused": bool(lease.reused) if lease is not None else False,
                    "generation": lease.generation if lease is not None else 1,
                    "repairs": repairs,
                    "preflight": final_preflight.as_dict() if final_preflight is not None else {},
                    "time_to_first_event_ms": first_public_event_ms,
                    "time_to_first_text_ms": first_text_ms,
                    "time_to_first_tool_ms": first_tool_ms,
                    "total_ms": round((time.monotonic() - execution_started) * 1000),
                    "usage": usage_summary,
                },
            )
        except Exception as exc:
            emit("runner.process.completed", {"runner_id": self.runtime_id, "status": "failed", "error": str(exc)})
            return RuntimeResult(self.runtime_id, "failed", 1, self.build_command(workspace), output_path if output_path.exists() else None, str(exc))
        finally:
            event_stop.set()
            if lease is not None:
                self.runtime_pool.release(lease)
            elif handle is not None and server is not None:
                server.stop(handle)
            if event_thread is not None:
                event_thread.join(timeout=3)
            if manager is not None:
                manager.shutdown()


def _assistant_result(messages: list[dict[str, Any]]) -> tuple[str, str]:
    texts: list[str] = []
    error = ""
    for message in messages:
        info = message.get("info") if isinstance(message.get("info"), dict) else {}
        if info.get("role") != "assistant":
            continue
        if isinstance(info.get("error"), dict):
            error = json.dumps(info["error"], ensure_ascii=False)
        current: list[str] = []
        for part in message.get("parts") or []:
            if isinstance(part, dict) and part.get("type") == "text":
                current.append(str(part.get("text") or ""))
        if current:
            texts = current
    return "".join(texts), error


def _wait_for_session(client, session_id: str, deadline: float, cancellation: threading.Event) -> str:
    seen_busy = False
    while time.monotonic() < deadline:
        if cancellation.is_set():
            client.abort(session_id)
            return "cancelled"
        status_map = client.session_status()
        status = status_map.get(session_id) if isinstance(status_map, dict) else None
        state = str(status.get("type") or "") if isinstance(status, dict) else ""
        if state in {"busy", "retry"}:
            seen_busy = True
        if seen_busy and state in {"idle", ""}:
            return "completed"
        time.sleep(0.2)
    return "timeout"


def _append_event(path: Path, event: str, data: dict[str, Any]) -> None:
    payload = {"event": event, "at": datetime.now(timezone.utc).isoformat(), **data}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
