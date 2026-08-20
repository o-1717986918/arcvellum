"""Read validation for one Studio Worker run manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_run(run_root: Path) -> dict[str, Any]:
    path = run_root.resolve() / "run.json"
    if not path.exists():
        raise FileNotFoundError(f"Studio run not found: {run_root}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid Studio run manifest: {path}")
    return payload


def update_run_manifest(path: Path, **updates: object) -> None:
    """Update the logical fields and freshness timestamp of one run manifest."""
    from .sandbox_files import utc_now

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(updates)
    payload["updated_at"] = utc_now()
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


__all__ = ["load_run", "update_run_manifest"]
