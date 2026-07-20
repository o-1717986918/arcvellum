"""Runtime adapter contract for platform Agents."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time
from typing import Any
from collections.abc import Callable
from typing import Sequence

from ..subprocess_utils import popen_hidden, run_hidden


@dataclass(frozen=True)
class RuntimeAvailability:
    runtime: str
    available: bool
    executable: str
    detail: str


@dataclass(frozen=True)
class RuntimeResult:
    runtime: str
    status: str
    returncode: int | None
    command: tuple[str, ...]
    output_path: Path | None
    message: str


@dataclass(frozen=True)
class AgentRunnerCapabilities:
    runner_id: str
    version: str
    available: bool
    readiness_state: str
    authentication_state: str
    provider: str
    selected_model: str
    execution_modes: tuple[str, ...]
    structured_output: bool
    streaming_events: bool
    model_selection: bool
    read_control: bool
    edit_control: bool
    shell_control: bool
    subagent_control: bool
    web_control: bool
    external_directory_control: bool
    stop: bool
    retry: bool
    resume: bool
    detail: str

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["execution_modes"] = list(self.execution_modes)
        return payload


class AgentRuntime:
    runtime_id = "base"

    def __init__(self, settings: dict[str, object]):
        self.settings = settings

    def availability(self) -> RuntimeAvailability:
        executable = str(self.settings.get("executable") or "").strip()
        resolved = resolve_executable(executable)
        if not resolved:
            return RuntimeAvailability(self.runtime_id, False, executable, "executable not found")
        try:
            completed = run_hidden(
                [*executable_prefix(resolved), "--version"],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return RuntimeAvailability(self.runtime_id, False, resolved, f"version probe failed: {exc}")
        detail = (completed.stdout.strip() or completed.stderr.strip() or f"exit code {completed.returncode}").splitlines()[0]
        return RuntimeAvailability(self.runtime_id, completed.returncode == 0, resolved, detail)

    def build_command(self, workspace: Path) -> Sequence[str]:
        raise NotImplementedError

    def capabilities(self, availability: RuntimeAvailability | None = None) -> AgentRunnerCapabilities:
        availability = availability or self.availability()
        version = availability.detail if availability.available else ""
        return AgentRunnerCapabilities(
            runner_id=self.runtime_id,
            version=version,
            available=availability.available,
            readiness_state="installed" if availability.available else "unavailable",
            authentication_state="not-probed",
            provider="",
            selected_model="",
            execution_modes=("single-task",),
            structured_output=False,
            streaming_events=False,
            model_selection=False,
            read_control=False,
            edit_control=False,
            shell_control=False,
            subagent_control=False,
            web_control=False,
            external_directory_control=False,
            stop=False,
            retry=True,
            resume=False,
            detail=availability.detail,
        )

    def normalize_output_line(self, line: str) -> tuple[tuple[str, dict[str, Any]], ...]:
        return (("agent.message.delta", {"text": line.rstrip("\r\n")}),)

    def load_execution_prompt(self, prompt_path: Path) -> str:
        """Return the exact task prompt transported by every Runner adapter."""

        return prompt_path.read_text(encoding="utf-8")

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
        command = [*self.build_command(workspace)]
        prompt = self.load_execution_prompt(prompt_path)
        events_path = run_root / "runtime.events.jsonl"
        output_path = run_root / "runtime.output.log"
        _append_event(events_path, "runtime_started", {"runtime": self.runtime_id, "command": command})
        if event_sink:
            event_sink("runner.process.started", {"runner_id": self.runtime_id})
        cancellation = cancel_event or threading.Event()
        try:
            process = popen_hidden(
                command,
                cwd=workspace,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            _append_event(events_path, "runtime_failed", {"runtime": self.runtime_id, "error": str(exc)})
            return RuntimeResult(self.runtime_id, "failed", None, tuple(command), None, str(exc))
        assert process.stdin is not None and process.stdout is not None
        process.stdin.write(prompt)
        process.stdin.close()
        line_queue: queue.Queue[str | None] = queue.Queue()

        def read_output() -> None:
            try:
                for line in process.stdout:
                    line_queue.put(line)
            finally:
                line_queue.put(None)

        reader = threading.Thread(target=read_output, name=f"les-output-{self.runtime_id}", daemon=True)
        reader.start()
        deadline = time.monotonic() + max(1, timeout)
        reader_done = False
        status = "failed"
        message = "runtime failed"
        with output_path.open("w", encoding="utf-8") as output:
            while True:
                try:
                    item = line_queue.get(timeout=0.1)
                except queue.Empty:
                    item = ""
                if item is None:
                    reader_done = True
                elif item:
                    output.write(item)
                    output.flush()
                    for event, data in self.normalize_output_line(item):
                        _append_event(events_path, event, data)
                        if event_sink:
                            event_sink(event, data)
                if cancellation.is_set() and process.poll() is None:
                    _terminate_process(process)
                    status = "cancelled"
                    message = "runtime cancelled"
                elif time.monotonic() >= deadline and process.poll() is None:
                    _terminate_process(process)
                    status = "timeout"
                    message = f"timed out after {timeout}s"
                if process.poll() is not None and reader_done:
                    break
        reader.join(timeout=2)
        process.stdout.close()
        returncode = process.poll()
        if status not in {"cancelled", "timeout"}:
            status = "completed" if returncode == 0 else "failed"
            message = "runtime completed" if returncode == 0 else f"runtime exited with {returncode}"
        _append_event(
            events_path,
            "runtime_finished",
            {"runtime": self.runtime_id, "returncode": returncode, "status": status},
        )
        if event_sink:
            event_sink(
                "runner.process.completed",
                {"runner_id": self.runtime_id, "returncode": returncode, "status": status},
            )
        return RuntimeResult(
            self.runtime_id,
            status,
            returncode,
            tuple(command),
            output_path,
            message,
        )


def resolve_executable(value: str) -> str:
    if not value:
        return ""
    direct = Path(value).expanduser()
    if direct.is_file():
        return str(direct.resolve())
    found = shutil.which(value)
    if found:
        return found
    if Path(value).suffix == "" and shutil.which(value + ".cmd"):
        return str(shutil.which(value + ".cmd"))
    return ""


def executable_prefix(resolved: str) -> tuple[str, ...]:
    if os.name == "nt" and Path(resolved).suffix.lower() in {".cmd", ".bat"}:
        command_processor = os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe")
        return (command_processor, "/d", "/s", "/c", resolved)
    return (resolved,)


def _append_event(path: Path, event: str, data: dict[str, object]) -> None:
    payload = {"event": event, "at": datetime.now(timezone.utc).isoformat(), **data}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _terminate_process(process: subprocess.Popen[str]) -> None:
    try:
        process.terminate()
        process.wait(timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        try:
            process.kill()
        except OSError:
            pass
