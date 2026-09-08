"""User-facing projection of lean scene transactions."""

from __future__ import annotations

from typing import Any, Iterable

from ...application.scene_transaction import SceneTransaction
from literary_engineering_studio_engine.literary.scene.transaction import (
    SceneTransactionStatus,
)


_TERMINAL = {
    SceneTransactionStatus.COMMITTED,
    SceneTransactionStatus.CANCELLED,
}


def scene_transaction_summary(transaction: SceneTransaction) -> dict[str, Any]:
    verification = transaction.verification
    review = transaction.review
    requires_input = (
        transaction.status is SceneTransactionStatus.BLOCKED
        or (
            transaction.status is SceneTransactionStatus.COMMITTABLE
            and transaction.policy.steward_approval_required
        )
    )
    return {
        "transaction_id": transaction.transaction_id,
        "scene_id": transaction.scene_id,
        "status": transaction.status.value,
        "mode": transaction.mode.value,
        "risk": transaction.brief.risk.level.value,
        "objective": transaction.brief.objective,
        "scene_function": transaction.brief.scene_function,
        "body_hanzi": verification.body_hanzi if verification else 0,
        "warning_count": len(verification.warnings) if verification else 0,
        "hard_issue_count": len(verification.hard_failures) if verification else 0,
        "review_decision": review.decision.value if review else "",
        "review_summary": review.summary if review else "",
        "revision_attempts": transaction.revision_attempts,
        "requires_input": requires_input,
        "message": transaction.last_error,
        "version": transaction.version,
    }


def project_scene_transactions(
    transactions: Iterable[SceneTransaction],
) -> list[dict[str, Any]]:
    """Keep the latest transaction for each scene in repository order."""

    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for transaction in transactions:
        if transaction.scene_id in seen:
            continue
        seen.add(transaction.scene_id)
        result.append(scene_transaction_summary(transaction))
    return result


def active_scene_transaction(
    summaries: Iterable[dict[str, Any]],
) -> dict[str, Any] | None:
    values = list(summaries)
    for item in values:
        try:
            status = SceneTransactionStatus(str(item.get("status") or ""))
        except ValueError:
            continue
        if status not in _TERMINAL:
            return item
    return values[0] if values else None


__all__ = [
    "active_scene_transaction",
    "project_scene_transactions",
    "scene_transaction_summary",
]
