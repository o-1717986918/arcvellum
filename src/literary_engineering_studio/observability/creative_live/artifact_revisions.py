"""Build checkpoint revisions and text diffs from real artifact events."""

from __future__ import annotations

from difflib import unified_diff
from pathlib import Path
from typing import Any, Iterable

from .projector import project_runtime_event


MAX_REVISIONS = 80
MAX_DIFF_CHARS = 240_000


def artifact_revisions(
    project_root: str | Path,
    raw_events: Iterable[dict[str, Any]],
    artifact_id: str,
) -> list[dict[str, Any]]:
    events = _project_events(project_root, raw_events)
    revisions = _collect_revisions(events, artifact_id)
    _attach_review_evidence(revisions, events)
    revisions = revisions[-MAX_REVISIONS:]
    _attach_diffs(revisions)
    return revisions


def _project_events(
    project_root: str | Path, raw_events: Iterable[dict[str, Any]]
) -> list[dict[str, Any]]:
    return [
        project_runtime_event(item, project_root, source=str(item.get("source") or "runtime"))
        for item in raw_events
    ]


def _collect_revisions(
    events: list[dict[str, Any]], artifact_id: str
) -> list[dict[str, Any]]:
    content = ""
    revisions: list[dict[str, Any]] = []
    last_key: tuple[int, str, str] | None = None
    for event in events:
        artifact = _matching_artifact(event, artifact_id)
        if artifact is None:
            continue
        data = _event_data(event)
        content = _next_content(content, data)
        key = _revision_key(artifact)
        if key == last_key and revisions:
            _refresh_revision(revisions[-1], event, content)
            continue
        _supersede_preview(revisions)
        revisions.append(_revision(artifact_id, len(revisions) + 1, event, artifact, data, content))
        last_key = key
    return revisions


def _matching_artifact(event: dict[str, Any], artifact_id: str) -> dict[str, Any] | None:
    artifact = event.get("artifact")
    if not isinstance(artifact, dict) or artifact.get("artifact_id") != artifact_id:
        return None
    return artifact


def _event_data(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data")
    return data if isinstance(data, dict) else {}


def _next_content(current: str, data: dict[str, Any]) -> str:
    if isinstance(data.get("content"), str):
        return data["content"]
    if isinstance(data.get("delta"), str):
        return current + data["delta"]
    return current


def _revision_key(artifact: dict[str, Any]) -> tuple[int, str, str]:
    return (
        int(artifact.get("revision") or 0),
        str(artifact.get("identity") or ""),
        str(artifact.get("digest") or ""),
    )


def _refresh_revision(revision: dict[str, Any], event: dict[str, Any], content: str) -> None:
    revision.update(content=content, characters=len(content), event_id=event.get("event_id"), at=event.get("at"))


def _supersede_preview(revisions: list[dict[str, Any]]) -> None:
    if revisions and revisions[-1].get("identity") == "streaming_preview":
        revisions[-1]["identity"] = "superseded"


def _revision(
    artifact_id: str, number: int, event: dict[str, Any], artifact: dict[str, Any],
    data: dict[str, Any], content: str,
) -> dict[str, Any]:
    return {
        "revision_id": f"{artifact_id}:r{number}", "artifact_id": artifact_id,
        "event_id": event.get("event_id"), "at": event.get("at"),
        "identity": artifact.get("identity"), "digest": artifact.get("digest"),
        "characters": len(content) or int(artifact.get("characters") or 0), "content": content,
        "finding_refs": _finding_refs(data), "attempt_id": event.get("attempt_id"),
        "task_id": event.get("task_id"), "route": event.get("route"),
    }


def _attach_diffs(revisions: list[dict[str, Any]]) -> None:
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
        )[:MAX_DIFF_CHARS]


def _attach_review_evidence(
    revisions: list[dict[str, Any]], events: list[dict[str, Any]]
) -> None:
    by_digest = {
        str(item.get("digest") or ""): item
        for item in revisions
        if str(item.get("digest") or "")
    }
    for event in events:
        if event.get("channel") != "review":
            continue
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        digest = str(
            data.get("candidate_digest")
            or data.get("candidate_sha256")
            or data.get("source_candidate_sha256")
            or ""
        )
        revision = by_digest.get(digest)
        if revision is None:
            continue
        revision["finding_refs"] = list(dict.fromkeys([
            *revision.get("finding_refs", []),
            *_finding_refs(data),
        ]))[:80]
        revision["review_event_id"] = event.get("event_id")
        if data.get("passed") is True and revision.get("identity") not in {"promoted", "state_and_canon_applied"}:
            revision["identity"] = "semantic_review_passed"


def _finding_refs(data: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for key in ("finding_ids", "finding_refs", "issues", "revision_actions"):
        value = data.get(key)
        if isinstance(value, list):
            result.extend(str(item) for item in value if str(item).strip())
    return list(dict.fromkeys(result))[:80]


__all__ = ["artifact_revisions"]
