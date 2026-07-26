"""Worker preflight for evidence-bound Project Archaeology outputs."""

from __future__ import annotations

import json
from pathlib import Path

from ..contracts import TaskPackage
from ..sandbox import SandboxManifest
from .common import PreflightIssue
from literary_engineering_studio_engine.literary.ingest import (
    read_chunk_extraction,
    validate_chunk_extraction,
)


def validate_archaeology_chunk_output(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    if task.route != "source-ingest" or task.current_state != "chunk-extraction-agent-task":
        return
    context = _chunk_context(task, sandbox, issues)
    if context is None:
        return
    manifest, chunk, output_rel = context
    output, errors = read_chunk_extraction(sandbox.workspace / output_rel)
    if output:
        errors.extend(
            validate_chunk_extraction(
                output,
                work_id=str(manifest.get("work_id") or ""),
                chunk=chunk,
                evidence_revision=_evidence_revision(manifest),
                root=sandbox.workspace,
            )
        )
    _append_contract_issues(issues, output_rel, errors)


def _chunk_context(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> tuple[dict[str, object], dict[str, object], str] | None:
    manifest_path = _source_manifest_path(task, sandbox)
    if manifest_path is None:
        _append_identity_issue(
            issues,
            "",
            "chunk extraction task does not declare its source manifest",
            "重新领取当前任务；不得在缺少 source manifest 的任务包中提交考古提取。",
        )
        return None
    manifest = _read_object(manifest_path)
    manifest_rel = manifest_path.relative_to(sandbox.workspace).as_posix()
    if not manifest:
        _append_identity_issue(
            issues,
            manifest_rel,
            "source manifest is missing or is not valid UTF-8 JSON",
            "重新领取当前任务，确认 Studio 已将 source manifest 放入沙箱。",
        )
        return None
    chunk_id = str(task.payload.get("chunk_id") or "")
    chunk = _manifest_chunk(manifest, chunk_id)
    if not chunk:
        message = (
            f"source manifest does not declare chunk_id: {chunk_id}"
            if chunk_id
            else "chunk extraction task is missing chunk_id"
        )
        _append_identity_issue(
            issues,
            manifest_rel,
            message,
            "重新导入源作品或领取与当前 source manifest 匹配的任务。",
        )
        return None
    return manifest, chunk, _semantic_output(task)


def _manifest_chunk(
    manifest: dict[str, object],
    chunk_id: str,
) -> dict[str, object]:
    return next(
        (
            item
            for item in manifest.get("chunks") or []
            if isinstance(item, dict)
            and str(item.get("chunk_id") or "") == chunk_id
        ),
        {},
    )


def _semantic_output(task: TaskPackage) -> str:
    return next(
        (
            item
            for item in task.expected_outputs
            if item.endswith(".json") and not item.endswith(".agent_completion.json")
        ),
        "",
    )


def _append_contract_issues(
    issues: list[PreflightIssue],
    output_rel: str,
    errors: list[str],
) -> None:
    for message in errors:
        issues.append(
            PreflightIssue(
                "archaeology-chunk-contract",
                output_rel,
                message,
                (
                    "按 chunk task package 重写当前 JSON；只使用当前 chunk 的 evidence ids，"
                    "保留 unknowns 与 contradiction_notes，不修改其他输出。"
                ),
            )
        )


def _append_identity_issue(
    issues: list[PreflightIssue],
    path: str,
    message: str,
    repair: str,
) -> None:
    issues.append(
        PreflightIssue(
            "archaeology-chunk-identity",
            path,
            message,
            repair,
        )
    )


def _source_manifest_path(
    task: TaskPackage,
    sandbox: SandboxManifest,
) -> Path | None:
    relative = next(
        (
            item
            for item in task.source_paths
            if item.replace("\\", "/").endswith("/source_manifest.json")
        ),
        "",
    )
    return sandbox.workspace / relative if relative else None


def _evidence_revision(manifest: dict[str, object]) -> str:
    evidence = manifest.get("evidence_index")
    return str(evidence.get("revision") or "") if isinstance(evidence, dict) else ""


def _read_object(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
