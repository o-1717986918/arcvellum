"""Coordinate portable plan audit files with the durable metadata index."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

from literary_engineering_studio_engine.foundation.atomic_io import (
    atomic_write_batch,
)

from .audit_integrity import validate_revision_chain, verify_semantic_chain
from .contracts import CompiledTaskGraph, CreativeExecutionPlan, to_primitive
from .lint import PlanLintResult
from .plan_index import CreativePlanIndex
from .simulator import PlanSimulationResult


@dataclass(frozen=True)
class OrchestrationAuditArtifacts:
    plan_id: str
    revision: int
    revision_digest: str
    root: str
    files: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class _PreparedShadowRevision:
    revision_name: str
    relative_root: Path
    rendered: dict[str, str]
    revision_digest: str
    relative_files: tuple[tuple[str, str], ...]


def persist_shadow_revision(
    project_root: Path,
    *,
    store: CreativePlanIndex,
    candidate_payload: dict[str, Any],
    plan: CreativeExecutionPlan,
    graph: CompiledTaskGraph,
    lint_result: PlanLintResult,
    simulation: PlanSimulationResult,
) -> OrchestrationAuditArtifacts:
    root = project_root.expanduser().resolve()
    validate_revision_chain(
        candidate_payload,
        plan,
        graph,
        lint_result,
        simulation,
    )
    prepared = _prepare_shadow_revision(
        candidate_payload,
        plan=plan,
        graph=graph,
        lint_result=lint_result,
        simulation=simulation,
    )
    record = _index_record(
        root,
        plan=plan,
        graph=graph,
        lint_result=lint_result,
        simulation=simulation,
        revision_digest=prepared.revision_digest,
        files=dict(prepared.relative_files),
        revision_name=prepared.revision_name,
    )
    reserved = store.reserve_creative_plan_revision(record)
    if str(reserved.get("artifact_state") or "") == "ready":
        verify_persisted_revision(root, reserved)
    else:
        entries = {
            root / prepared.relative_root / name: text
            for name, text in prepared.rendered.items()
        }
        atomic_write_batch(entries)
        store.finalize_creative_plan_revision(
            plan.plan_id,
            plan.revision,
            digest=prepared.revision_digest,
        )
    return OrchestrationAuditArtifacts(
        plan_id=plan.plan_id,
        revision=plan.revision,
        revision_digest=prepared.revision_digest,
        root=prepared.relative_root.as_posix(),
        files=prepared.relative_files,
    )


def activate_persisted_revision(
    project_root: Path,
    *,
    store: CreativePlanIndex,
    plan_id: str,
    revision: int,
    expected_active_revision: int,
    current_project_fingerprint: str,
) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    plan_record = store.read_creative_plan(plan_id)
    expected_project = str(root).replace("\\", "/").rstrip("/").casefold()
    if str(plan_record.get("project_root") or "") != expected_project:
        raise RuntimeError("creative plan belongs to a different project")
    revision_record = store.read_creative_plan_revision(plan_id, revision)
    verified_digest = verify_persisted_revision(root, revision_record)
    active_path = root / "workflow" / "orchestration" / "active_plan.json"
    active_payload = {
        "schema": "arcvellum/active-creative-plan/v1",
        "plan_id": plan_id,
        "revision": revision,
        "revision_digest": verified_digest,
        "base_project_fingerprint": current_project_fingerprint,
    }
    return store.activate_creative_plan(
        plan_id,
        revision,
        expected_active_revision=expected_active_revision,
        current_project_fingerprint=current_project_fingerprint,
        verified_revision_digest=verified_digest,
        active_plan_path=active_path,
        active_plan_payload=active_payload,
    )


def verify_persisted_revision(
    project_root: Path,
    revision_record: dict[str, Any],
) -> str:
    root = project_root.expanduser().resolve()
    if str(revision_record.get("artifact_state") or "") != "ready":
        raise RuntimeError("creative plan audit artifacts are not ready")
    payloads, digests = _read_verified_audit_payloads(root, revision_record)
    revision_digest = _revision_digest(digests)
    if revision_digest != str(revision_record.get("digest") or ""):
        raise RuntimeError("creative plan revision digest mismatch")
    provenance = _read_provenance(root, revision_record)
    if str(provenance.get("revision_digest") or "") != revision_digest:
        raise RuntimeError("creative plan provenance does not match the revision digest")
    verify_semantic_chain(payloads, provenance)
    if _provenance_files(provenance) != digests:
        raise RuntimeError("creative plan provenance file manifest is inconsistent")
    return revision_digest


def _prepare_shadow_revision(
    candidate_payload: dict[str, Any],
    *,
    plan: CreativeExecutionPlan,
    graph: CompiledTaskGraph,
    lint_result: PlanLintResult,
    simulation: PlanSimulationResult,
) -> _PreparedShadowRevision:
    revision_name = f"revision_{plan.revision:04d}"
    relative_root = Path("workflow") / "orchestration" / "plans" / plan.plan_id
    payloads = _audit_payloads(
        revision_name,
        candidate_payload=candidate_payload,
        plan=plan,
        graph=graph,
        lint_result=lint_result,
        simulation=simulation,
    )
    rendered = _render_payloads(payloads)
    content_digests = {name: _sha256(text) for name, text in rendered.items()}
    revision_digest = _revision_digest(content_digests)
    provenance = _provenance_payload(
        plan,
        graph,
        lint_result,
        revision_digest=revision_digest,
        content_digests=content_digests,
    )
    rendered["provenance.json"] = _render_json(provenance)
    relative_files = tuple(
        ((relative_root / name).as_posix(), _sha256(text))
        for name, text in sorted(rendered.items())
    )
    return _PreparedShadowRevision(
        revision_name=revision_name,
        relative_root=relative_root,
        rendered=rendered,
        revision_digest=revision_digest,
        relative_files=relative_files,
    )


def _audit_payloads(
    revision_name: str,
    *,
    candidate_payload: dict[str, Any],
    plan: CreativeExecutionPlan,
    graph: CompiledTaskGraph,
    lint_result: PlanLintResult,
    simulation: PlanSimulationResult,
) -> dict[str, dict[str, Any]]:
    return {
        f"{revision_name}.candidate.json": candidate_payload,
        f"{revision_name}.plan.json": to_primitive(plan),
        f"{revision_name}.compiled_graph.json": to_primitive(graph),
        f"{revision_name}.lint.json": _lint_payload(lint_result),
        f"{revision_name}.simulation.json": to_primitive(simulation),
        f"{revision_name}.review.json": {
            "schema": "arcvellum/orchestration-review/v1",
            "status": "not_required_shadow",
            "message": "Shadow compilation does not authorize activation.",
        },
    }


def _provenance_payload(
    plan: CreativeExecutionPlan,
    graph: CompiledTaskGraph,
    lint_result: PlanLintResult,
    *,
    revision_digest: str,
    content_digests: dict[str, str],
) -> dict[str, Any]:
    return {
        "schema": "arcvellum/orchestration-provenance/v1",
        "plan_id": plan.plan_id,
        "revision": plan.revision,
        "base_project_fingerprint": plan.base_project_fingerprint,
        "plan_digest": lint_result.plan_digest,
        "graph_digest": graph.graph_digest,
        "revision_digest": revision_digest,
        "files": [
            {"path": name, "sha256": digest}
            for name, digest in sorted(content_digests.items())
        ],
    }


def _read_verified_audit_payloads(
    root: Path,
    revision_record: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    payloads: dict[str, dict[str, Any]] = {}
    digests: dict[str, str] = {}
    fields = ("candidate", "normalized", "compiled", "lint", "simulation", "review")
    for field in fields:
        reference = revision_record.get(field)
        if not isinstance(reference, dict):
            raise RuntimeError(f"creative plan audit reference is missing: {field}")
        relative = _safe_relative_path(reference.get("path"))
        target = (root / relative).resolve()
        _validate_audit_target(root, target, relative)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if digest != str(reference.get("sha256") or ""):
            raise RuntimeError(
                f"creative plan audit file digest mismatch: {relative.as_posix()}"
            )
        payload = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError(
                f"creative plan audit payload is invalid: {relative.as_posix()}"
            )
        digests[target.name] = digest
        payloads[field] = payload
    return payloads, digests


def _validate_audit_target(
    root: Path,
    target: Path,
    relative: PurePosixPath,
) -> None:
    if root not in target.parents:
        raise RuntimeError("creative plan audit path escapes the project")
    if not target.is_file():
        raise RuntimeError(f"creative plan audit file is missing: {relative.as_posix()}")


def _read_provenance(
    root: Path,
    revision_record: dict[str, Any],
) -> dict[str, Any]:
    normalized = revision_record.get("normalized")
    if not isinstance(normalized, dict):
        raise RuntimeError("creative plan normalized audit reference is missing")
    provenance_path = (
        root / _safe_relative_path(normalized.get("path"))
    ).parent / "provenance.json"
    if root not in provenance_path.resolve().parents or not provenance_path.is_file():
        raise RuntimeError("creative plan provenance file is missing or unsafe")
    payload = json.loads(provenance_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("creative plan provenance payload is invalid")
    return payload


def _provenance_files(provenance: dict[str, Any]) -> dict[str, str]:
    return {
        str(item.get("path") or ""): str(item.get("sha256") or "")
        for item in provenance.get("files", ())
        if isinstance(item, dict)
    }


def _render_payloads(
    payloads: dict[str, dict[str, Any]],
) -> dict[str, str]:
    return {name: _render_json(payload) for name, payload in payloads.items()}


def _render_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _index_record(
    root: Path,
    *,
    plan: CreativeExecutionPlan,
    graph: CompiledTaskGraph,
    lint_result: PlanLintResult,
    simulation: PlanSimulationResult,
    revision_digest: str,
    files: dict[str, str],
    revision_name: str,
) -> dict[str, Any]:
    prefix = f"workflow/orchestration/plans/{plan.plan_id}"

    def reference(suffix: str, status: str = "") -> dict[str, str]:
        path = f"{prefix}/{revision_name}.{suffix}.json"
        value = {"path": path, "sha256": files[path]}
        if status:
            value["status"] = status
        return value

    return {
        "plan_id": plan.plan_id,
        "revision": plan.revision,
        "project_root": str(root),
        "scope_kind": plan.scope.kind.value,
        "scope_key": plan.scope.key,
        "status": "shadow",
        "base_project_fingerprint": plan.base_project_fingerprint,
        "policy": {"freedom_budget": to_primitive(plan.freedom_budget)},
        "candidate": reference("candidate"),
        "normalized": reference("plan", plan.lifecycle_status.value),
        "compiled": reference("compiled_graph", graph.graph_digest),
        "lint": reference("lint", lint_result.status),
        "simulation": reference("simulation", simulation.status),
        "review": reference("review", "not_required_shadow"),
        "digest": revision_digest,
        "created_at": plan.created_at,
    }


def _lint_payload(result: PlanLintResult) -> dict[str, Any]:
    return {
        "schema": "arcvellum/plan-lint-result/v1",
        "status": result.status,
        "digest": result.digest,
        "plan_digest": result.plan_digest,
        "issues": to_primitive(result.issues),
    }


def _revision_digest(digests: dict[str, str]) -> str:
    return _sha256(
        json.dumps(digests, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _safe_relative_path(value: object) -> PurePosixPath:
    path = PurePosixPath(str(value or "").replace("\\", "/"))
    if not path.parts or path.is_absolute() or ".." in path.parts or ":" in path.parts[0]:
        raise RuntimeError(f"invalid creative plan audit path: {value}")
    return path
