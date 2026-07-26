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
