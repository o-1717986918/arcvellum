"""Controlled Archive recycle-bin transactions over registered assets."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import threading
from typing import Any, Protocol
import uuid

from .impact import build_asset_impact
from .loader import AssetLoader
from .owner_transactions import AssetVersionConflictError
from .registry import AssetViewRegistry
from .revisions import content_revision
from .staleness import build_formal_stale_propagation
from .validation import validate_asset_content


_FORMAL_REFERENCE_ROOTS = ("scenes/", "canon/", "plot/")


class ArchiveReferenceConflictError(RuntimeError):
    def __init__(self, blockers: list[str]):
        self.blockers = blockers
        super().__init__("archive asset is still referenced by formal project facts")


class RestoreConflictError(RuntimeError):
    pass


class RecycleBinIndex(Protocol):
    def record_recycle_entry(self, record: dict[str, Any]) -> dict[str, Any]: ...


class RecycleBinService:
    def __init__(
        self,
        registry: AssetViewRegistry,
        loader: AssetLoader,
        index: RecycleBinIndex | None = None,
    ):
        self.registry = registry
        self.loader = loader
        self.index = index
        self._lock = threading.RLock()

    def archive(
        self,
        project_root: Path,
        asset_id: str,
        *,
        base_revision: str,
        reason: str,
    ) -> dict[str, object]:
        _validate_reason(reason)
        with self._lock:
            return self._archive_locked(project_root, asset_id, base_revision, reason.strip())

    def restore(
        self,
        project_root: Path,
        asset_id: str,
        *,
        entry_id: str,
        reason: str,
    ) -> dict[str, object]:
        _validate_reason(reason)
        with self._lock:
            return self._restore_locked(project_root, asset_id, entry_id, reason.strip())

    def entries(self, project_root: Path) -> dict[str, object]:
        root = _project_root(project_root)
        items, skipped = _scan_entries(root)
        indexed = 0
        index_failures = 0
        if self.index is not None:
            for entry in items:
                try:
                    self.index.record_recycle_entry({**entry, "project_root": str(root)})
                except (OSError, RuntimeError, ValueError):
                    index_failures += 1
                else:
                    indexed += 1
        return {
            "schema": "arcvellum/archive-recycle-bin/v1",
            "items": [_public_entry(entry) for entry in items],
            "synchronization": {
                "indexed": indexed,
                "skipped": skipped,
                "index_failures": index_failures,
                "status": "indexed" if self.index is not None and not index_failures else (
                    "not-configured" if self.index is None else "rebuild-required"
                ),
            },
        }

    def _archive_locked(
        self,
        project_root: Path,
        asset_id: str,
        base_revision: str,
        reason: str,
    ) -> dict[str, object]:
        root = _project_root(project_root)
        asset = self.loader.load(root, asset_id)
        definition, _ = self.registry.parse_asset_id(asset_id)
        if not definition.supports_archive:
            raise ValueError(f"archive is not supported for asset type: {definition.asset_type}")
        if asset.revision != base_revision:
            raise AssetVersionConflictError("archive asset changed after this revision was opened")
        impact = build_asset_impact(root, asset, "")
        blockers = _formal_blockers(impact)
        if blockers:
            raise ArchiveReferenceConflictError(blockers)
        entry = _new_entry(root, asset, reason)
        receipt = _archive_receipt(entry, impact)
        target = self.loader.resolve_path(root, asset_id)
        final_dir = _archive_files(root, target, entry, receipt)
        try:
            receipt["stale_propagation"] = build_formal_stale_propagation(root, asset.relative_path)
            _write_json(final_dir / "archive-receipt.json", receipt)
        except Exception:
            _rollback_archive(target, final_dir, Path(str(entry["snapshot_path"])).name)
            raise
        self._index_entry(root, entry, receipt)
        return receipt

    def _restore_locked(
        self,
        project_root: Path,
        asset_id: str,
        entry_id: str,
        reason: str,
    ) -> dict[str, object]:
        root = _project_root(project_root)
        entry_dir, entry = _load_entry(root, entry_id)
        if str(entry.get("asset_id") or "") != asset_id:
            raise RestoreConflictError("recycle entry does not belong to the requested asset")
        if str(entry.get("status") or "") != "active":
            raise RestoreConflictError("recycle entry is no longer active")
        target = self.loader.resolve_path(root, asset_id)
        if target.exists():
            raise RestoreConflictError("formal asset path already exists")
        content = _verified_snapshot(root, entry)
        definition, local_id = self.registry.parse_asset_id(asset_id)
        validation = validate_asset_content(root, definition, local_id, content)
        if not validation.valid:
            raise ValueError("archived snapshot failed deterministic validation")
        receipt, updated = _restored_records(entry, reason)
        _write_restored_target(target, content, entry_id)
        try:
            _mark_restored(entry_dir, updated, receipt)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        self._index_entry(root, updated, receipt)
        return receipt

    def _index_entry(
        self,
        root: Path,
        entry: dict[str, object],
        receipt: dict[str, object],
    ) -> None:
        if self.index is None:
            receipt["recycle_index"] = {"status": "not-configured"}
        else:
            try:
                self.index.record_recycle_entry({**entry, "project_root": str(root)})
            except (OSError, RuntimeError, ValueError) as exc:
                receipt["recycle_index"] = {"status": "rebuild-required", "message": str(exc)}
            else:
                receipt["recycle_index"] = {"status": "indexed"}
        receipt_name = "restore-receipt.json" if entry["status"] == "restored" else "archive-receipt.json"
        _write_json(root / str(entry["entry_path"]).rsplit("/", 1)[0] / receipt_name, receipt)


def _new_entry(root: Path, asset, reason: str) -> dict[str, object]:
    entry_id = f"recycle-{uuid.uuid4().hex}"
    relative_dir = Path("workflow") / "archive" / "recycle-bin" / entry_id
    suffix = Path(asset.relative_path).suffix or ".txt"
    archived_at = datetime.now(timezone.utc).isoformat()
    return {
        "schema": "arcvellum/archive-recycle-entry/v1",
        "entry_id": entry_id,
        "asset_id": asset.asset_id,
        "asset_type": asset.asset_type,
        "revision": asset.revision,
        "title": asset.title,
        "media_type": asset.media_type,
        "status": "active",
        "original_path": asset.relative_path,
        "snapshot_path": (relative_dir / f"snapshot{suffix}").as_posix(),
        "entry_path": (relative_dir / "entry.json").as_posix(),
        "archive_receipt_path": (relative_dir / "archive-receipt.json").as_posix(),
        "restore_receipt_path": "",
        "reason": reason,
        "archived_at": archived_at,
        "restored_at": "",
    }


def _archive_receipt(entry: dict[str, object], impact: dict[str, object]) -> dict[str, object]:
    return {
        "schema": "arcvellum/archive-recycle-receipt/v1",
        **entry,
        "impact": impact,
        "stale_propagation": {"status": "pending"},
    }


def _archive_files(
    root: Path,
    target: Path,
    entry: dict[str, object],
    receipt: dict[str, object],
) -> Path:
    archive_root = root / "workflow" / "archive" / "recycle-bin"
    archive_root.mkdir(parents=True, exist_ok=True)
    final_dir = archive_root / str(entry["entry_id"])
    staging_dir = archive_root / f".{entry['entry_id']}.tmp"
    if final_dir.exists() or staging_dir.exists():
        raise ValueError("recycle entry id already exists")
    staging_dir.mkdir()
    snapshot_name = Path(str(entry["snapshot_path"])).name
    staging_snapshot = staging_dir / snapshot_name
    target.replace(staging_snapshot)
    try:
        _activate_entry(staging_dir, entry, receipt)
        staging_dir.replace(final_dir)
    except Exception:
        _rollback_archive(target, staging_dir if staging_dir.exists() else final_dir, snapshot_name)
        raise
    return final_dir


def _activate_entry(
    staging_dir: Path,
    entry: dict[str, object],
    receipt: dict[str, object],
) -> None:
    _write_json(staging_dir / "entry.json", entry)
    _write_json(staging_dir / "archive-receipt.json", receipt)


def _rollback_archive(target: Path, entry_dir: Path, snapshot_name: str) -> None:
    snapshot = entry_dir / snapshot_name
    if snapshot.is_file() and not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        snapshot.replace(target)
    shutil.rmtree(entry_dir, ignore_errors=True)


def _restored_records(
    entry: dict[str, object],
    reason: str,
) -> tuple[dict[str, object], dict[str, object]]:
    restored_at = datetime.now(timezone.utc).isoformat()
    updated = {
        **entry,
        "status": "restored",
        "restore_receipt_path": str(entry["entry_path"]).rsplit("/", 1)[0] + "/restore-receipt.json",
        "restored_at": restored_at,
    }
    receipt = {
        "schema": "arcvellum/archive-restore-receipt/v1",
        **updated,
        "restore_reason": reason,
        "snapshot_preserved": True,
    }
    return receipt, updated


def _write_restored_target(target: Path, content: str, entry_id: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{entry_id}.tmp")
    temporary.write_text(content, encoding="utf-8")
    try:
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _mark_restored(
    entry_dir: Path,
    entry: dict[str, object],
    receipt: dict[str, object],
) -> None:
    _replace_json(entry_dir / "restore-receipt.json", receipt)
    _replace_json(entry_dir / "entry.json", entry)


def _scan_entries(root: Path) -> tuple[list[dict[str, object]], int]:
    recycle_root = root / "workflow" / "archive" / "recycle-bin"
    if not recycle_root.is_dir():
        return [], 0
    items: list[dict[str, object]] = []
    skipped = 0
    for entry_path in sorted(recycle_root.glob("recycle-*/entry.json")):
        try:
            entry = _read_entry(root, entry_path)
        except (OSError, RuntimeError, ValueError):
            skipped += 1
        else:
            items.append(entry)
    items.sort(key=lambda item: (str(item.get("archived_at") or ""), str(item["entry_id"])), reverse=True)
    return items, skipped


def _load_entry(root: Path, entry_id: str) -> tuple[Path, dict[str, object]]:
    _validate_entry_id(entry_id)
    entry_dir = root / "workflow" / "archive" / "recycle-bin" / entry_id
    entry = _read_entry(root, entry_dir / "entry.json")
    return entry_dir, entry


def _read_entry(root: Path, entry_path: Path) -> dict[str, object]:
    safe_path = _safe_project_file(root, entry_path)
    try:
        payload = json.loads(safe_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("recycle entry is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("recycle entry root must be an object")
    entry_id = str(payload.get("entry_id") or "")
    _validate_entry_id(entry_id)
    if safe_path.parent.name != entry_id:
        raise ValueError("recycle entry id does not match its directory")
    _verified_snapshot(root, payload)
    if str(payload.get("status") or "") not in {"active", "restored"}:
        raise ValueError("recycle entry has invalid status")
    return payload


def _verified_snapshot(root: Path, entry: dict[str, object]) -> str:
    snapshot = _safe_relative_file(root, str(entry.get("snapshot_path") or ""))
    content = snapshot.read_text(encoding="utf-8")
    if content_revision(content) != str(entry.get("revision") or ""):
        raise ValueError("recycle snapshot digest does not match its entry")
    return content


def _formal_blockers(impact: dict[str, object]) -> list[str]:
    references = impact.get("references")
    if not isinstance(references, list):
        return []
    return sorted(
        {
            str(item.get("path") or "")
            for item in references
            if isinstance(item, dict)
            and str(item.get("path") or "").startswith(_FORMAL_REFERENCE_ROOTS)
        }
    )


def _public_entry(entry: dict[str, object]) -> dict[str, object]:
    return {
        field: entry.get(field)
        for field in (
            "entry_id",
            "asset_id",
            "asset_type",
            "revision",
            "title",
            "media_type",
            "status",
            "original_path",
            "reason",
            "archived_at",
            "restored_at",
        )
    }


def _project_root(project_root: Path) -> Path:
    root = project_root.expanduser().resolve()
    if not root.is_dir() or not (root / "project.yaml").is_file():
        raise ValueError("archive project must contain project.yaml")
    return root


def _safe_relative_file(root: Path, relative: str) -> Path:
    clean = relative.strip().replace("\\", "/").lstrip("./")
    if not clean or clean.startswith("/") or ":" in clean or ".." in clean.split("/"):
        raise ValueError("invalid recycle entry path")
    return _safe_project_file(root, root / clean)


def _safe_project_file(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    if path.is_symlink() or not resolved.is_relative_to(root) or not resolved.is_file():
        raise FileNotFoundError("recycle entry file is unavailable")
    return resolved


def _validate_reason(reason: str) -> None:
    if len(str(reason or "").strip()) < 6:
        raise ValueError("archive reason must explain the author decision")


def _validate_entry_id(entry_id: str) -> None:
    if not entry_id.startswith("recycle-") or len(entry_id) > 100:
        raise ValueError("invalid recycle entry id")
    if any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in entry_id):
        raise ValueError("invalid recycle entry id")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _replace_json(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    _write_json(temporary, payload)
    temporary.replace(path)
