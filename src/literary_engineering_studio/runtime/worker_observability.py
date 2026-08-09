"""Context-bound event projection shared by formal Worker execution paths."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from ..observability.event_policy import is_ephemeral_runtime_event


class WorkerObserver:
    """Attach one worker run's context identity to emitted lifecycle events."""

    def __init__(self, event_sink: Any = None):
        self.event_sink = event_sink
        self._context_ledger_fields: dict[str, str] = {}
        self._agent_session_id = ""
        self._run_root: Path | None = None
        self._pending_sink_failures: list[dict[str, str]] = []

    @property
    def agent_session_id(self) -> str:
        return self._agent_session_id

    def reset_context_ledger(self) -> None:
        self._context_ledger_fields = {}
        self._agent_session_id = ""
        self._run_root = None
        self._pending_sink_failures = []

    def bind_run_root(self, run_root: Path) -> None:
        self._run_root = run_root.expanduser().resolve()
        self._flush_sink_failures()

    def bind_context_ledger(self, run: dict[str, Any]) -> None:
        ledger_id = str(run.get("context_ledger_id") or "")
        ledger_digest = str(run.get("context_ledger_digest") or "")
        ledger_path = str(run.get("context_ledger") or "")
        self._context_ledger_fields = (
            {
                "context_ledger_id": ledger_id,
                "context_ledger_digest": ledger_digest,
                "context_ledger": ledger_path,
                "run_root": str(run.get("run_root") or Path(ledger_path).parent),
            }
            if ledger_id and ledger_digest and ledger_path
            else {}
        )
        run_root = str(run.get("run_root") or "").strip()
        if run_root:
            self.bind_run_root(Path(run_root))

    def publish_context_ready(self, task, sandbox, runtime_id: str) -> None:
        if task.execution_contract.execution_policy != "agent-required":
            return
        run = json.loads(sandbox.manifest_path.read_text(encoding="utf-8"))
        self.bind_context_ledger(run)
        budget = run.get("context_budget") if isinstance(run.get("context_budget"), dict) else {}
        execution_context = (
            run.get("execution_context")
            if isinstance(run.get("execution_context"), dict)
            else {}
        )
        self.emit(
            "sandbox.context_ready",
            {
                "run_id": sandbox.run_id,
                "run_root": str(sandbox.run_root),
                "workspace": str(sandbox.workspace),
                "project_root": str(task.project_root),
                "runner_id": runtime_id,
                "task_id": task.task_id,
                "context_budget": budget,
                "execution_context": execution_context,
            },
        )

    def emit(self, event: str, data: dict[str, Any]) -> None:
        if event in {
            "runner.session.started",
            "runner.session.finished",
            "runner.session.status",
        }:
            session_id = str(data.get("session_id") or "").strip()
            if session_id:
                self._agent_session_id = session_id
        if self.event_sink is not None:
            try:
                context_fields = self._context_ledger_fields
                if is_ephemeral_runtime_event(event):
                    context_fields = {
                        key: value
                        for key, value in context_fields.items()
                        if key in {"context_ledger_id", "context_ledger_digest"}
                    }
                self.event_sink(event, {**data, **context_fields})
            except Exception as exc:
                self._pending_sink_failures.append(
                    {
                        "at": datetime.now(timezone.utc).isoformat(),
                        "event": event,
                        "error_type": type(exc).__name__,
                        "message": str(exc)[:500],
                    }
                )
                self._flush_sink_failures()

    def _flush_sink_failures(self) -> None:
        if self._run_root is None or not self._pending_sink_failures:
            return
        path = self._run_root / "observability-errors.jsonl"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as stream:
                for failure in self._pending_sink_failures:
                    stream.write(
                        json.dumps(failure, ensure_ascii=False, sort_keys=True) + "\n"
                    )
        except OSError:
            return
        self._pending_sink_failures.clear()
