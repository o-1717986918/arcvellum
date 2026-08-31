"""Project bounded, digest-bound review files into the live read model."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


MAX_REVIEW_BYTES = 2_000_000


def project_review_artifacts(
    project_root: str | Path, events: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    root = Path(project_root).resolve()
    projected: list[dict[str, Any]] = []
    for event, artifact, relative, path in _review_candidates(root, events):
        payload = _load_review(path)
        if payload is not None:
            projected.append(_project_review(event, artifact, relative, payload))
    return list(reversed(projected))


def _review_candidates(
    root: Path, events: list[dict[str, Any]]
) -> list[tuple[dict[str, Any], dict[str, Any], str, Path]]:
    result: list[tuple[dict[str, Any], dict[str, Any], str, Path]] = []
    seen: set[str] = set()
    for event in reversed(events):
        artifact = event.get("artifact")
        if not isinstance(artifact, dict):
            continue
        relative = str(artifact.get("path") or "").replace("\\", "/")
        if relative in seen or not _is_review_json(relative):
            continue
        seen.add(relative)
        path = _bounded_review_path(root, relative)
        if path is not None:
            result.append((event, artifact, relative, path))
    return result


def _bounded_review_path(root: Path, relative: str) -> Path | None:
    path = (root / relative).resolve()
    if root not in path.parents or not path.is_file():
        return None
    try:
        return path if path.stat().st_size <= MAX_REVIEW_BYTES else None
    except OSError:
        return None


def _load_review(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _project_review(
    event: dict[str, Any], artifact: dict[str, Any], relative: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    conclusion = str(payload.get("conclusion") or payload.get("status") or "").strip()
    candidate_digest = _candidate_digest(payload)
    findings = _findings(payload)
    digest = str(artifact.get("digest") or "")
    return {
        "schema": "arcvellum/creative-live-event/v1",
        "event_id": "review-file:" + hashlib.sha256(
            f"{relative}\0{digest}\0{conclusion}".encode("utf-8")
        ).hexdigest()[:24],
        "sequence": int(event.get("sequence") or 0),
        "event": "review.artifact.projected", "channel": "review",
        "visibility": "user", "durability": "durable", "at": str(event.get("at") or ""),
        "project_id": str(event.get("project_id") or ""), "run_id": str(event.get("run_id") or ""),
        "session_id": str(event.get("session_id") or ""), "task_id": str(event.get("task_id") or ""),
        "route": str(event.get("route") or ""), "attempt_id": str(event.get("attempt_id") or ""),
        "artifact": artifact,
        "data": {
            "title": _title(conclusion), "message": _summary(payload, conclusion, len(findings)),
            "status": conclusion, "passed": conclusion == "pass",
            "candidate_digest": candidate_digest,
            "finding_ids": [item["id"] for item in findings], "findings": findings,
        },
    }


def _candidate_digest(payload: dict[str, Any]) -> str:
    for key in ("candidate_sha256", "candidate_digest", "source_candidate_sha256"):
        value = str(payload.get(key) or "").strip().lower()
        if value:
            return value
    return ""


def apply_review_identities(
    artifacts: list[dict[str, Any]], reviews: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    passed = {
        str((item.get("data") or {}).get("candidate_digest") or "")
        for item in reviews
        if (item.get("data") or {}).get("passed") is True
    }
    for artifact in artifacts:
        if artifact.get("identity") in {"promoted", "state_and_canon_applied"}:
            continue
        if str(artifact.get("digest") or "") in passed:
            artifact["identity"] = "semantic_review_passed"
    return artifacts


def _is_review_json(relative: str) -> bool:
    lowered = relative.casefold()
    return lowered.startswith("reviews/") and lowered.endswith(".json") and "review" in lowered


def _findings(payload: dict[str, Any]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for key in ("blocking_issues", "findings", "revision_actions", "recommendations"):
        values = payload.get(key)
        if not isinstance(values, list):
            continue
        for index, value in enumerate(values):
            if isinstance(value, dict):
                identity = str(value.get("id") or f"{key}-{index + 1}")
                message = str(value.get("message") or value.get("action") or value.get("summary") or "")
            else:
                identity, message = f"{key}-{index + 1}", str(value)
            if message.strip():
                result.append({"id": identity, "message": message[:600]})
    return result[:80]


def _title(conclusion: str) -> str:
    return {
        "pass": "语义审读通过",
        "pass_with_notes": "审读提出修订意见",
        "revise_required": "正文需要修订",
        "reject": "本轮正文未通过审读",
    }.get(conclusion, "审读结论已形成")


def _summary(payload: dict[str, Any], conclusion: str, findings: int) -> str:
    summary = str(payload.get("summary") or "").strip()
    if summary:
        return summary[:1200]
    if conclusion == "pass":
        return "审读证据与当前候选摘要精确匹配，可以进入后续正式门禁。"
    if findings:
        return f"审读记录了 {findings} 项需要处理的具体意见。"
    return "审读结论已经写入项目证据。"


__all__ = ["apply_review_identities", "project_review_artifacts"]
