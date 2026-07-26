"""Persist machine receipts arriving through an existing Worker event sink."""

from __future__ import annotations

from typing import Any


def persist_mutation_receipt_event(
    store,
    *,
    project_root: str,
    event: str,
    data: dict[str, Any],
) -> dict[str, Any] | None:
    if event != "mutation.receipt":
        return None
    receipt = data.get("receipt")
    if not isinstance(receipt, dict):
        raise ValueError("mutation.receipt event lacks a receipt object")
    return store.record_mutation_receipt(project_root, receipt)
