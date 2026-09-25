"""Restore lean scene draft revisions from transaction-local, read-only caches."""

from __future__ import annotations

from datetime import datetime, timezone
from difflib import unified_diff
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable

from .contracts import artifact_id as build_artifact_id, project_id


def merge_scene_revision_history(
    project_root: Path,
    data_root: Path,
    transactions: Iterable[Any],
    artifact_id: str,
    event_revisions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Add only cached drafts belonging to this project's exact scene artifact."""
    history = [dict(item) for item in event_revisions]
    transaction = next((item for item in transactions if _artifact_id(project_root, item) == artifact_id), None)
    if transaction is None:
        return history
    _restore_committed(history, project_root, str(transaction.scene_id))
    cache_root = _cache_root(data_root, str(transaction.transaction_id))
    if cache_root:
        _append_cached(history, cache_root, artifact_id)
    history.sort(key=lambda item: _timestamp(str(item.get("at") or "")))
    _apply_diffs(history)
    return history[-80:]


def _restore_committed(history: list[dict[str, Any]], project_root: Path, scene_id: str) -> None:
    final_text = _committed_text(project_root, scene_id)
    if not final_text:
        return
    for item in history:
        if item.get("identity") == "promoted" and not item.get("content"):
            item["content"] = final_text
            item["characters"] = len(final_text)


def _append_cached(history: list[dict[str, Any]], cache_root: Path, artifact_id: str) -> None:
    seen = {
        _digest(str(item.get("content") or ""))
        for item in history if item.get("content") and item.get("identity") != "promoted"
    }
    for path in _candidate_paths(cache_root):
        content = _cached_prose(path)
        digest = _digest(content)
        if not content or digest in seen:
            continue
        seen.add(digest)
        history.append({
            "revision_id": f"{artifact_id}:cache:{digest[:16]}",
            "artifact_id": artifact_id,
            "event_id": f"cache:{path.name}",
            "at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
            "identity": "candidate_written",
            "digest": digest,
            "characters": len(content),
            "content": content,
            "finding_refs": [],
        })


def _apply_diffs(history: list[dict[str, Any]]) -> None:
    for index, item in enumerate(history):
        before = str(history[index - 1].get("content") or "") if index else ""
        after = str(item.get("content") or "")
        item["diff"] = "".join(unified_diff(
            before.splitlines(keepends=True), after.splitlines(keepends=True),
            fromfile="上一版", tofile="当前版", n=2,
        ))[:240_000]


def _artifact_id(root: Path, transaction: Any) -> str:
    return build_artifact_id(
        project_id(root), f"drafts/scenes/{transaction.scene_id}.md", str(transaction.transaction_id),
    )


def _cache_root(data_root: Path, transaction_id: str) -> Path | None:
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", transaction_id).strip("._")
    if not safe:
        return None
    root = data_root.resolve()
    candidate = (root / "scene-transactions" / safe).resolve()
    return candidate if candidate.is_relative_to(root) and candidate.is_dir() else None


def _candidate_paths(root: Path) -> list[Path]:
    files = [*root.glob("creative_result_*.json"), *root.glob("revision_result_*.json")]
    return sorted(files, key=lambda path: path.stat().st_mtime)[:80]


def _cached_prose(path: Path) -> str:
    if path.stat().st_size > 4_000_000:
        return ""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    return str(value.get("prose") or "") if isinstance(value, dict) else ""


def _committed_text(root: Path, scene_id: str) -> str:
    receipt = root / "workflow" / "scene_commits" / f"{scene_id}.json"
    draft = root / "drafts" / "scenes" / f"{scene_id}.md"
    if not receipt.is_file() or not draft.is_file() or draft.stat().st_size > 4_000_000:
        return ""
    try:
        expected = str(json.loads(receipt.read_text(encoding="utf-8")).get("prose_sha256") or "")
        content = draft.read_text(encoding="utf-8").rstrip()
    except (OSError, ValueError):
        return ""
    return content if expected == _digest(content) else ""


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _timestamp(value: str) -> float:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc).timestamp() if parsed.tzinfo is None else parsed.timestamp()
    except ValueError:
        return 0.0


__all__ = ["merge_scene_revision_history"]
