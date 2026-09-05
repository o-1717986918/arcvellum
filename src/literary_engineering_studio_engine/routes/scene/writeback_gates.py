"""Writeback and handoff gates for the formal scene route."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from ...canon_evolver import canon_writeback_status
from ...character_state_apply import state_patch_writeback_status
from ...continuity_ledger import continuity_ledger_status, continuity_ledger_task_status
from ...scene_handoff import scene_handoff_source_status
from ...scene_route_support import _read_optional_json
from ...semantic_task_contracts import semantic_artifact_errors
from ...task_paths import relative_path as _rel
from ..review.canon_gates import (
    canon_patch_apply_gate_errors,
    canon_patch_candidate_gate_errors,
    canon_patch_decision_gate_errors,
)
from ..review.evidence import declared_repair_targets_changed


def state_and_canon_gate_validation(
    root: Path,
    task: dict[str, object],
    current_state: str,
    scene_id: str,
) -> list[str]:
    errors = _state_gate_errors(root, current_state, scene_id)
    errors.extend(_canon_gate_errors(root, task, current_state, scene_id))
    return errors


def continuity_and_handoff_gate_validation(
    root: Path,
    current_state: str,
    scene_id: str,
    *,
    status_reader: Callable[..., tuple[bool, str, dict[str, object]]] = continuity_ledger_status,
    task_status_reader: Callable[..., tuple[bool, str]] = continuity_ledger_task_status,
) -> list[str]:
    errors = _continuity_gate_errors(
        root,
        current_state,
        scene_id,
        status_reader=status_reader,
        task_status_reader=task_status_reader,
    )
    if current_state == "scene-handoff":
        passed, message, _payload = scene_handoff_source_status(root, scene_id)
        if not passed:
            errors.append(message)
    return errors


def _state_gate_errors(root: Path, current_state: str, scene_id: str) -> list[str]:
    errors: list[str] = []
    if current_state in {"state-patch-json", "state-agent-task"}:
        errors.extend(_state_patch_gate_errors(root, scene_id))
    if current_state == "state-agent-task":
        errors.extend(semantic_artifact_errors(root, current_state, scene_id))
    if current_state in {"state-patch-approval", "state-apply"}:
        status = state_patch_writeback_status(root, scene_id)
        value = str(status.get("status") or "")
        allowed = {"pending_apply", "pass", "not_required"}
        if current_state == "state-patch-approval" and value not in allowed:
            errors.append(str(status.get("message") or "state patch approval is incomplete"))
        if current_state == "state-apply" and value != "pass":
            errors.append(str(status.get("message") or "state apply is incomplete"))
    return errors


def _canon_gate_errors(
    root: Path,
    task: dict[str, object],
    current_state: str,
    scene_id: str,
) -> list[str]:
    errors: list[str] = []
    if current_state == "canon-patch-json":
        errors.extend(_canon_writeback_gate_errors(root, scene_id, require_review=False))
    if current_state == "canon-agent-task":
        errors.extend(_canon_writeback_gate_errors(root, scene_id, require_review=True))
        errors.extend(semantic_artifact_errors(root, current_state, scene_id))
    if current_state == "canon-patch-revision":
        errors.extend(declared_repair_targets_changed(root, task, "canon-patch revision"))
        errors.extend(canon_patch_candidate_gate_errors(root, task))
    if current_state in {"canon-patch-approval", "canon-patch-deferred"}:
        errors.extend(canon_patch_decision_gate_errors(root, task, require_approve=False))
    if current_state == "canon-patch-apply":
        errors.extend(canon_patch_apply_gate_errors(root, task))
    return errors


def _continuity_gate_errors(
    root: Path,
    current_state: str,
    scene_id: str,
    *,
    status_reader: Callable[..., tuple[bool, str, dict[str, object]]],
    task_status_reader: Callable[..., tuple[bool, str]],
) -> list[str]:
    stages = {"continuity-ledger-agent-task", "continuity-ledger-review", "continuity-ledger-apply"}
    errors: list[str] = []
    if current_state in stages:
        passed, message, _delta = status_reader(
            root,
            scene_id,
            require_review=current_state != "continuity-ledger-agent-task",
        )
        if not passed:
            errors.append(message)
    if current_state in {"continuity-ledger-agent-task", "continuity-ledger-review"}:
        passed, message = task_status_reader(
            root, scene_id, review=current_state == "continuity-ledger-review"
        )
        if not passed:
            errors.append(message)
    receipt = root / "plot" / "ledger_deltas" / f"{scene_id}_apply.json"
    if current_state == "continuity-ledger-apply" and not receipt.is_file():
        errors.append("continuity ledger apply receipt is missing")
    return errors


def _state_patch_gate_errors(root: Path, scene_id: str) -> list[str]:
    path = root / "characters" / "state_patches" / f"{scene_id}_state_patch.json"
    payload, error = _read_optional_json(path)
    if error:
        return [error]
    if not payload:
        return [f"state patch JSON is missing or empty: {_rel(path, root)}"]
    errors: list[str] = []
    if str(payload.get("schema") or "") != "literary-engineering-workbench/character-state-patch/v0.1":
        errors.append("state patch JSON has wrong or missing schema")
    if str(payload.get("scene_id") or "") not in {"", scene_id}:
        errors.append(f"state patch scene_id mismatch: {payload.get('scene_id')}")
    allowed = {"pending_human_approval", "candidate", "reviewed", "approved"}
    if str(payload.get("status") or "").strip().lower() not in allowed:
        errors.append("state patch status must remain candidate/review/approval-scoped")
    return errors


def _canon_writeback_gate_errors(
    root: Path,
    scene_id: str,
    *,
    require_review: bool = True,
) -> list[str]:
    status = canon_writeback_status(root, scene_id, require_review=require_review)
    if str(status.get("status") or "") in {"pass", "not_required"}:
        return []
    return [f"canon writeback gate is not complete for {scene_id}: {status.get('message')}"]


__all__ = ["continuity_and_handoff_gate_validation", "state_and_canon_gate_validation"]
