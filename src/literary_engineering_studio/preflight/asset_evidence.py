"""Exact candidate-content evidence shared by asset preflight stages."""

from __future__ import annotations

import hashlib
from pathlib import Path

from ..contracts import TaskPackage
from ..sandbox import SandboxManifest
from .common import PreflightIssue


def candidate_digest(
    task: TaskPackage,
    sandbox: SandboxManifest,
    payload: dict[str, object] | None = None,
) -> tuple[str, str]:
    candidate_rel = str(
        task.payload.get("candidate") or (payload or {}).get("candidate") or ""
    ).replace("\\", "/").strip()
    candidate = sandbox.workspace / Path(candidate_rel) if candidate_rel else None
    digest = (
        hashlib.sha256(candidate.read_bytes()).hexdigest()
        if candidate is not None and candidate.is_file()
        else ""
    )
    return candidate_rel, digest


def review_digest_issues(
    task: TaskPackage,
    sandbox: SandboxManifest,
    payload: dict[str, object],
    review_rel: str,
) -> list[PreflightIssue]:
    _candidate, expected = candidate_digest(task, sandbox, payload)
    reviewed = str(payload.get("candidate_sha256") or "").strip().lower()
    if not reviewed:
        return [
            PreflightIssue(
                "asset-review-invalid",
                f"{review_rel}#candidate_sha256",
                "字段 `candidate_sha256` 必须绑定当前候选内容。",
                "不要自行估算；Studio Worker 会依据任务包中的候选文件写入当前 SHA-256。",
            )
        ]
    if expected and reviewed != expected:
        return [
            PreflightIssue(
                "asset-review-invalid",
                f"{review_rel}#candidate_sha256",
                "candidate_sha256 未精确对应本任务的当前候选资产。",
                "重新读取候选文件并执行独立审查；不得沿用旧候选的审查结论。",
            )
        ]
    return []


def review_digest_value(
    task: TaskPackage,
    sandbox: SandboxManifest,
    payload: dict[str, object],
    declared: object,
) -> str:
    current = candidate_digest(task, sandbox, payload)[1]
    return current or str(declared or "")


def review_machine_fields(
    task: TaskPackage,
    sandbox: SandboxManifest,
    payload: dict[str, object],
    contract: dict[str, object],
    *,
    candidate: str,
    candidate_id: str,
    asset_type: str,
) -> dict[str, object]:
    return {
        "schema": str(contract.get("schema") or "literary-engineering-workbench/candidate-asset-review/v0.1"),
        "candidate": str(contract.get("candidate") or candidate),
        "candidate_id": str(contract.get("candidate_id") or candidate_id),
        "asset_type": str(contract.get("asset_type") or asset_type),
        "candidate_sha256": review_digest_value(task, sandbox, payload, contract.get("candidate_sha256")),
    }
