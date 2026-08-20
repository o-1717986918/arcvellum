"""Candidate asset schema and metadata validation."""

from __future__ import annotations

import json
from pathlib import Path

from ..contracts import TaskPackage
from ..sandbox import SandboxManifest
from .common import PreflightIssue


def validate_asset_candidate(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    """Validate one task-owned asset candidate without changing it."""

    if not _requires_asset_candidate_validation(task):
        return
    candidate = _candidate_relative_path(task)
    payload = _read_candidate(sandbox, candidate)
    if payload is None:
        return
    schema_name = _asset_schema_name(task, payload)
    if not schema_name:
        asset_type = str(task.payload.get("asset_type") or payload.get("asset_type") or "").strip()
        issues.append(
            PreflightIssue(
                "unknown-asset-schema",
                candidate,
                f"无法确定资产类型 `{asset_type or 'missing'}` 对应的 schema。",
                "读取任务包中的 asset_type 和 Source Artifacts，按声明的资产类型重写候选 JSON。",
            )
        )
        return
    _append_schema_issues(payload, schema_name, candidate, issues)
    _append_metadata_issues(payload, candidate, issues)


def _requires_asset_candidate_validation(task: TaskPackage) -> bool:
    gates = " ".join(str(item) for item in task.payload.get("validation_gates") or []).lower()
    return (
        task.payload.get("task_type") == "platform-agent-asset-creation"
        or "candidate schema validates" in gates
    )


def _candidate_relative_path(task: TaskPackage) -> str:
    candidate = str(task.payload.get("candidate") or "").replace("\\", "/").strip()
    if candidate:
        return candidate
    return next(
        (
            relative
            for relative in task.expected_outputs
            if relative.endswith(".json") and not relative.endswith(".agent_completion.json")
        ),
        "",
    )


def _read_candidate(sandbox: SandboxManifest, relative: str) -> dict[str, object] | None:
    if not relative:
        return None
    path = sandbox.workspace / Path(relative)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _asset_schema_name(task: TaskPackage, payload: dict[str, object]) -> str:
    from literary_engineering_studio_engine.public.literary import ASSET_SCHEMA_NAMES

    asset_type = str(task.payload.get("asset_type") or payload.get("asset_type") or "").strip()
    return ASSET_SCHEMA_NAMES.get(asset_type, "")


def _append_schema_issues(
    payload: dict[str, object],
    schema_name: str,
    candidate: str,
    issues: list[PreflightIssue],
) -> None:
    from literary_engineering_studio_engine.public.prompting import validate_payload

    schema_errors, _warnings = validate_payload(payload, schema_name)
    for item in schema_errors:
        field = str(item.get("path") or "schema")
        message = str(item.get("message") or "schema validation failed")
        issues.append(
            PreflightIssue(
                "asset-schema-invalid",
                f"{candidate}#{field}",
                message,
                f"按 `{schema_name}` 修复字段 `{field}`；字段必须位于 JSON 根对象且类型、固定值与 schema 完全一致。",
            )
        )


def _append_metadata_issues(
    payload: dict[str, object],
    candidate: str,
    issues: list[PreflightIssue],
) -> None:
    metadata_contract = {
        "candidate_id": str,
        "risks": list,
        "source_paths": list,
        "promotion_notes": str,
    }
    for field, expected_type in metadata_contract.items():
        value = payload.get(field)
        valid = isinstance(value, expected_type) and (expected_type is not str or bool(value.strip()))
        if valid:
            continue
        expected_label = "字符串" if expected_type is str else "数组"
        issues.append(
            PreflightIssue(
                "asset-metadata-invalid",
                f"{candidate}#{field}",
                f"字段 `{field}` 必须是非空{expected_label}。",
                f"把 `{field}` 改为{expected_label}；不要用对象替代 schema 要求的字符串。",
            )
        )
