"""Normalize heterogeneous Runtime events into the Creative Live contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..event_policy import canonical_runtime_event, classify_runtime_event
from .contracts import (
    ArtifactIdentity,
    CreativeLiveEvent,
    EventChannel,
    EventVisibility,
    artifact_id,
    project_id,
)
from .redaction import public_runtime_data


def project_runtime_event(
    raw: dict[str, Any],
    project_root: str | Path,
    *,
    source: str = "runtime",
) -> dict[str, Any]:
    event = canonical_runtime_event(str(raw.get("event") or "runtime.activity"))
    data = public_runtime_data(raw.get("data") if isinstance(raw.get("data"), dict) else {})
    if not isinstance(data, dict):
        data = {}
    sequence = max(0, int(raw.get("sequence") or 0))
    at = str(raw.get("at") or "")
    project = project_id(project_root)
    channel = _channel(event)
    visibility = _visibility(event)
    data.setdefault("title", _title(event, data))
    data.setdefault("message", _message(event, data))
    artifact = _artifact(project, event, data)
    event_id = str(data.get("runtime_event_id") or "") or _fallback_event_id(
        source, event, sequence, at, data
    )
    return CreativeLiveEvent.create(
        event_id=event_id,
        sequence=sequence,
        event=event if "." in event else f"runtime.{event}",
        channel=channel,
        visibility=visibility,
        durability=classify_runtime_event(event).value,
        at=at,
        project_id=project,
        run_id=str(data.get("run_id") or data.get("controller_id") or ""),
        session_id=str(data.get("session_id") or data.get("run_session_id") or ""),
        task_id=str(data.get("task_id") or ""),
        route=str(data.get("route") or ""),
        attempt_id=str(data.get("attempt_id") or ""),
        artifact=artifact,
        data=data,
    ).as_dict()


def _channel(event: str) -> EventChannel:
    if event.startswith(("artifact.", "file.", "writeback.")) or event == "mutation.receipt":
        return EventChannel.ARTIFACT
    if any(term in event for term in ("review", "validation", "preflight", "lint")):
        return EventChannel.REVIEW
    if "usage" in event:
        return EventChannel.USAGE
    if event.startswith(("agent.message", "runner.reasoning", "tool.")):
        return EventChannel.TRANSCRIPT
    if event.startswith(("autopilot.", "human.", "decision.", "release.")):
        return EventChannel.CONTROL
    return EventChannel.ACTIVITY


def _visibility(event: str) -> EventVisibility:
    if event.startswith("runner.reasoning"):
        return EventVisibility.ADVANCED
    if event.startswith("tool.") or event.startswith("runner."):
        return EventVisibility.ADVANCED
    if event in {"core.command_started", "core.command_failed"}:
        return EventVisibility.DIAGNOSTIC
    return EventVisibility.USER


def _artifact(project: str, event: str, data: dict[str, Any]) -> dict[str, Any] | None:
    receipt = data.get("receipt") if isinstance(data.get("receipt"), dict) else {}
    path = str(data.get("path") or receipt.get("target") or "")
    if not path or not (
        event.startswith(("artifact.", "file.", "writeback."))
        or event == "mutation.receipt"
    ):
        return None
    identity = str(data.get("identity") or _identity(event, {**data, **receipt}))
    attempt = str(data.get("attempt_id") or data.get("run_id") or receipt.get("run_id") or "")
    return {
        "artifact_id": artifact_id(project, path, attempt),
        "path": path.replace("\\", "/"),
        "kind": str(data.get("kind") or "agent-authored"),
        "format": str(data.get("format") or _format(path)),
        "identity": identity,
        "revision": max(0, int(data.get("revision") or 0)),
        "digest": str(data.get("sha256") or data.get("digest") or receipt.get("result_sha256") or ""),
        "characters": max(0, int(data.get("characters") or 0)),
    }


def _identity(event: str, data: dict[str, Any]) -> str:
    if event.startswith("artifact.preview"):
        return ArtifactIdentity.STREAMING_PREVIEW.value
    if event == "artifact.checkpoint.written" or event == "file.changed":
        return ArtifactIdentity.CANDIDATE_WRITTEN.value
    if event == "writeback.approved":
        return ArtifactIdentity.PROMOTED.value
    if event == "mutation.receipt":
        action = str(data.get("action") or "")
        effect = str(data.get("formal_effect") or "")
        if action == "formal_promoted" or effect == "formal":
            return ArtifactIdentity.PROMOTED.value
        if action in {"writeback_rolled_back", "preflight_rejected"}:
            return ArtifactIdentity.REJECTED.value
        if str(data.get("preflight_status") or "") == "pass":
            return ArtifactIdentity.DETERMINISTIC_PREFLIGHT_PASSED.value
    if event.endswith(("failed", "rejected", "denied")) or data.get("validation_passed") is False:
        return ArtifactIdentity.VALIDATION_FAILED.value
    return ArtifactIdentity.CANDIDATE_WRITTEN.value


def _title(event: str, data: dict[str, Any]) -> str:
    if event.startswith("artifact.preview"):
        return "正文正在形成" if data.get("preview_mode") == "prose_stream" else "创作产物正在形成"
    if event == "artifact.checkpoint.written":
        return "候选稿已写入"
    if event == "validation.passed":
        return "确定性检查通过"
    if event == "tool.started":
        return "正在使用创作工具"
    if event == "usage.updated":
        return "本轮用量已更新"
    if event.startswith("runner.reasoning"):
        return "主创正在思考"
    if event == "agent.message.delta":
        return "主创正在说明"
    if event.startswith("task."):
        return "创作任务推进"
    return "创作现场更新"


def _message(event: str, data: dict[str, Any]) -> str:
    if event.startswith("artifact.preview"):
        return "候选内容仍在生成，尚未成为正式正文。"
    if event == "artifact.checkpoint.written":
        return "候选产物已完整写入，等待正式检查。"
    if event == "validation.passed":
        return "本轮机器可验证条件已经满足。"
    if event == "tool.started":
        return f"正在执行 {data.get('tool') or '当前工具'}。"
    if event == "tool.completed":
        return f"{data.get('tool') or '当前工具'} 已完成。"
    if event == "runner.reasoning.activity":
        return "模型仍在进行当前任务的推理。"
    return str(data.get("message") or data.get("detail") or "项目状态已有新变化。")


def _format(path: str) -> str:
    suffix = Path(path).suffix.casefold()
    return {".md": "markdown", ".json": "json", ".yaml": "yaml", ".yml": "yaml"}.get(suffix, "text")


def _fallback_event_id(
    source: str, event: str, sequence: int, at: str, data: dict[str, Any]
) -> str:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
    value = "\0".join((source, event, str(sequence), at, payload))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


__all__ = ["project_runtime_event"]
