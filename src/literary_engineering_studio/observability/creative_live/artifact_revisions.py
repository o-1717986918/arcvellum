"""Build checkpoint revisions and text diffs from real artifact events."""

from __future__ import annotations

from difflib import unified_diff
from pathlib import Path
from typing import Any, Iterable

from .projector import project_runtime_event


def artifact_revisions(
    project_root: str | Path,
    raw_events: Iterable[dict[str, Any]],
    artifact_id: str,
) -> list[dict[str, Any]]:
    events = [
        project_runtime_event(item, project_root, source=str(item.get("source") or "runtime"))
        for item in raw_events
    ]
    content = ""
    revisions: list[dict[str, Any]] = []
    last_key: tuple[int, str, str] | None = None
    for event in events:
        artifact = event.get("artifact")
        if not isinstance(artifact, dict) or artifact.get("artifact_id") != artifact_id:
            continue
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        if isinstance(data.get("content"), str):
            content = data["content"]
        elif isinstance(data.get("delta"), str):
            content += data["delta"]
        key = (
            int(artifact.get("revision") or 0),
            str(artifact.get("identity") or ""),
            str(artifact.get("digest") or ""),
        )
        if key == last_key and revisions:
            revisions[-1]["content"] = content
            revisions[-1]["characters"] = len(content)
            revisions[-1]["event_id"] = event.get("event_id")
            revisions[-1]["at"] = event.get("at")
            continue
        revisions.append(
            {
                "revision_id": f"{artifact_id}:r{len(revisions) + 1}",
                "artifact_id": artifact_id,
                "event_id": event.get("event_id"),
                "at": event.get("at"),
                "identity": artifact.get("identity"),
                "digest": artifact.get("digest"),
                "characters": len(content) or int(artifact.get("characters") or 0),
                "content": content,
                "finding_refs": _finding_refs(data),
            }
        )
        last_key = key
    for index, revision in enumerate(revisions):
        before = "" if index == 0 else str(revisions[index - 1].get("content") or "")
        after = str(revision.get("content") or "")
        revision["diff"] = "".join(
            unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile="上一版",
                tofile="当前版",
                n=2,
            )
        )
    return revisions


def _finding_refs(data: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for key in ("finding_ids", "finding_refs", "issues", "revision_actions"):
        value = data.get(key)
        if isinstance(value, list):
            result.extend(str(item) for item in value if str(item).strip())
    return list(dict.fromkeys(result))[:80]


__all__ = ["artifact_revisions"]
