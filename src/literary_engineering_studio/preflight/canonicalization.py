"""Task-owned metadata normalization before deterministic preflight validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..contracts import TaskPackage
from .archaeology import canonicalize_archaeology_metadata
from .canonicalization_assets import canonicalize_asset_machine_metadata
from .canonicalization_common import (
    meaningful as _meaningful,
    normalize_complete_status as _normalize_complete_status,
    read_object as _read_object,
    session_identity as _session_identity,
    write_machine_fields as _write_machine_fields,
)
from .common import REVIEW_CONCLUSION, REVIEW_CONCLUSION_VARIANT
from .scene_manifest_metadata import (
    canonicalize_scene_candidate_manifest,
    canonicalize_scene_revision_manifest,
)
from .scene_review_metadata import canonicalize_scene_review_metadata
from .style_snapshot import prompt_style_snapshot
from .style_metadata import canonicalize_style_machine_metadata
from ..sandbox import SandboxManifest
from literary_engineering_studio_engine.public.literary import REQUIRED_FIELDS
from .completion_receipts import canonicalize_agent_completion_markers
from .project_review_repair_scope import canonicalize_project_review_repair_scope
from .project_review_markdown import canonicalize_project_review_markdown
from .semantic_metadata import canonicalize_semantic_artifact_metadata


def canonicalize_task_outputs(task: TaskPackage, sandbox: SandboxManifest) -> list[dict[str, str]]:
    """Normalize semantically identical machine markers without changing a review verdict."""

    changes = _canonicalize_archaeology_chunk_metadata(task, sandbox)
    changes.extend(canonicalize_archaeology_metadata(task, sandbox))
    changes.extend(canonicalize_asset_machine_metadata(task, sandbox))
    changes.extend(_canonicalize_semantic_artifact_metadata(task, sandbox))
    changes.extend(_canonicalize_canon_patch_candidate_metadata(task, sandbox))
    changes.extend(_canonicalize_story_architecture_metadata(task, sandbox))
    changes.extend(_canonicalize_continuity_ledger_metadata(task, sandbox))
    changes.extend(canonicalize_style_machine_metadata(task, sandbox))
    changes.extend(canonicalize_project_review_repair_scope(task, sandbox))
    changes.extend(
        canonicalize_project_review_markdown(
            task,
            sandbox,
            read_object=_read_object,
        )
    )
    changes.extend(_canonicalize_project_review_metadata(task, sandbox))
    changes.extend(_canonicalize_agent_completion_markers(task, sandbox))
    changes.extend(
        canonicalize_scene_revision_manifest(
            task,
            sandbox,
            read_object=_read_object,
            session_identity=_session_identity,
        )
    )
    changes.extend(
        canonicalize_scene_candidate_manifest(
            task,
            sandbox,
            write_machine_fields=_write_machine_fields,
            session_identity=_session_identity,
        )
    )
    changes.extend(canonicalize_scene_review_metadata(task, sandbox))
    gates = " ".join(str(item) for item in task.payload.get("validation_gates") or []).lower()
    if (
        "conclusion is pass" not in gates
        and "conclusion is recorded" not in gates
        and "结论" not in gates
    ):
        return changes
    for relative in task.expected_outputs:
        if not relative.endswith(".md") or "review" not in relative.lower() or "agent_tasks" in relative.lower():
            continue
        path = sandbox.workspace / Path(relative)
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if REVIEW_CONCLUSION.search(text):
            continue
        matches = list(REVIEW_CONCLUSION_VARIANT.finditer(text))
        if len(matches) != 1:
            continue
        verdict = matches[0].group(1).lower()
        normalized = text[: matches[0].start()] + f"- 结论： {verdict}" + text[matches[0].end() :]
        path.write_text(normalized, encoding="utf-8")
        changes.append({"path": relative, "verdict": verdict})
    return changes

def _canonicalize_archaeology_chunk_metadata(
    task: TaskPackage,
    sandbox: SandboxManifest,
) -> list[dict[str, str]]:
    if task.route != "source-ingest" or task.current_state != "chunk-extraction-agent-task":
        return []
    owned = (
        task.payload.get("system_owned_fields")
        if isinstance(task.payload.get("system_owned_fields"), dict)
        else {}
    )
    expected = owned.get("archaeology") if isinstance(owned.get("archaeology"), dict) else {}
    if not expected:
        return []
    relative = next(
        (
            item
            for item in task.expected_outputs
            if item.endswith(".json") and not item.endswith(".agent_completion.json")
        ),
        "",
    )
    path = sandbox.workspace / relative
    payload = _read_object(path)
    if payload is None:
        return []
    return _write_machine_fields(
        path,
        relative,
        payload,
        expected,
        "archaeology-chunk",
    )


def _canonicalize_semantic_artifact_metadata(task: TaskPackage, sandbox: SandboxManifest) -> list[dict[str, str]]:
    return canonicalize_semantic_artifact_metadata(
        task,
        sandbox,
        read_object=_read_object,
        write_machine_fields=_write_machine_fields,
        canonicalize_declared_list_fields=_canonicalize_declared_list_fields,
    )


def _canonicalize_canon_patch_candidate_metadata(
    task: TaskPackage,
    sandbox: SandboxManifest,
) -> list[dict[str, str]]:
    """Bind Canon candidate transport fields without changing its judgment."""

    if str(task.current_state or "") != "canon-patch-json":
        return []
    scene_id = str(task.payload.get("scene_id") or "").strip()
    relative = next(
        (item for item in task.expected_outputs if item.endswith("_canon_patch.json")),
        "",
    )
    if not scene_id or not relative:
        return []
    path = sandbox.workspace / relative
    payload = _read_object(path)
    if payload is None:
        return []
    scene = str(task.payload.get("scene") or f"scenes/{scene_id}.yaml")
    source = f"drafts/scenes/{scene_id}.md"
    expected = {
        "schema": "literary-engineering-workbench/canon-patch-candidate/v0.1",
        "formal_contract_revision": "2026-07-23.3",
        "scene_id": scene_id,
        "scene": scene,
        "source": source,
        "status": "candidate",
        "applied": False,
        "requires_user_approval": True,
        "source_paths": [scene, source],
    }
    return _write_machine_fields(
        path, relative, payload, expected, "canon-patch-candidate"
    )


def _canonicalize_declared_list_fields(
    path: Path,
    relative: str,
    payload: dict[str, Any],
    schema_spec: dict[str, Any],
) -> list[dict[str, str]]:
    declared = schema_spec.get("types") if isinstance(schema_spec.get("types"), dict) else {}
    changed: list[str] = []
    for field, expected_type in declared.items():
        if expected_type != "list" or field not in payload:
            continue
        value = payload.get(field)
        if isinstance(value, list) or value is None or (isinstance(value, str) and not value.strip()):
            continue
        payload[field] = [value]
        changed.append(str(field))
    if not changed:
        return []
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return [
        {
            "path": relative,
            "field": field,
            "reason": "wrapped an existing semantic value to satisfy a schema-declared list field",
        }
        for field in changed
    ]


def _canonicalize_story_architecture_metadata(task: TaskPackage, sandbox: SandboxManifest) -> list[dict[str, str]]:
    """Bind architecture identity, digests, and session roles to the task.

    Architecture content and its verdict remain authored by the Writer or
    Reviewer.  A session identifier is only evidence of which formal task
    owned that role; it is not literary judgment and must never be guessed by
    the model.
    """

    state = str(task.current_state or "")
    candidate_rel = "plot/story_architecture.candidate.json"
    review_rel = "reviews/longform/story_architecture_review.json"
    changes: list[dict[str, str]] = []
    if state == "story-architecture-agent-task":
        path = sandbox.workspace / candidate_rel
        payload = _read_object(path)
        if payload is not None:
            expected: dict[str, Any] = {
                "schema": "literary-engineering-workbench/story-architecture/v1",
                "writer_session_id": _session_identity(task, "writer"),
            }
            _normalize_complete_status(payload, expected)
            if all(_meaningful(payload.get(field)) for field in REQUIRED_FIELDS):
                # status is workflow-owned lifecycle metadata.  Once the
                # Writer has produced every required creative field, the
                # Worker completes the lifecycle instead of waiting for the
                # model to guess a machine field.
                expected["status"] = "complete"
            changes.extend(_write_machine_fields(path, candidate_rel, payload, expected, "story-architecture"))
    elif state == "story-architecture-review":
        path = sandbox.workspace / review_rel
        candidate = sandbox.workspace / candidate_rel
        payload = _read_object(path)
        source = _read_object(candidate)
        if payload is not None and candidate.is_file():
            expected = {
                "schema": "literary-engineering-workbench/story-architecture-review/v1",
                "candidate_path": candidate_rel,
                "candidate_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
                "writer_session_id": str((source or {}).get("writer_session_id") or _session_identity(task, "writer")),
                "reviewer_session_id": _session_identity(task, "reviewer"),
            }
            _normalize_complete_status(payload, expected)
            if str(payload.get("verdict") or "").strip().lower() in {
                "pass",
                "revise",
                "block",
            }:
                expected["status"] = "complete"
            changes.extend(_write_machine_fields(path, review_rel, payload, expected, "story-architecture-review"))
    return changes



def _canonicalize_continuity_ledger_metadata(task: TaskPackage, sandbox: SandboxManifest) -> list[dict[str, str]]:
    """Keep continuity ledgers tied to the exact promoted draft and task role."""

    state = str(task.current_state or "")
    if state not in {"continuity-ledger-agent-task", "continuity-ledger-review"}:
        return []
    scene_id = str(task.payload.get("scene_id") or task.scene_id or "").strip()
    if not scene_id:
        return []
    delta_rel = f"plot/ledger_deltas/{scene_id}.json"
    review_rel = f"reviews/continuity/{scene_id}_ledger_review.json"
    draft_rel = f"drafts/scenes/{scene_id}.md"
    changes: list[dict[str, str]] = []
    if state == "continuity-ledger-agent-task":
        path = sandbox.workspace / delta_rel
        draft = sandbox.workspace / draft_rel
        payload = _read_object(path)
        if payload is not None and draft.is_file():
            expected: dict[str, Any] = {
                "schema": "literary-engineering-workbench/continuity-ledger-delta/v1",
                "scene_id": scene_id,
                "source_draft": draft_rel,
                "source_draft_sha256": hashlib.sha256(draft.read_bytes()).hexdigest(),
                "writer_session_id": _session_identity(task, "writer"),
            }
            _normalize_complete_status(payload, expected)
            changes.extend(_write_machine_fields(path, delta_rel, payload, expected, "continuity-ledger"))
    else:
        path = sandbox.workspace / review_rel
        delta = sandbox.workspace / delta_rel
        payload = _read_object(path)
        delta_payload = _read_object(delta)
        if payload is not None and delta.is_file():
            expected = {
                "schema": "literary-engineering-workbench/continuity-ledger-review/v1",
                "scene_id": scene_id,
                "delta_path": delta_rel,
                "delta_sha256": hashlib.sha256(delta.read_bytes()).hexdigest(),
                "writer_session_id": str((delta_payload or {}).get("writer_session_id") or _session_identity(task, "writer")),
                "reviewer_session_id": _session_identity(task, "reviewer"),
            }
            _normalize_complete_status(payload, expected)
            changes.extend(_write_machine_fields(path, review_rel, payload, expected, "continuity-ledger-review"))
    return changes


def _canonicalize_project_review_metadata(task: TaskPackage, sandbox: SandboxManifest) -> list[dict[str, str]]:
    """Normalize project-review provenance while preserving the review verdict."""

    state = str(task.current_state or "")
    contracts = {
        "canon-review-agent-task": ((_CANON_REVIEW_CONTRACT),),
        "canon-review-pass": ((_CANON_REVIEW_CONTRACT),),
        "committee-agent-task": ((_COMMITTEE_REVIEW_CONTRACT),),
        "committee-pass": (_CANON_REVIEW_CONTRACT, _COMMITTEE_REVIEW_CONTRACT),
    }
    changes: list[dict[str, str]] = []
    for contract in contracts.get(state, ()):
        changes.extend(_canonicalize_project_review_artifact(task, sandbox, state, contract))
    return changes


_CANON_REVIEW_CONTRACT = (
    "reviews/agent/canon_review.json",
    "literary-engineering-workbench/canon-review-agent/v1",
    "conclusion",
    False,
)
_COMMITTEE_REVIEW_CONTRACT = (
    "reviews/agent/committee_project-final-audit.json",
    "literary-engineering-workbench/committee-review-agent/v1",
    "final_recommendation",
    True,
)


def _canonicalize_project_review_artifact(
    task: TaskPackage,
    sandbox: SandboxManifest,
    state: str,
    contract: tuple[str, str, str, bool],
) -> list[dict[str, str]]:
    relative, schema, verdict_field, committee = contract
    path = sandbox.workspace / relative
    payload = _read_object(path)
    if payload is None:
        return []
    expected: dict[str, Any] = {"schema": schema}
    expected.update(_project_review_semantic_aliases(payload, committee=committee))
    if state.endswith("agent-task"):
        expected["source_paths"] = [str(item).replace("\\", "/") for item in task.source_paths]
    if committee:
        expected["subject"] = str(task.payload.get("target_id") or "project-final-audit")
    if state in {"canon-review-pass", "committee-pass"}:
        expected[verdict_field] = "recheck_required"
        expected["applied_repair_actions"] = _project_review_applied_repairs(task, sandbox)
    return _write_machine_fields(path, relative, payload, expected, "project-review")


def _project_review_applied_repairs(
    task: TaskPackage,
    sandbox: SandboxManifest,
) -> list[dict[str, str]]:
    """Record only deterministic before/after evidence for changed targets."""

    before = task.payload.get("repair_target_sha256_before_revision")
    hashes = before if isinstance(before, dict) else {}
    actions: list[dict[str, str]] = []
    for relative in task.payload.get("repair_targets") or []:
        normalized = str(relative).replace("\\", "/").strip()
        path = sandbox.workspace / Path(normalized)
        if not normalized or not path.is_file():
            continue
        previous = str(hashes.get(normalized) or "")
        current = hashlib.sha256(path.read_bytes()).hexdigest()
        if previous and previous == current:
            continue
        actions.append(
            {
                "target_path": normalized,
                "status": "changed",
                "before_sha256": previous,
                "after_sha256": current,
            }
        )
    return actions


def _project_review_semantic_aliases(
    payload: dict[str, Any],
    *,
    committee: bool,
) -> dict[str, Any]:
    """Normalize only explicit, semantically equivalent review fields."""

    expected = _project_review_verdict_alias(payload, committee=committee)
    expected.update(_project_review_action_alias(payload, committee=committee))
    return expected


def _project_review_verdict_alias(
    payload: dict[str, Any],
    *,
    committee: bool,
) -> dict[str, Any]:
    verdict_field = "final_recommendation" if committee else "conclusion"
    allowed = (
        {"approve", "approve_with_notes", "revise", "reject"}
        if committee
        else {"pass", "pass_with_notes", "revise_required", "reject"}
    )
    if str(payload.get(verdict_field) or "").strip():
        return {}
    for alias in ("verdict", "recommendation"):
        candidate = str(payload.get(alias) or "").strip().lower()
        if candidate in allowed:
            return {verdict_field: candidate}
    return {}


def _project_review_action_alias(
    payload: dict[str, Any],
    *,
    committee: bool,
) -> dict[str, Any]:
    action_field = "action_items" if committee else "recommendations"
    current_actions = payload.get(action_field)
    if isinstance(current_actions, list) and current_actions:
        return {}
    findings = payload.get("findings") if isinstance(payload.get("findings"), list) else []
    actions = [_actionable_project_review_finding(item) for item in findings]
    normalized = [item for item in actions if item]
    return {action_field: normalized} if normalized else {}


def _actionable_project_review_finding(item: Any) -> dict[str, str]:
    if not isinstance(item, dict):
        return {}
    target = str(item.get("target_path") or item.get("target") or "").strip()
    action = str(item.get("action") or "").strip()
    verification = str(item.get("verification") or "").strip()
    if not target or not action or not verification:
        return {}
    normalized = {
        "target_path": target,
        "action": action,
        "verification": verification,
    }
    if str(item.get("id") or "").strip():
        normalized["id"] = str(item["id"]).strip()
    return normalized



def _canonicalize_agent_completion_markers(task: TaskPackage, sandbox: SandboxManifest) -> list[dict[str, str]]:
    return canonicalize_agent_completion_markers(task, sandbox, read_object=_read_object)
