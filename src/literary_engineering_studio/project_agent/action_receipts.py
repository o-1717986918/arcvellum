"""Small receipts for Project Agent actions and long-running goals."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from ..application.failures import present_run
from .scope import work_reference


def action_receipt(operation: str, value: Mapping[str, Any]) -> dict[str, str]:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return {
        "operation": operation,
        "token": sha256(payload.encode("utf-8")).hexdigest()[:20],
    }


def goal_result(
    root: Path, operation: str, run: Mapping[str, Any], status: str
) -> dict[str, Any]:
    presented = present_run(dict(run))
    value = {
        "ok": True,
        "operation": f"goal_{operation}",
        "status": status,
        "work_id": work_reference(root)["work_id"],
        "run": presented,
    }
    receipt: dict[str, Any] = action_receipt(f"goal_{operation}", value)
    receipt.update(
        run_id=str(presented.get("run_id") or ""),
        run_status=str(presented.get("status") or ""),
        work_id=str(value["work_id"]),
        goal_status=status,
    )
    return {**value, "receipt": receipt}


__all__ = ["action_receipt", "goal_result"]
