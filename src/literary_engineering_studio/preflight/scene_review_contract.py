"""Deterministic semantic checks for independent scene reviews."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..contracts import TaskPackage
from ..sandbox import SandboxManifest
from .common import PreflightIssue


def validate_scene_review_contract(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    """Bind a review verdict to its schema and exact prose candidate."""

    if task.current_state not in {"candidate-review", "agent-review-task"}:
        return
    review_rel = _review_output(task)
    payload = _read_review(sandbox.workspace / Path(review_rel)) if review_rel else None
    if payload is None:
        return
    _append_schema_and_semantic_issues(payload, review_rel, issues)
    candidate_rel = _candidate_source(task)
    candidate_path = sandbox.workspace / Path(candidate_rel)
    if candidate_rel and candidate_path.is_file():
        _append_candidate_binding_issues(
            payload, review_rel, candidate_rel, candidate_path, issues
        )


def _review_output(task: TaskPackage) -> str:
    return next(
        (
            relative
            for relative in task.expected_outputs
            if relative.endswith(".json")
            and "scene_review" in relative
            and not relative.endswith(".agent_completion.json")
        ),
        "",
    )


def _read_review(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _append_schema_and_semantic_issues(
    payload: dict[str, Any],
    review_rel: str,
    issues: list[PreflightIssue],
) -> None:
    from literary_engineering_studio_engine.literary.review.resolution import (
        review_semantic_consistency_issues,
    )
    from literary_engineering_studio_engine.prompting.agents.schema import validate_payload

    schema_errors, _warnings = validate_payload(payload, "scene_review.v1")
    for error in schema_errors:
        issues.append(
            PreflightIssue(
                "scene-review-schema-invalid",
                f"{review_rel}#{error.get('path') or 'schema'}",
                str(error.get("message") or "scene review schema validation failed"),
                "读取 CLI Protected Outputs 中的 scene review sidecar 和 scene_review.v1 schema；"
                "保留真实审查结论，仅补齐缺失字段、正确类型与固定 schema 值。",
            )
        )
    for message in review_semantic_consistency_issues(payload):
        issues.append(
            PreflightIssue(
                "scene-review-verdict-inconsistent",
                f"{review_rel}#conclusion",
                message,
                "重新判断审查语义：低于阈值且 blocks_pass=false 的观察保留在 clean pass 的 warning/style_notes；"
                "只有精确、可执行且尚未解决的问题才能进入 revision_actions 并使用 pass_with_notes/revise_required。",
            )
        )


def _candidate_source(task: TaskPackage) -> str:
    candidate = str(task.payload.get("candidate") or "").replace("\\", "/").strip()
    if candidate:
        return candidate
    return next(
        (
            relative
            for relative in task.source_paths
            if relative.replace("\\", "/").startswith("drafts/candidates/")
            and relative.endswith(".md")
        ),
        "",
    )


def _append_candidate_binding_issues(
    payload: dict[str, Any],
    review_rel: str,
    candidate_rel: str,
    candidate_path: Path,
    issues: list[PreflightIssue],
) -> None:
    expected_digest = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
    if str(payload.get("candidate_sha256") or "") != expected_digest:
        issues.append(
            PreflightIssue(
                "scene-review-candidate-digest-mismatch",
                f"{review_rel}#candidate_sha256",
                "candidate_sha256 未精确对应本任务候选正文。",
                "从任务包的候选正文重新计算或复制精确 SHA-256；不得写示例值、旧值或自造摘要。",
            )
        )
    source_paths = payload.get("source_paths")
    normalized = {
        str(item).replace("\\", "/")
        for item in source_paths
    } if isinstance(source_paths, list) else set()
    if candidate_rel not in normalized:
        issues.append(
            PreflightIssue(
                "scene-review-candidate-source-missing",
                f"{review_rel}#source_paths",
                "source_paths 必须引用本任务的精确候选正文。",
                f"在 source_paths 中保留 `{candidate_rel}`；不要引用其他候选、正式草稿或笼统目录。",
            )
        )


__all__ = ["validate_scene_review_contract"]
