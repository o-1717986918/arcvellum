"""In-memory mutation receipt repository with deterministic identities."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ...observability.mutation_receipts import parse_mutation_receipt
from .state import MemoryPersistenceState


class InMemoryMutationReceiptRepository:
    def __init__(self, state: MemoryPersistenceState):
        self._state = state

    def record_mutation_receipt(self, project_root: str, payload: dict[str, Any]) -> dict[str, Any]:
        project = str(project_root or "").strip()
        if not project:
            raise ValueError("mutation receipt project_root is required")
        receipt = parse_mutation_receipt(payload)
        canonical = receipt.as_dict()
        with self._state.lock:
            existing = self._state.mutation_receipts.get(receipt.receipt_id)
            if existing is not None:
                if existing["project_root"] != project:
                    raise ValueError("mutation receipt belongs to a different project")
                if existing["payload"]["digest"] != receipt.digest:
                    raise ValueError("mutation receipt conflicts with an existing digest")
                return deepcopy(existing["payload"])
            self._state.mutation_receipts[receipt.receipt_id] = {
                "project_root": project,
                "payload": canonical,
            }
            return deepcopy(canonical)

    def read_mutation_receipt(self, receipt_id: str) -> dict[str, Any]:
        with self._state.lock:
            try:
                return deepcopy(self._state.mutation_receipts[receipt_id]["payload"])
            except KeyError as exc:
                raise FileNotFoundError(f"mutation receipt not found: {receipt_id}") from exc

    def list_mutation_receipts(
        self,
        project_root: str,
        *,
        task_id: str = "",
        run_id: str = "",
        session_id: str = "",
        plan_id: str = "",
        change_group_id: str = "",
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        filters = {
            "task_id": task_id,
            "run_id": run_id,
            "session_id": session_id,
            "plan_id": plan_id,
            "change_group_id": change_group_id,
        }
        with self._state.lock:
            records = [
                item["payload"] for item in self._state.mutation_receipts.values()
                if item["project_root"] == project_root
                and all(not value or item["payload"].get(key) == value for key, value in filters.items())
            ]
            records.sort(key=lambda item: (item["created_at"], item["receipt_id"]))
            return deepcopy(records[:max(1, min(2000, int(limit)))])


__all__ = ["InMemoryMutationReceiptRepository"]
