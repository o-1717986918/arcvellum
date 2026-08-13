"""Task-owned metadata normalization before deterministic preflight validation."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from ..contracts import TaskPackage
from .archaeology import canonicalize_archaeology_metadata
from .asset_evidence import review_machine_fields
from .common import REVIEW_CONCLUSION, REVIEW_CONCLUSION_VARIANT
from .scene_manifest_metadata import (
    canonicalize_scene_candidate_manifest,
    canonicalize_scene_revision_manifest,
)
from .scene_review_metadata import canonicalize_scene_review_metadata
from .style_snapshot import prompt_style_snapshot
from .style_metadata import canonicalize_style_machine_metadata
from ..sandbox import SandboxManifest
from literary_engineering_studio_engine.prompting.agents.schema import load_schema_spec
from literary_engineering_studio_engine.semantic_task_contracts import (
    semantic_artifact_definition,
    semantic_artifact_relative_path,
)
from literary_engineering_studio_engine.literary.assets.continuity.architecture import REQUIRED_FIELDS


SEMANTIC_SOURCE_PATTERNS = {
    "roleplay-agent-task": "branches/{scene_id}/roleplay_simulation.md",
    "branch-agent-task": "branches/{scene_id}/branch_manifest.json",
    "composition-agent-task": "drafts/compositions/{scene_id}_composition.json",
    "state-agent-task": "characters/state_patches/{scene_id}_state_patch.json",
    "canon-agent-task": "canon/patches/{scene_id}_canon_patch.json",
}


def canonicalize_task_outputs(task: TaskPackage, sandbox: SandboxManifest) -> list[dict[str, str]]:
    """Normalize semantically identical machine markers without changing a review verdict."""

    changes = _canonicalize_archaeology_chunk_metadata(task, sandbox)
    changes.extend(canonicalize_archaeology_metadata(task, sandbox))
    changes.extend(_canonicalize_asset_machine_metadata(task, sandbox))
    changes.extend(_canonicalize_semantic_artifact_metadata(task, sandbox))
    changes.extend(_canonicalize_canon_patch_candidate_metadata(task, sandbox))
    changes.extend(_canonicalize_story_architecture_metadata(task, sandbox))
    changes.extend(_canonicalize_continuity_ledger_metadata(task, sandbox))
    changes.extend(canonicalize_style_machine_metadata(task, sandbox))
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
    """Normalize task-owned semantic artifact identity without editing judgment.

    Agents own the roleplay/composition/state/canon reasoning.  The schema
    discriminator, scene identity and standard spelling of a finished status
    are state-machine facts.  In particular, a model spelling ``completed``
    must not turn a complete roleplay into a dead-end route failure.
    """

    current_state = str(task.current_state or task.payload.get("current_state") or "")
    scene_id = str(task.payload.get("scene_id") or "").strip()
    definition = semantic_artifact_definition(current_state)
    relative = semantic_artifact_relative_path(current_state, scene_id)
    if definition is None or not relative:
        return []
    path = sandbox.workspace / Path(relative)
    payload = _read_object(path)
    if payload is None:
        return []

    schema_spec = load_schema_spec(definition["schema_name"])
    expected = {
        "schema": str(schema_spec.get("schema_value") or payload.get("schema") or ""),
        "scene_id": scene_id,
    }
    expected_source = SEMANTIC_SOURCE_PATTERNS.get(current_state, "").format(scene_id=scene_id)
    if expected_source:
        expected["source_artifact"] = expected_source
        source_path = sandbox.workspace / Path(expected_source)
        if source_path.is_file():
            digest_key = {
                "composition-agent-task": "composition_sha256",
                "state-agent-task": "state_patch_sha256",
                "canon-agent-task": "canon_patch_sha256",
            }.get(current_state, "")
            if digest_key:
                expected[digest_key] = hashlib.sha256(source_path.read_bytes()).hexdigest()
    status_aliases = {
        "completed": "complete",
        "done": "complete",
        "passed": "complete",
        # Review Agents commonly use their verdict vocabulary in the lifecycle
        # field.  ``status`` is bookkeeping, so this is safe to normalize.
        "pass": "complete",
    }
    actual_status = str(payload.get("status") or "").strip().lower()
    if actual_status in status_aliases:
        expected["status"] = status_aliases[actual_status]
    # ``verdict`` is creative judgment and is normally left untouched.  The
    # one harmless mismatch is a review that has stated it is ready and has no
    # required changes, but wrote the lifecycle word "complete" as its
    # verdict.  Canonicalize that representation rather than consuming a full
    # repair turn on a field swap.
    if (
        current_state == "composition-agent-task"
        and str(payload.get("verdict") or "").strip().lower() in {"complete", "completed"}
        and payload.get("ready_for_generation") is True
        and not payload.get("required_changes")
    ):
        expected["verdict"] = "pass"
    changes = _write_machine_fields(path, relative, payload, expected, "semantic-artifact")
    # Agent output frequently represents one finding as an object and several
    # findings as a list.  For a schema-declared list field, wrapping an
    # existing non-empty value preserves the Agent's judgment exactly while
    # removing a purely mechanical container mismatch.  Missing/null/blank
    # fields remain invalid so the Worker never invents creative evidence.
    list_changes = _canonicalize_declared_list_fields(path, relative, payload, schema_spec)
    return [*changes, *list_changes]


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


def _meaningful(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict)):
        return len(value) > 0
    return True


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
        "canon-review-agent-task": ("reviews/agent/canon_review.json", "literary-engineering-workbench/canon-review-agent/v1", "conclusion"),
        "canon-review-pass": ("reviews/agent/canon_review.json", "literary-engineering-workbench/canon-review-agent/v1", "conclusion"),
        "committee-agent-task": ("reviews/agent/committee_project-final-audit.json", "literary-engineering-workbench/committee-review-agent/v1", "final_recommendation"),
        "committee-pass": ("reviews/agent/committee_project-final-audit.json", "literary-engineering-workbench/committee-review-agent/v1", "final_recommendation"),
    }
    contract = contracts.get(state)
    if contract is None:
        return []
    relative, schema, verdict_field = contract
    path = sandbox.workspace / relative
    payload = _read_object(path)
    if payload is None:
        return []
    expected: dict[str, Any] = {
        "schema": schema,
        "source_paths": [str(item).replace("\\", "/") for item in task.source_paths],
    }
    if state.startswith("committee"):
        expected["subject"] = str(task.payload.get("target_id") or "project-final-audit")
    if state in {"canon-review-pass", "committee-pass"}:
        expected[verdict_field] = "recheck_required"
    return _write_machine_fields(path, relative, payload, expected, "project-review")


def _session_identity(task: TaskPackage, role: str) -> str:
    """Stable role identity for independence gates, derived from the task id."""

    return f"studio:{role}:{task.task_id}"


def _normalize_complete_status(payload: dict[str, Any], expected: dict[str, Any]) -> None:
    # ``status`` is workflow-owned lifecycle metadata, not creative judgment.
    # Keep common Agent phrasings from consuming a repair turn while leaving
    # verdicts, findings, and all substantive ledger content untouched.
    aliases = {
        "completed": "complete",
        "done": "complete",
        "passed": "complete",
        "handled": "complete",
        "agent_judged": "complete",
        "agent_judgment_complete": "complete",
    }
    status = str(payload.get("status") or "").strip().lower()
    if status in aliases:
        expected["status"] = aliases[status]


def _canonicalize_agent_completion_markers(task: TaskPackage, sandbox: SandboxManifest) -> list[dict[str, str]]:
    """Emit machine-owned lifecycle receipts after substantive output exists."""

    task_type = str(task.payload.get("task_type") or "")
    legacy_agent_states = {
        "roleplay-agent-task", "branch-agent-task", "branch-selection", "composition-agent-task",
        "state-agent-task", "canon-agent-task", "continuity-ledger-agent-task", "continuity-ledger-review",
    }
    agent_required = (
        str(task.payload.get("execution_policy") or "") == "agent-required"
        or task_type.startswith(("platform-agent", "main-platform-agent"))
        or task.current_state in legacy_agent_states
    )
    if not agent_required or task.route == "character-and-world-assets":
        return []
    marker_outputs = [item for item in task.expected_outputs if item.endswith(".agent_completion.json")]
    if not marker_outputs:
        return []
    non_markers = [item for item in task.expected_outputs if not item.endswith(".agent_completion.json")]
    if not non_markers or any(
        not (sandbox.workspace / Path(item)).is_file()
        or (sandbox.workspace / Path(item)).stat().st_size == 0
        for item in non_markers
    ):
        return []
    owned = task.payload.get("system_owned_fields") if isinstance(task.payload.get("system_owned_fields"), dict) else {}
    lifecycle = owned.get("lifecycle") if isinstance(owned.get("lifecycle"), dict) else {}
    receipts = lifecycle.get("completion_receipts") if isinstance(lifecycle.get("completion_receipts"), list) else []
    receipt_by_path = {
        str(item.get("path") or "").replace("\\", "/"): item
        for item in receipts
        if isinstance(item, dict)
    }
    changes: list[dict[str, str]] = []
    for relative in marker_outputs:
        contract = receipt_by_path.get(relative.replace("\\", "/"), {})
        base = relative[: -len(".agent_completion.json")]
        source_task = str(
            contract.get("source_task")
            or base + (".md" if base.endswith(".agent_tasks") else ".agent_tasks.md")
        )
        status = str(contract.get("status") or "complete")
        checked = bool(contract.get("expected_artifacts_checked", status == "complete"))
        payload = {
            "schema": str(contract.get("schema") or "literary-engineering-workbench/agent-task-completion/v1"),
            "source_task": source_task,
            "status": status,
            "handled_by": "studio-worker",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "expected_artifacts_checked": checked,
            "notes": ["Machine-owned completion receipt; route gates validate the Agent-authored result separately."],
        }
        path = sandbox.workspace / Path(relative)
        existing = _read_object(path)
        comparable = dict(payload)
        comparable.pop("completed_at")
        existing_comparable = dict(existing or {})
        existing_comparable.pop("completed_at", None)
        source_task_path = sandbox.workspace / Path(source_task)
        receipt_is_fresh = path.is_file() and (
            not source_task_path.is_file()
            or path.stat().st_mtime_ns >= source_task_path.stat().st_mtime_ns
        )
        if existing_comparable == comparable and receipt_is_fresh:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        changes.append({"path": relative, "field": "completion", "reason": "generated deterministic Agent-task completion metadata"})
    return changes


def _canonicalize_asset_machine_metadata(
    task: TaskPackage,
    sandbox: SandboxManifest,
) -> list[dict[str, str]]:
    """Restore task-owned asset IDs, paths and marker values before validation."""

    if task.route != "character-and-world-assets":
        return []
    task_type = str(task.payload.get("task_type") or "")
    if task_type not in {
        "platform-agent-asset-creation",
        "platform-agent-asset-review",
        "platform-agent-revision",
    }:
        return []
    owned = task.payload.get("system_owned_fields")
    owned = owned if isinstance(owned, dict) else {}
    candidate_contract = owned.get("candidate") if isinstance(owned.get("candidate"), dict) else {}
    review_contract = owned.get("review") if isinstance(owned.get("review"), dict) else {}
    completion_contract = owned.get("completion") if isinstance(owned.get("completion"), dict) else {}
    candidate_rel = str(
        candidate_contract.get("path") or task.payload.get("candidate") or ""
    ).replace("\\", "/").strip()
    candidate_id = str(
        candidate_contract.get("candidate_id")
        or task.payload.get("candidate_id")
        or task.payload.get("target_id")
        or ""
    ).strip()
    asset_type = str(
        candidate_contract.get("asset_type") or task.payload.get("asset_type") or ""
    ).strip()
    source_paths = candidate_contract.get("source_paths")
    if not isinstance(source_paths, list):
        source_paths = [str(item).replace("\\", "/") for item in task.source_paths]
    else:
        source_paths = [str(item).replace("\\", "/") for item in source_paths]
    changes: list[dict[str, str]] = []
    if task_type == "platform-agent-asset-creation":
        changes.extend(
            _canonicalize_asset_candidate(
                sandbox,
                candidate_contract,
                candidate_rel,
                candidate_id,
                asset_type,
                source_paths,
            )
        )
    if task_type in {"platform-agent-asset-review", "platform-agent-revision"}:
        changes.extend(
            _canonicalize_asset_review(
                task,
                sandbox,
                review_contract,
                candidate_rel,
                candidate_id,
                asset_type,
            )
        )
    changes.extend(
        _canonicalize_asset_completion_markers(task, sandbox, completion_contract)
    )
    return changes


def _canonicalize_asset_candidate(
    sandbox: SandboxManifest,
    contract: dict[str, Any],
    relative: str,
    candidate_id: str,
    asset_type: str,
    source_paths: list[str],
) -> list[dict[str, str]]:
    if not relative:
        return []
    path = sandbox.workspace / Path(relative)
    payload = _read_object(path)
    if payload is None:
        return []
    expected = {
        "schema": str(contract.get("schema") or payload.get("schema") or ""),
        "candidate_id": candidate_id,
        "asset_type": asset_type,
        "source_paths": source_paths,
    }
    if not isinstance(payload.get("promotion_notes"), str) or not str(
        payload.get("promotion_notes") or ""
    ).strip():
        expected["promotion_notes"] = (
            "Promotion requires a clean independent review and a matching approval record."
        )
    return _write_machine_fields(path, relative, payload, expected, "asset-candidate")


def _canonicalize_asset_review(
    task: TaskPackage,
    sandbox: SandboxManifest,
    contract: dict[str, Any],
    candidate_rel: str,
    candidate_id: str,
    asset_type: str,
) -> list[dict[str, str]]:
    review_rel = str(contract.get("path") or "").replace("\\", "/").strip()
    if not review_rel:
        review_rel = next(
            (
                relative
                for relative in task.expected_outputs
                if relative.replace("\\", "/").startswith("reviews/assets/")
                and relative.endswith("_review.json")
            ),
            "",
        )
    path = sandbox.workspace / Path(review_rel)
    payload = _read_object(path)
    if payload is None:
        return []
    expected = review_machine_fields(
        task,
        sandbox,
        payload,
        contract,
        candidate=candidate_rel,
        candidate_id=candidate_id,
        asset_type=asset_type,
    )
    if task.current_state in {"asset-review-pass", "asset-approval-revision"}:
        expected["status"] = "recheck_required"
    changes = _write_machine_fields(path, review_rel, payload, expected, "asset-review")
    changes.extend(_canonicalize_asset_review_action_targets(path, review_rel, payload, candidate_rel))
    changes.extend(
        _canonicalize_asset_approval_revision(
            task, sandbox, path, review_rel, payload, candidate_rel
        )
    )
    return changes


def _canonicalize_asset_review_action_targets(
    path: Path,
    relative: str,
    payload: dict[str, Any],
    candidate_rel: str,
) -> list[dict[str, str]]:
    """Attach a current-candidate path to a reviewer's bare JSON field anchor.

    ``psychology.secret`` is an intelligible creative review target, but the
    formal artifact contract represents it as
    ``characters/candidates/<id>.json#psychology.secret``.  The file prefix is
    system-owned routing data.  Preserve the reviewer-selected field while
    adding that prefix, and deliberately leave explicit file paths untouched
    so the cross-task write guard still catches them.
    """

    if not candidate_rel:
        return []
    actions = payload.get("revision_actions")
    if not isinstance(actions, list):
        return []
    changed = False
    for action in actions:
        if not isinstance(action, dict):
            continue
        target = str(action.get("target") or "").replace("\\", "/").strip()
        if not target:
            continue
        if target.startswith(candidate_rel):
            continue
        if target.startswith("#"):
            action["target"] = candidate_rel + target
            changed = True
            continue
        if "/" not in target:
            action["target"] = f"{candidate_rel}#{target}"
            changed = True
    if not changed:
        return []
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return [{"path": relative, "field": "revision_actions.target", "reason": "attached task-owned candidate path to review field anchor"}]


def _canonicalize_asset_approval_revision(
    task: TaskPackage,
    sandbox: SandboxManifest,
    review_path: Path,
    review_rel: str,
    review: dict[str, Any],
    candidate_rel: str,
) -> list[dict[str, str]]:
    """Reset revision bookkeeping after a real approval-bound candidate change.

    In this route the candidate change is creative work, while the review reset
    is lifecycle evidence.  Keeping the latter machine-owned prevents a model
    from stalling on a large review JSON solely to restate immutable status
    fields.  The fresh independent review remains the authority for quality.
    """

    if task.current_state != "asset-approval-revision" or not candidate_rel:
        return []
    candidate_path = sandbox.workspace / Path(candidate_rel)
    before = str(task.payload.get("candidate_sha256_before_revision") or "").strip().lower()
    if not before or not candidate_path.is_file():
        return []
    current = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
    if current == before:
        return []

    applied = review.get("applied_revision_actions")
    if isinstance(applied, list) and applied:
        return []
    rationale = _latest_asset_approval_rationale(sandbox.workspace, str(review.get("candidate_id") or ""))
    existing_round = review.get("revision_round")
    round_value = existing_round + 1 if isinstance(existing_round, int) and not isinstance(existing_round, bool) else 1
    review["status"] = "recheck_required"
    review["revision_round"] = max(1, round_value)
    review["applied_revision_actions"] = [
        {
            "id": "APPROVAL-REV-001",
            "action": rationale or "Applied the latest approval-bound candidate revision.",
            "evidence": f"{candidate_rel} changed from the approval-bound candidate digest; a fresh independent review must verify the exact semantic change.",
        }
    ]
    review["revised_at"] = datetime.now(timezone.utc).isoformat()
    review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _append_approval_revision_notice(review_path.with_suffix(".md"), review["revision_round"], rationale)
    return [
        {"path": review_rel, "field": "approval-revision-reset", "reason": "generated deterministic approval-revision lifecycle evidence"}
    ]


def _latest_asset_approval_rationale(workspace: Path, candidate_id: str) -> str:
    approvals = workspace / "workflow" / "approvals" / "index.jsonl"
    if not approvals.is_file():
        return ""
    try:
        records = [json.loads(line) for line in approvals.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ""
    for record in reversed(records):
        if not isinstance(record, dict) or str(record.get("run_id") or "") != candidate_id:
            continue
        if str(record.get("decision") or "").strip().lower() not in {"revise", "reject"}:
            continue
        return str(record.get("notes") or "").strip()[:800]
    return ""


def _append_approval_revision_notice(report_path: Path, revision_round: int, rationale: str) -> None:
    if not report_path.is_file():
        return
    try:
        content = report_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return
    marker = "## Studio Revision Reset"
    if marker in content:
        return
    note = rationale or "The latest approval requested a candidate-local revision."
    report_path.write_text(
        content.rstrip()
        + f"\n\n{marker}\n\n- Revision round: {revision_round}\n- Approval rationale recorded for independent recheck: {note}\n",
        encoding="utf-8",
    )


def _read_object(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_machine_fields(
    path: Path,
    relative: str,
    payload: dict[str, Any],
    expected: dict[str, Any],
    reason: str,
) -> list[dict[str, str]]:
    changed: list[str] = []
    for field, value in expected.items():
        if not value or payload.get(field) == value:
            continue
        payload[field] = value
        changed.append(field)
    if not changed:
        return []
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return [{"path": relative, "field": field, "reason": f"normalized deterministic {reason} metadata"} for field in changed]


def _canonicalize_asset_completion_markers(
    task: TaskPackage,
    sandbox: SandboxManifest,
    completion_contract: dict[str, Any],
) -> list[dict[str, str]]:
    """Generate marker metadata from the Worker-owned task lifecycle.

    This does not certify semantic quality; the regular preflight and core
    route gate still do that.  It removes a purely mechanical instruction from
    the Agent after it has already produced every requested artifact.
    """

    non_markers = [item for item in task.expected_outputs if not item.endswith(".agent_completion.json")]
    if any(not (sandbox.workspace / Path(item)).is_file() or (sandbox.workspace / Path(item)).stat().st_size == 0 for item in non_markers):
        return []
    revision_reset = task.current_state in {"asset-review-pass", "asset-approval-revision"}
    expected_status = "recheck_required" if revision_reset else str(completion_contract.get("status") or "complete")
    expected_checked = False if revision_reset else bool(completion_contract.get("expected_artifacts_checked", True))
    changed: list[dict[str, str]] = []
    for relative in task.expected_outputs:
        if not relative.endswith(".agent_completion.json"):
            continue
        completion_base = relative[: -len(".agent_completion.json")]
        source_task = completion_base + (".md" if completion_base.endswith(".agent_tasks") else ".agent_tasks.md")
        payload = {
            "schema": str(completion_contract.get("schema") or "literary-engineering-workbench/agent-task-completion/v1"),
            "source_task": source_task,
            "status": expected_status,
            "handled_by": "studio-worker",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "expected_artifacts_checked": expected_checked,
            "notes": ["Machine-owned completion metadata; semantic validation is enforced by the route gate."],
        }
        path = sandbox.workspace / Path(relative)
        existing = _read_object(path)
        comparable = dict(payload)
        comparable.pop("completed_at")
        existing_comparable = dict(existing or {})
        existing_comparable.pop("completed_at", None)
        if existing_comparable == comparable:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        changed.append({"path": relative, "field": "completion", "reason": "generated deterministic asset-task completion metadata"})
    return changed
