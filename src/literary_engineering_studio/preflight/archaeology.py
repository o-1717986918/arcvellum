"""Worker preflight for evidence-bound Project Archaeology outputs."""

from __future__ import annotations

import json
from pathlib import Path

from ..contracts import TaskPackage
from ..sandbox import SandboxManifest
from .common import PreflightIssue
from literary_engineering_studio_engine.public.literary import (
    DOMAIN_REVIEW_SCHEMA,
    IDENTITY_RESOLUTION_SCHEMA,
    RECONSTRUCTION_CANDIDATE_SCHEMA,
    read_chunk_extraction,
    validate_domain_review,
    validate_identity_resolution,
    validate_reconstruction_candidate,
    validate_chunk_extraction,
)
from literary_engineering_studio_engine.public.literary import canonical_digest


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


def canonicalize_archaeology_metadata(
    task: TaskPackage,
    sandbox: SandboxManifest,
) -> list[dict[str, str]]:
    state = task.current_state
    if task.route != "source-ingest" or state not in {
        "archaeology-resolution-agent-task",
        "archaeology-reconstruction-agent-task",
        "archaeology-domain-review-agent-task",
    }:
        return []
    relative = _semantic_output(task)
    path = sandbox.workspace / relative
    payload = _read_object(path)
    if not payload:
        return []
    manifest = _source_manifest(task, sandbox)
    aggregate = _source_object(task, sandbox, "aggregate.json")
    field, expected = _archaeology_expected_metadata(
        task,
        sandbox,
        manifest=manifest,
        aggregate=aggregate,
    )
    changed = _apply_owned_metadata(payload, expected)
    changed = _apply_revision(payload) or changed
    if not changed:
        return []
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return [{"path": relative, "kind": field}]


def _archaeology_expected_metadata(
    task: TaskPackage,
    sandbox: SandboxManifest,
    *,
    manifest: dict[str, object],
    aggregate: dict[str, object],
) -> tuple[str, dict[str, object]]:
    state = task.current_state
    field = {
        "archaeology-resolution-agent-task": "archaeology_resolution",
        "archaeology-reconstruction-agent-task": "archaeology_reconstruction",
        "archaeology-domain-review-agent-task": "archaeology_domain_review",
    }[state]
    owned = task.payload.get("system_owned_fields")
    owned = owned if isinstance(owned, dict) else {}
    expected = owned.get(field)
    expected = dict(expected) if isinstance(expected, dict) else {}
    expected.update(
        _state_machine_metadata(
            task,
            sandbox,
            manifest=manifest,
            aggregate=aggregate,
        )
    )
    return field, expected


def _state_machine_metadata(
    task: TaskPackage,
    sandbox: SandboxManifest,
    *,
    manifest: dict[str, object],
    aggregate: dict[str, object],
) -> dict[str, object]:
    if task.current_state == "archaeology-resolution-agent-task":
        return {
            "schema": IDENTITY_RESOLUTION_SCHEMA,
            "aggregate_revision": str(aggregate.get("revision") or ""),
            "evidence_revision": _evidence_revision(manifest),
            "status": "complete",
        }
    if task.current_state == "archaeology-reconstruction-agent-task":
        resolution = _source_object(task, sandbox, "identity_resolution.json")
        return {
            "schema": RECONSTRUCTION_CANDIDATE_SCHEMA,
            "aggregate_revision": str(aggregate.get("revision") or ""),
            "resolution_revision": str(resolution.get("revision") or ""),
            "status": "candidate",
        }
    candidate = _source_object(task, sandbox, "candidate_project.json")
    return {
        "schema": DOMAIN_REVIEW_SCHEMA,
        "candidate_revision": str(candidate.get("revision") or ""),
    }


def _apply_owned_metadata(
    payload: dict[str, object],
    expected: dict[str, object],
) -> bool:
    changed = False
    for key, value in expected.items():
        if payload.get(key) != value:
            payload[key] = value
            changed = True
    return changed


def _apply_revision(payload: dict[str, object]) -> bool:
    revision = canonical_digest(payload)
    if payload.get("revision") == revision:
        return False
    payload["revision"] = revision
    return True


def validate_archaeology_reconstruction_output(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    state = task.current_state
    if task.route != "source-ingest" or state not in {
        "archaeology-resolution-agent-task",
        "archaeology-reconstruction-agent-task",
        "archaeology-domain-review-agent-task",
    }:
        return
    manifest = _source_manifest(task, sandbox)
    aggregate = _source_object(task, sandbox, "aggregate.json")
    output_rel = _semantic_output(task)
    payload = _read_object(sandbox.workspace / output_rel)
    if not manifest or not payload:
        return
    if state == "archaeology-resolution-agent-task":
        errors = validate_identity_resolution(
            payload,
            manifest=manifest,
            aggregate=aggregate,
        )
    elif state == "archaeology-reconstruction-agent-task":
        resolution = _source_object(task, sandbox, "identity_resolution.json")
        errors = validate_reconstruction_candidate(
            payload,
            manifest=manifest,
            aggregate=aggregate,
            resolution=resolution,
        )
    else:
        candidate = _source_object(task, sandbox, "candidate_project.json")
        errors = validate_domain_review(
            payload,
            manifest=manifest,
            candidate=candidate,
        )
        if str(payload.get("status") or "") != "pass":
            errors.append(
                "archaeology domain review must pass before materialization"
            )
    for message in errors:
        issues.append(
            PreflightIssue(
                "archaeology-reconstruction-contract",
                output_rel,
                message,
                (
                    "按当前 task package 修复证据引用、覆盖集合、模式策略和审查结论；"
                    "保留未决项，不要修改机器拥有的 schema、revision 或来源身份。"
                ),
            )
        )


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


def _source_manifest(
    task: TaskPackage,
    sandbox: SandboxManifest,
) -> dict[str, object]:
    path = _source_manifest_path(task, sandbox)
    return _read_object(path) if path is not None else {}


def _source_object(
    task: TaskPackage,
    sandbox: SandboxManifest,
    filename: str,
) -> dict[str, object]:
    relative = next(
        (
            item
            for item in task.source_paths
            if item.replace("\\", "/").endswith(f"/{filename}")
        ),
        "",
    )
    return _read_object(sandbox.workspace / relative) if relative else {}


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
