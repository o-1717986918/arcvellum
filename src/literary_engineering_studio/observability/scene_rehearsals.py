"""Read-only public scene rehearsal history backed by transaction-local sessions."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Iterable

from ..application.scene_transaction import SceneTransaction


def scene_rehearsal_index(data_root: Path, transactions: Iterable[SceneTransaction]) -> list[dict[str, Any]]:
    result = []
    for transaction in transactions:
        path = _session_path(data_root, transaction.transaction_id)
        if path is None and transaction.status.value != "creating":
            continue
        state = _read_session(path, transaction.scene_id) if path else None
        result.append(_summary(transaction, path, state))
    return result


def scene_rehearsal_detail(
    data_root: Path, transactions: Iterable[SceneTransaction], transaction_id: str,
) -> dict[str, Any]:
    transaction = next((item for item in transactions if item.transaction_id == transaction_id), None)
    if transaction is None:
        raise ValueError("scene rehearsal does not belong to this project")
    path = _session_path(data_root, transaction_id)
    state = _read_session(path, transaction.scene_id) if path else None
    summary = _summary(transaction, path, state)
    return {**summary, "turns": _public_turns(state), "environment": _public_environment(state)}


def _public_turns(state: dict[str, Any] | None) -> list[dict[str, Any]]:
    directions = state.get("directions") if isinstance(state, dict) else []
    entries = state.get("actor_entries") if isinstance(state, dict) else []
    by_id = {str(item.get("entry_id") or ""): item for item in entries if isinstance(item, dict)}
    return [_public_turn(item, by_id) for item in directions if isinstance(item, dict)]


def _public_environment(state: dict[str, Any] | None) -> list[dict[str, str]]:
    environment = state.get("environment") if isinstance(state, dict) else None
    passages = environment.get("passages") if isinstance(environment, dict) else []
    return [
        {"beat_id": str(item.get("beat_id") or ""), "description": str(item.get("description") or "")}
        for item in passages if isinstance(item, dict) and item.get("description")
    ]


def _summary(transaction: SceneTransaction, path: Path | None, state: dict[str, Any] | None) -> dict[str, Any]:
    directions = state.get("directions") if isinstance(state, dict) else []
    return {
        "transaction_id": transaction.transaction_id, "scene_id": transaction.scene_id,
        "status": transaction.status.value, "objective": transaction.brief.objective,
        "turn_count": len(directions) if isinstance(directions, list) else 0,
        "updated_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat() if path else "",
    }


def _public_turn(direction: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ids = direction.get("entry_ids") if isinstance(direction.get("entry_ids"), list) else []
    return {
        "turn": int(direction.get("turn") or 0), "speaker": str(direction.get("next_speaker") or ""),
        "beat_id": str(direction.get("beat_id") or ""),
        "source": "creator-request" if direction.get("director_note") == "主创按需续演" else "rehearsal",
        "entries": [
            {"entry_id": entry_id, "spoken": str(by_id[entry_id].get("spoken") or ""),
             "first_person_action": str(by_id[entry_id].get("first_person_action") or "")}
            for entry_id in ids if isinstance(entry_id, str) and entry_id in by_id
        ],
    }


def _session_path(data_root: Path, transaction_id: str) -> Path | None:
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", transaction_id).strip("._")
    if not safe:
        return None
    directory = (data_root / "scene-transactions" / safe).resolve()
    if not directory.is_relative_to(data_root.resolve()) or not directory.is_dir():
        return None
    paths = list(directory.glob("performance-interaction-session-*.json"))
    return max(paths, key=lambda path: path.stat().st_mtime) if paths else None


def _read_session(path: Path, scene_id: str) -> dict[str, Any] | None:
    if path.stat().st_size > 2_000_000:
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) and value.get("scene_id") == scene_id else None


__all__ = ["scene_rehearsal_index", "scene_rehearsal_detail"]
