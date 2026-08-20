"""In-memory Archive transaction and asset revision index."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .state import MemoryPersistenceState


class InMemoryAssetRevisionIndex:
    def __init__(self, state: MemoryPersistenceState):
        self._state = state

    def record_asset_transaction(self, record: dict[str, Any]) -> dict[str, Any]:
        key = (str(record.get("project_root") or ""), str(record.get("asset_id") or ""))
        transaction_id = str(record.get("transaction_id") or "")
        if not all((*key, transaction_id)):
            raise ValueError("asset transaction identity is required")
        with self._state.lock:
            records = self._state.asset_transactions.setdefault(key, [])
            existing = next((item for item in records if item["transaction_id"] == transaction_id), None)
            if existing is not None:
                return deepcopy(existing)
            normalized = deepcopy(record)
            records.append(normalized)
            return deepcopy(normalized)

    def list_asset_transactions(
        self,
        project_root: str,
        asset_id: str,
        *,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        with self._state.lock:
            records = self._state.asset_transactions.get((project_root, asset_id), [])
            return deepcopy(records[-max(1, int(limit)):])

    def read_asset_revision(self, project_root: str, asset_id: str, revision: str) -> dict[str, Any]:
        revisions = self.list_asset_revisions(project_root, asset_id, limit=10000)
        match = next((item for item in revisions if item["revision"] == revision), None)
        if match is None:
            raise FileNotFoundError(f"asset revision not found: {asset_id}@{revision}")
        return match

    def list_asset_revisions(
        self,
        project_root: str,
        asset_id: str,
        *,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        with self._state.lock:
            revisions: dict[str, dict[str, Any]] = {}
            for record in self._state.asset_transactions.get((project_root, asset_id), []):
                for revision_field, snapshot_field, role in (
                    ("base_revision", "before_snapshot", "before"),
                    ("new_revision", "after_snapshot", "after"),
                ):
                    revision = str(record.get(revision_field) or "")
                    if revision:
                        revisions[revision] = {
                            "project_root": project_root,
                            "asset_id": asset_id,
                            "revision": revision,
                            "transaction_id": record["transaction_id"],
                            "snapshot_path": str(record.get(snapshot_field) or ""),
                            "snapshot_role": role,
                            "created_at": str(record.get("created_at") or ""),
                        }
            return deepcopy(list(revisions.values())[-max(1, int(limit)):])


__all__ = ["InMemoryAssetRevisionIndex"]
