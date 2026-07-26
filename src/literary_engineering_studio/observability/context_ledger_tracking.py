"""Persist a run Context Ledger at the exact Agent-context-ready boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def persist_context_ledger_event(
    store,
    *,
    project_root: str,
    event: str,
    data: dict[str, Any],
) -> dict[str, Any] | None:
    if event != "sandbox.context_ready":
        return None
    run_root = str(data.get("run_root") or "").strip()
    ledger_path = str(data.get("context_ledger") or "").strip()
    if not run_root or not ledger_path:
        raise ValueError("sandbox.context_ready requires run_root and context_ledger")
    return persist_context_ledger_from_run(
        store,
        project_root=project_root,
        run_root=Path(run_root),
        ledger_path=Path(ledger_path),
    )


def persist_context_ledger_from_run(
    store,
    *,
    project_root: str,
    run_root: Path,
    ledger_path: Path | None = None,
) -> dict[str, Any]:
    root = run_root.expanduser().resolve()
    path = (ledger_path or (root / "context-ledger.json")).expanduser().resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("context ledger must remain inside its run root") from exc
    if not path.is_file():
        raise FileNotFoundError(f"context ledger not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("context ledger payload must be an object")
    return store.record_context_ledger(project_root, payload)


def persist_prepared_context(store, task, sandbox) -> dict[str, Any] | None:
    if task.execution_contract.execution_policy != "agent-required":
        return None
    return persist_context_ledger_from_run(
        store,
        project_root=str(task.project_root),
        run_root=sandbox.run_root,
    )
