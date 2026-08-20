"""In-memory Context Ledger repository with SQLite-compatible semantics."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ...observability.context_ledger import parse_context_ledger
from .primitives import iso_now
from .state import MemoryPersistenceState


class InMemoryContextLedgerRepository:
    def __init__(self, state: MemoryPersistenceState, clock):
        self._state = state
        self._clock = clock

    def record_context_ledger(self, project_root: str, payload: dict[str, Any]) -> dict[str, Any]:
        project = str(project_root or "").strip()
        if not project:
            raise ValueError("context ledger project_root is required")
        ledger = parse_context_ledger(payload)
        with self._state.lock:
            existing = self._state.context_ledgers.get(ledger.ledger_id)
            if existing is not None:
                if existing["project_root"] != project:
                    raise ValueError("context ledger belongs to a different project")
                if existing["digest"] != ledger.digest:
                    raise ValueError("context ledger conflicts with an existing digest")
                return deepcopy(existing)
            record = {
                **ledger.as_dict(),
                "project_root": project,
                "created_at": iso_now(self._clock),
            }
            self._state.context_ledgers[ledger.ledger_id] = record
            return deepcopy(record)

    def read_context_ledger(self, ledger_id: str) -> dict[str, Any]:
        with self._state.lock:
            try:
                return deepcopy(self._state.context_ledgers[ledger_id])
            except KeyError as exc:
                raise FileNotFoundError(f"context ledger not found: {ledger_id}") from exc

    def list_context_ledgers(self, project_root: str, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._state.lock:
            records = [
                item for item in self._state.context_ledgers.values()
                if item["project_root"] == project_root
            ]
            records.sort(key=lambda item: (item["created_at"], item["ledger_id"]), reverse=True)
            return deepcopy(records[:max(1, min(1000, int(limit)))])


__all__ = ["InMemoryContextLedgerRepository"]
