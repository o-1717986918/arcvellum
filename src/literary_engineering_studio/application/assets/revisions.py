"""Content revisions and rebuildable Archive history indexes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Protocol


def content_revision(content: str) -> str:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


class AssetRevisionIndex(Protocol):
    def record_asset_transaction(self, record: dict[str, Any]) -> dict[str, Any]: ...

    def list_asset_transactions(
        self,
        project_root: str,
        asset_id: str,
        *,
        limit: int = 200,
    ) -> list[dict[str, Any]]: ...

    def list_asset_revisions(
        self,
        project_root: str,
        asset_id: str,
        *,
        limit: int = 200,
    ) -> list[dict[str, Any]]: ...

    def read_asset_revision(
        self,
        project_root: str,
        asset_id: str,
        revision: str,
    ) -> dict[str, Any]: ...


class AssetRevisionService:
    """Synchronize receipt truth into SQLite and resolve verified snapshots."""

    def __init__(self, index: AssetRevisionIndex):
        self.index = index

    def synchronize(self, project_root: Path, asset_id: str) -> dict[str, int]:
        root = project_root.resolve()
        indexed = 0
        skipped = 0
        transactions = root / "workflow" / "archive" / "transactions"
        if not transactions.is_dir():
            return {"indexed": 0, "skipped": 0}
        for receipt_path in sorted(transactions.glob("*/receipt.json")):
            receipt = _read_json(receipt_path)
            if str(receipt.get("asset_id") or "") != asset_id:
                continue
            try:
                record = self._record_from_receipt(root, receipt_path, receipt)
                self.index.record_asset_transaction(record)
            except (FileNotFoundError, ValueError):
                skipped += 1
            else:
                indexed += 1
        return {"indexed": indexed, "skipped": skipped}

    def history(
        self,
        project_root: Path,
        asset_id: str,
    ) -> dict[str, object]:
        root = project_root.resolve()
        sync = self.synchronize(root, asset_id)
        return {
            "transactions": self.index.list_asset_transactions(str(root), asset_id),
            "revisions": self.index.list_asset_revisions(str(root), asset_id),
            "synchronization": sync,
        }

    def snapshot_content(
        self,
        project_root: Path,
        asset_id: str,
        revision: str,
    ) -> tuple[str, dict[str, Any]]:
        root = project_root.resolve()
        self.synchronize(root, asset_id)
        record = self.index.read_asset_revision(str(root), asset_id, revision)
        snapshot = _safe_project_file(root, str(record.get("snapshot_path") or ""))
        content = snapshot.read_text(encoding="utf-8")
        if content_revision(content) != revision:
            raise ValueError("archive revision snapshot digest does not match the requested revision")
        return content, record

    def index_receipt(
        self,
        project_root: Path,
        receipt: dict[str, object],
    ) -> dict[str, Any]:
        root = project_root.resolve()
        receipt_path = _safe_project_file(root, str(receipt.get("receipt_path") or ""))
        record = self._record_from_receipt(root, receipt_path, receipt)
        return self.index.record_asset_transaction(record)

    @staticmethod
    def _record_from_receipt(
        root: Path,
        receipt_path: Path,
        receipt: dict[str, object],
    ) -> dict[str, Any]:
        for field in ("transaction_path", "before_snapshot", "after_snapshot"):
            _safe_project_file(root, str(receipt.get(field) or ""))
        return {
            **receipt,
            "project_root": str(root),
            "receipt_path": receipt_path.relative_to(root).as_posix(),
        }


def _safe_project_file(root: Path, relative: str) -> Path:
    clean = relative.strip().replace("\\", "/").lstrip("./")
    if not clean or clean.startswith("/") or ":" in clean or ".." in clean.split("/"):
        raise ValueError(f"invalid Archive snapshot path: {relative}")
    path = root / clean
    resolved = path.resolve()
    if path.is_symlink() or not resolved.is_relative_to(root) or not resolved.is_file():
        raise FileNotFoundError(f"Archive snapshot is unavailable: {clean}")
    return resolved


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}
