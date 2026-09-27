"""Stable grouping for all receipts emitted by one Worker transaction."""

from __future__ import annotations

import hashlib
import json
def change_group_id(*, project_key: str, run_id: str, task_id: str) -> str:
    payload = json.dumps(
        {"project_key": project_key, "run_id": run_id, "task_id": task_id},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"change-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:24]}"
