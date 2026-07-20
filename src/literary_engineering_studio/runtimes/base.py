"""Runtime adapter contract for platform Agents."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Sequence


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
            completed = subprocess.run(
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

    def execute(self, workspace: Path, prompt_path: Path, run_root: Path, *, timeout: int) -> RuntimeResult:
        availability = self.availability()
        if not availability.available:
            raise RuntimeError(f"runtime {self.runtime_id} is unavailable: {availability.detail}")
        command = [*self.build_command(workspace)]
        prompt = prompt_path.read_text(encoding="utf-8")
        events_path = run_root / "runtime.events.jsonl"
        output_path = run_root / "runtime.output.log"
        _append_event(events_path, "runtime_started", {"runtime": self.runtime_id, "command": command})
        try:
            completed = subprocess.run(
                command,
                cwd=workspace,
                input=prompt,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or "") + "\n" + (exc.stderr or "")
            output_path.write_text(output, encoding="utf-8")
            _append_event(events_path, "runtime_timeout", {"runtime": self.runtime_id, "timeout": timeout})
            return RuntimeResult(self.runtime_id, "timeout", None, tuple(command), output_path, f"timed out after {timeout}s")
        output = completed.stdout
        if completed.stderr:
            output += "\n[stderr]\n" + completed.stderr
        output_path.write_text(output, encoding="utf-8")
        status = "completed" if completed.returncode == 0 else "failed"
        _append_event(
            events_path,
            "runtime_finished",
            {"runtime": self.runtime_id, "returncode": completed.returncode, "status": status},
        )
        return RuntimeResult(
            self.runtime_id,
            status,
            completed.returncode,
            tuple(command),
            output_path,
            "runtime completed" if completed.returncode == 0 else f"runtime exited with {completed.returncode}",
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
