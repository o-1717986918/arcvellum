"""Transactional activation projection for a verified creative plan revision."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from literary_engineering_studio_engine.foundation.atomic_io import atomic_write_text

from .creative_plan_events import append_creative_plan_event_tx
from .creative_plan_primitives import project_key
from .primitives import _now


def apply_creative_plan_activation(
    connection,
    *,
    plan: dict[str, Any],
    revision: dict[str, Any],
    requested_revision: int,
    expected_active_revision: int,
    current_project_fingerprint: str,
    verified_revision_digest: str,
    active_plan_path: Path,
    active_plan_payload: dict[str, Any],
) -> None:
    _validate_activation_evidence(revision)
    _validate_active_plan_target(
        plan,
        active_plan_path,
        active_plan_payload,
        requested_revision=requested_revision,
        verified_revision_digest=verified_revision_digest,
        current_project_fingerprint=current_project_fingerprint,
    )
    atomic_write_text(
        active_plan_path,
        json.dumps(active_plan_payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
    )
    _activate_index_rows(
        connection,
        plan=plan,
        requested_revision=requested_revision,
        expected_active_revision=expected_active_revision,
    )


def capture_active_projection(target: Path) -> str | None:
    return target.read_text(encoding="utf-8") if target.is_file() else None


def _activate_index_rows(
    connection,
    *,
    plan: dict[str, Any],
    requested_revision: int,
    expected_active_revision: int,
) -> None:
    now = _now()
    connection.execute(
        """
        UPDATE creative_plans
        SET status = 'superseded', updated_at = ?
        WHERE project_root = ? AND status = 'active' AND plan_id <> ?
        """,
        (now, str(plan["project_root"]), str(plan["plan_id"])),
    )
    connection.execute(
        """
        UPDATE creative_plans
        SET status = 'active', active_revision = ?, updated_at = ?
        WHERE plan_id = ?
        """,
        (requested_revision, now, str(plan["plan_id"])),
    )
    append_creative_plan_event_tx(
        connection,
        str(plan["plan_id"]),
        requested_revision,
        "plan.activated",
        {"previous_revision": int(expected_active_revision)},
    )


def _validate_activation_evidence(revision: dict[str, Any]) -> None:
    if revision["lint"].get("status") not in {"pass", "warn"}:
        raise RuntimeError("creative plan activation requires passing Plan Lint")
    if revision["simulation"].get("status") not in {"pass", "warn"}:
        raise RuntimeError("creative plan activation requires passing Plan Simulation")
    if revision["review"].get("status") != "pass":
        raise RuntimeError("creative plan activation requires passing orchestration review")


def _validate_active_plan_target(
    plan: dict[str, Any],
    target: Path,
    payload: dict[str, Any],
    *,
    requested_revision: int,
    verified_revision_digest: str,
    current_project_fingerprint: str,
) -> None:
    resolved = target.expanduser().resolve()
    if resolved.name != "active_plan.json" or len(resolved.parents) < 3:
        raise ValueError("creative plan active projection path is invalid")
    if project_key(str(resolved.parents[2])) != str(plan["project_root"]):
        raise ValueError("creative plan active projection escapes the work project")
    expected = {
        "schema": "arcvellum/active-creative-plan/v1",
        "plan_id": str(plan["plan_id"]),
        "revision": requested_revision,
        "revision_digest": verified_revision_digest,
        "base_project_fingerprint": current_project_fingerprint,
    }
    if payload != expected:
        raise ValueError("creative plan active projection payload is inconsistent")


def restore_active_projection(target: Path, previous: str | None) -> None:
    if previous is None:
        target.unlink(missing_ok=True)
    else:
        atomic_write_text(target, previous)
