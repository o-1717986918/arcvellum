"""Context-bound event projection shared by formal Worker execution paths."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class WorkerObservabilityMixin:
    event_sink: Any
    _context_ledger_fields: dict[str, str]
    _agent_session_id: str

    def _reset_context_ledger(self) -> None:
        self._context_ledger_fields = {}
        self._agent_session_id = ""

    def _bind_context_ledger(self, run: dict[str, Any]) -> None:
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

    def _publish_context_ready(self, task, sandbox, runtime_id: str) -> None:
        if task.execution_contract.execution_policy != "agent-required":
            return
        run = json.loads(sandbox.manifest_path.read_text(encoding="utf-8"))
        self._bind_context_ledger(run)
        self._emit(
            "sandbox.context_ready",
            {
                "run_id": sandbox.run_id,
                "run_root": str(sandbox.run_root),
                "workspace": str(sandbox.workspace),
                "project_root": str(task.project_root),
                "runner_id": runtime_id,
                "task_id": task.task_id,
            },
        )

    def _emit(self, event: str, data: dict[str, Any]) -> None:
        if event in {
            "runner.session.started",
            "runner.session.finished",
            "runner.session.status",
        }:
            session_id = str(data.get("session_id") or "").strip()
            if session_id:
                self._agent_session_id = session_id
        if self.event_sink is not None:
            self.event_sink(event, {**data, **self._context_ledger_fields})
