"""Explicit assisted activation for verified creative-plan revisions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .plan_index import CreativePlanIndex


def activate_persisted_revision(
    project_root: Path,
    *,
    store: CreativePlanIndex,
    plan_id: str,
    revision: int,
    expected_active_revision: int,
    current_project_fingerprint: str,
) -> dict[str, Any]:
    from .persistence import verify_persisted_revision

    root = project_root.expanduser().resolve()
    _validate_plan_project(root, store.read_creative_plan(plan_id))
    revision_record = store.read_creative_plan_revision(plan_id, revision)
    verified_digest = verify_persisted_revision(root, revision_record)
    active_path = root / "workflow" / "orchestration" / "active_plan.json"
    active_payload = {
        "schema": "arcvellum/active-creative-plan/v1",
        "plan_id": plan_id,
        "revision": revision,
        "revision_digest": verified_digest,
        "authorization_digest": _authorization_digest(revision_record),
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


def authorize_persisted_revision(
    project_root: Path,
    *,
    store: CreativePlanIndex,
    plan_id: str,
    revision: int,
    authorized_by: str,
    reason: str,
) -> dict[str, Any]:
    """Promote reviewed shadow evidence to assisted activation eligibility."""

    from .persistence import read_verified_revision_payloads, verify_persisted_revision

    root = project_root.expanduser().resolve()
    _validate_plan_project(root, store.read_creative_plan(plan_id))
    revision_record = store.read_creative_plan_revision(plan_id, revision)
    verified_digest = verify_persisted_revision(root, revision_record)
    review = read_verified_revision_payloads(root, revision_record)["review"]
    _validate_independent_review(review)
    return store.authorize_creative_plan_revision(
        plan_id,
        revision,
        authorized_by=authorized_by,
        reason=reason,
        verified_revision_digest=verified_digest,
    )


def assisted_activate_persisted_revision(
    project_root: Path,
    *,
    store: CreativePlanIndex,
    plan_id: str,
    revision: int,
    expected_active_revision: int,
    current_project_fingerprint: str,
    authorized_by: str,
    reason: str,
) -> dict[str, Any]:
    authorize_persisted_revision(
        project_root,
        store=store,
        plan_id=plan_id,
        revision=revision,
        authorized_by=authorized_by,
        reason=reason,
    )
    return activate_persisted_revision(
        project_root,
        store=store,
        plan_id=plan_id,
        revision=revision,
        expected_active_revision=expected_active_revision,
        current_project_fingerprint=current_project_fingerprint,
    )


def _validate_plan_project(root: Path, plan_record: dict[str, Any]) -> None:
    expected = str(root).replace("\\", "/").rstrip("/").casefold()
    if str(plan_record.get("project_root") or "") != expected:
        raise RuntimeError("creative plan belongs to a different project")


def _validate_independent_review(review: dict[str, Any]) -> None:
    if review.get("status") != "pass":
        raise RuntimeError("assisted activation requires a passing orchestration review")
    planner = str(review.get("planner_session_id") or "").strip()
    reviewer = str(review.get("reviewer_session_id") or "").strip()
    if not planner or not reviewer or planner == reviewer:
        raise RuntimeError("assisted activation requires an independent reviewer")


def _authorization_digest(revision_record: dict[str, Any]) -> str:
    review = revision_record.get("review")
    authorization = review.get("authorization") if isinstance(review, dict) else None
    digest = (
        str(authorization.get("digest") or "").strip()
        if isinstance(authorization, dict)
        else ""
    )
    if not digest:
        raise RuntimeError(
            "creative plan revision is shadow-only and lacks assisted authorization"
        )
    return digest
