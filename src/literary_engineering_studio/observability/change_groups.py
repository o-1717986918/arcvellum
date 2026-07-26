"""Stable grouping for all receipts emitted by one Worker transaction."""

from __future__ import annotations

import hashlib
import json
from typing import Iterable

from .mutation_receipts import MutationReceipt


def change_group_id(*, project_key: str, run_id: str, task_id: str) -> str:
    payload = json.dumps(
        {"project_key": project_key, "run_id": run_id, "task_id": task_id},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"change-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:24]}"


def group_mutation_receipts(
    receipts: Iterable[MutationReceipt],
) -> dict[str, tuple[MutationReceipt, ...]]:
    grouped: dict[str, list[MutationReceipt]] = {}
    for receipt in receipts:
        grouped.setdefault(receipt.change_group_id, []).append(receipt)
    return {
        group_id: tuple(sorted(items, key=lambda item: (item.created_at, item.receipt_id)))
        for group_id, items in grouped.items()
    }
