"""Reduce artifact deltas and checkpoints into bounded user-facing snapshots."""

from __future__ import annotations

from typing import Any


MAX_ACTIVE_ARTIFACT_CHARS = 2_000_000


def reduce_artifacts(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    artifacts: dict[str, dict[str, Any]] = {}
    for event in events:
        identity = event.get("artifact")
        if not isinstance(identity, dict):
            continue
        artifact_id = str(identity.get("artifact_id") or "")
        if not artifact_id:
            continue
        current = artifacts.setdefault(
            artifact_id,
            {
                **identity,
                "content": "",
                "updated_at": str(event.get("at") or ""),
                "source_event": str(event.get("event") or ""),
            },
        )
        current.update(identity)
        current["updated_at"] = str(event.get("at") or current.get("updated_at") or "")
        current["source_event"] = str(event.get("event") or "")
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        if isinstance(data.get("content"), str):
            current["content"] = data["content"][:MAX_ACTIVE_ARTIFACT_CHARS]
        elif isinstance(data.get("delta"), str):
            current["content"] = (
                str(current.get("content") or "") + data["delta"]
            )[-MAX_ACTIVE_ARTIFACT_CHARS:]
        current["truncated"] = len(str(current.get("content") or "")) >= MAX_ACTIVE_ARTIFACT_CHARS
    return sorted(artifacts.values(), key=lambda item: str(item.get("updated_at") or ""), reverse=True)


__all__ = ["MAX_ACTIVE_ARTIFACT_CHARS", "reduce_artifacts"]
