"""Terminal application state for reviewed Canon patch candidates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .approval import approval_matches_patch, approval_record_for_run, patch_requires_approval
from .paths import canon_apply_manifest_path


def canon_application_status(
    root: Path,
    patch_path: Path,
    payload: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    patch_id = patch_path.stem
    patch_sha256 = hashlib.sha256(patch_path.read_bytes()).hexdigest()
    apply_manifest = canon_apply_manifest_path(root, patch_id)
    applied = _read_json(apply_manifest)
    if _applied_manifest_is_current(root, patch_path, payload, applied, patch_sha256):
        approval = applied.get("approval") if isinstance(applied.get("approval"), dict) else {}
        result.update(
            status="pass",
            message="canon change candidate completed and applied to canon ledger",
            patch_id=patch_id,
            candidate_sha256=str(applied.get("candidate_sha256") or ""),
            applied_patch_sha256=patch_sha256,
            approval_run_id=str(applied.get("approval_run_id") or patch_id),
            approval_decision=str(approval.get("decision") or ""),
            approval_current=True,
            applied=True,
            apply_manifest=_rel(apply_manifest, root),
        )
        return result

    approval = approval_record_for_run(root, patch_id)
    approval_current = approval_matches_patch(approval, patch_path)
    decision = str(approval.get("decision") or "").strip().lower() if approval_current else ""
    result.update(
        patch_id=patch_id,
        candidate_sha256=patch_sha256,
        approval_run_id=patch_id,
        approval_decision=decision,
        approval_current=approval_current,
    )
    terminal = _decision_state(decision)
    if terminal:
        status, message = terminal
        result.update(status=status, message=message)
    elif patch_requires_approval(payload) and decision != "approve":
        result.update(
            status="needs_approval",
            message="canon patch needs an approve decision bound to its exact digest",
        )
    else:
        result.update(
            status="pending_apply",
            message="reviewed canon patch is ready for deterministic canon-apply",
        )
    return result


def _applied_manifest_is_current(
    root: Path,
    patch_path: Path,
    patch: dict[str, Any],
    applied: dict[str, Any],
    patch_sha256: str,
) -> bool:
    recorded_applied_digest = str(applied.get("applied_patch_sha256") or "").strip().lower()
    legacy_digest = _legacy_pre_apply_sha256(patch) if patch.get("applied") is True else ""
    digest_matches = recorded_applied_digest == patch_sha256 or (
        not recorded_applied_digest
        and bool(legacy_digest)
        and str(applied.get("candidate_sha256") or "").lower() == legacy_digest
    )
    manifest = canon_apply_manifest_path(root, patch_path.stem)
    return (
        patch.get("applied") is True
        and str(patch.get("apply_manifest") or "") == _rel(manifest, root)
        and str(applied.get("status") or "") == "applied"
        and str(applied.get("patch") or "") == _rel(patch_path, root)
        and digest_matches
    )


def _decision_state(decision: str) -> tuple[str, str] | None:
    return {
        "revise": ("needs_revision", "canon patch has a current revise decision"),
        "reject": (
            "rejected",
            "canon patch was rejected and must be reconciled with the promoted scene",
        ),
        "defer": ("deferred", "canon patch is deferred; chronological scene work is paused"),
    }.get(decision)


def _legacy_pre_apply_sha256(payload: dict[str, Any]) -> str:
    candidate = dict(payload)
    candidate["status"] = "candidate"
    candidate["applied"] = False
    for key in ("applied_at", "approval_run_id", "apply_manifest", "canon_change_log"):
        candidate.pop(key, None)
    text = json.dumps(candidate, ensure_ascii=False, indent=2) + "\n"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


__all__ = ["canon_application_status"]
