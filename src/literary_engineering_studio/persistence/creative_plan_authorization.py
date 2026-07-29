"""Pure authorization rules for reviewed creative-plan revisions."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def prepare_revision_authorization(
    revision: dict[str, Any],
    *,
    authorized_by: str,
    reason: str,
    verified_revision_digest: str,
    authorized_at: str,
) -> tuple[dict[str, Any], dict[str, str]] | None:
    actor = str(authorized_by or "").strip()
    rationale = str(reason or "").strip()
    if not actor or not rationale:
        raise ValueError("creative plan assisted authorization requires actor and reason")
    _validate_revision_evidence(revision, verified_revision_digest)
    review = dict(revision["review"])
    existing = review.get("authorization")
    if isinstance(existing, dict):
        _validate_idempotent_authorization(
            existing,
            actor=actor,
            reason=rationale,
            revision_digest=verified_revision_digest,
        )
        return None
    body = {
        "authorized_by": actor,
        "reason": rationale,
        "revision_digest": verified_revision_digest,
        "authorized_at": authorized_at,
    }
    authorization = {**body, "digest": authorization_digest(body)}
    review.update(
        {
            "activation_eligible": True,
            "lifecycle": "assisted_authorized",
            "authorization": authorization,
        }
    )
    return review, authorization


def _validate_revision_evidence(
    revision: dict[str, Any],
    verified_revision_digest: str,
) -> None:
    if revision["artifact_state"] != "ready":
        raise RuntimeError("creative plan authorization requires ready audit artifacts")
    if revision["digest"] != verified_revision_digest:
        raise RuntimeError("creative plan authorization requires verified audit artifacts")
    review = revision["review"]
    if not isinstance(review, dict) or review.get("status") != "pass":
        raise RuntimeError("creative plan authorization requires passing independent review")


def _validate_idempotent_authorization(
    existing: dict[str, Any],
    *,
    actor: str,
    reason: str,
    revision_digest: str,
) -> None:
    observed = (
        str(existing.get("authorized_by") or ""),
        str(existing.get("reason") or ""),
        str(existing.get("revision_digest") or ""),
    )
    if observed != (actor, reason, revision_digest):
        raise RuntimeError("creative plan revision already has a different authorization")


def authorization_digest(payload: dict[str, Any]) -> str:
    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()
