"""Preview and atomically commit author-owned asset replacements."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import threading

from .contracts import OwnerOverrideTransaction, SemanticReview
from .impact import build_asset_impact
from .loader import AssetLoader
from .registry import AssetViewRegistry
from .revisions import content_revision
from .validation import validate_asset_content


class AssetVersionConflictError(RuntimeError):
    pass


class OwnerTransactionService:
    def __init__(self, registry: AssetViewRegistry, loader: AssetLoader):
        self.registry = registry
        self.loader = loader
        self._lock = threading.RLock()

    def preview(self, project_root: Path, transaction: OwnerOverrideTransaction) -> dict[str, object]:
        asset = self.loader.load(project_root, transaction.asset_id)
        definition, local_id = self.registry.parse_asset_id(transaction.asset_id)
        self._validate_transaction(transaction, asset.asset_type)
        content = transaction.replacement_content()
        validation = validate_asset_content(project_root.resolve(), definition, local_id, content)
        impact = build_asset_impact(project_root.resolve(), asset, content)
        return {
            "schema": "arcvellum/owner-override-preview/v1",
            "transaction": transaction.as_dict(),
            "asset": {
                "asset_id": asset.asset_id,
                "asset_type": asset.asset_type,
                "base_revision": asset.revision,
            },
            "validation": validation.as_dict(),
            "impact": impact,
            "committable": validation.valid
            and asset.revision == transaction.base_revision
            and transaction.semantic_review == SemanticReview.WAIVED,
        }

    def commit(self, project_root: Path, transaction: OwnerOverrideTransaction) -> dict[str, object]:
        if transaction.semantic_review != SemanticReview.WAIVED:
            raise ValueError("semantic review is required before this owner transaction can commit")
        if len(transaction.reason) < 6:
            raise ValueError("owner override reason must explain the author decision")
        with self._lock:
            return self._commit_locked(project_root.resolve(), transaction)

    def _commit_locked(self, root: Path, transaction: OwnerOverrideTransaction) -> dict[str, object]:
        asset = self.loader.load(root, transaction.asset_id)
        if asset.revision != transaction.base_revision:
            raise AssetVersionConflictError("archive asset changed after this editor revision was opened")
        definition, local_id = self.registry.parse_asset_id(transaction.asset_id)
        self._validate_transaction(transaction, asset.asset_type)
        content = transaction.replacement_content()
        validation = validate_asset_content(root, definition, local_id, content)
        if not validation.valid:
            raise ValueError("archive asset failed deterministic validation")
        if content == asset.content:
            raise ValueError("owner transaction does not change asset content")
        impact = build_asset_impact(root, asset, content)
        target = root / asset.relative_path
        receipt = self._write_transaction(root, target, asset.content, content, transaction, impact)
        return receipt

    @staticmethod
    def _validate_transaction(transaction: OwnerOverrideTransaction, actual_asset_type: str) -> None:
        if transaction.authority != "owner":
            raise ValueError("owner transaction authority must be owner")
        if transaction.asset_type != actual_asset_type:
            raise ValueError("owner transaction asset_type does not match asset_id")
        transaction.replacement_content()

    def _write_transaction(
        self,
        root: Path,
        target: Path,
        before: str,
        after: str,
        transaction: OwnerOverrideTransaction,
        impact: dict[str, object],
    ) -> dict[str, object]:
        archive_root = root / "workflow" / "archive" / "transactions"
        archive_root.mkdir(parents=True, exist_ok=True)
        final_dir = archive_root / transaction.transaction_id
        staging_dir = archive_root / f".{transaction.transaction_id}.tmp"
        if final_dir.exists() or staging_dir.exists():
            raise ValueError("owner transaction id already exists")
        staging_dir.mkdir()
        suffix = target.suffix or ".txt"
        before_path = staging_dir / f"before{suffix}"
        after_path = staging_dir / f"after{suffix}"
        transaction_path = staging_dir / "transaction.json"
        receipt_path = staging_dir / "receipt.json"
        before_path.write_text(before, encoding="utf-8")
        after_path.write_text(after, encoding="utf-8")
        _write_json(transaction_path, transaction.as_dict())
        new_revision = content_revision(after)
        receipt = {
            "schema": "arcvellum/mutation-receipt/v1",
            "transaction_id": transaction.transaction_id,
            "asset_id": transaction.asset_id,
            "asset_type": transaction.asset_type,
            "authority": "owner",
            "semantic_review": transaction.semantic_review.value,
            "base_revision": transaction.base_revision,
            "new_revision": new_revision,
            "reason": transaction.reason,
            "impact": impact,
            "stale_propagation": "recorded-for-follow-up",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _write_json(receipt_path, receipt)
        target_tmp = target.with_name(f".{target.name}.{transaction.transaction_id}.tmp")
        target_tmp.write_text(after, encoding="utf-8")
        try:
            target_tmp.replace(target)
            staging_dir.replace(final_dir)
        except Exception:
            target_tmp.unlink(missing_ok=True)
            rollback = target.with_name(f".{target.name}.{transaction.transaction_id}.rollback")
            rollback.write_text(before, encoding="utf-8")
            rollback.replace(target)
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise
        receipt.update(
            {
                "receipt_path": (final_dir / "receipt.json").relative_to(root).as_posix(),
                "transaction_path": (final_dir / "transaction.json").relative_to(root).as_posix(),
                "before_snapshot": (final_dir / f"before{suffix}").relative_to(root).as_posix(),
                "after_snapshot": (final_dir / f"after{suffix}").relative_to(root).as_posix(),
            }
        )
        _write_json(final_dir / "receipt.json", receipt)
        return receipt


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
