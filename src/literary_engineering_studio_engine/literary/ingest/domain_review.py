"""Independent domain-review contract for reconstructed project candidates."""

from __future__ import annotations

from typing import Any

from .evidence import canonical_digest
from .reconstruction_contracts import (
    ARCHAEOLOGY_DOMAINS,
    ASSET_DECISIONS,
    DOMAIN_REVIEW_SCHEMA,
    REVIEW_STATUSES,
    _identity_errors,
)


def validate_domain_review(
    payload: dict[str, Any],
    *,
    manifest: dict[str, Any],
    candidate: dict[str, Any],
) -> list[str]:
    mode = str(manifest.get("mode") or "")
    errors = _identity_errors(
        payload,
        schema=DOMAIN_REVIEW_SCHEMA,
        work_id=str(manifest.get("work_id") or ""),
        mode=mode,
        candidate_revision=str(candidate.get("revision") or ""),
    )
    status = str(payload.get("status") or "")
    if status not in REVIEW_STATUSES:
        errors.append(f"domain review status must be one of {sorted(REVIEW_STATUSES)}")
    if str(candidate.get("revision") or "") != canonical_digest(candidate):
        errors.append("reconstruction candidate revision does not match its content")
    reviews = payload.get("domain_reviews")
    if not isinstance(reviews, list):
        return [*errors, "domain review domain_reviews must be a list"]
    review_errors, reviewed_domains, blocking_count = _domain_review_errors(reviews)
    errors.extend(review_errors)
    missing_domains = sorted(set(ARCHAEOLOGY_DOMAINS) - reviewed_domains)
    if missing_domains:
        errors.append("domain review omits domains: " + ", ".join(missing_domains))
    errors.extend(_asset_decision_errors(payload, candidate, mode))
    if status == "pass" and blocking_count:
        errors.append("domain review cannot pass while domain blockers remain")
    return errors


def _domain_review_errors(
    reviews: list[object],
) -> tuple[list[str], set[str], int]:
    errors: list[str] = []
    reviewed_domains: set[str] = set()
    blocking_count = 0
    for index, review in enumerate(reviews):
        item_errors, domain, count = _domain_review_item_errors(
            review,
            index=index,
            reviewed_domains=reviewed_domains,
        )
        errors.extend(item_errors)
        if domain:
            reviewed_domains.add(domain)
        blocking_count += count
    return errors, reviewed_domains, blocking_count


def _domain_review_item_errors(
    review: object,
    *,
    index: int,
    reviewed_domains: set[str],
) -> tuple[list[str], str, int]:
    prefix = f"domain_reviews[{index}]"
    if not isinstance(review, dict):
        return [f"{prefix} must be an object"], "", 0
    errors: list[str] = []
    domain = str(review.get("domain") or "")
    if domain not in ARCHAEOLOGY_DOMAINS:
        errors.append(f"{prefix}.domain must be one of {list(ARCHAEOLOGY_DOMAINS)}")
    if domain in reviewed_domains:
        errors.append(f"duplicate domain review: {domain}")
    status = str(review.get("status") or "")
    if status not in REVIEW_STATUSES:
        errors.append(f"{prefix}.status must be one of {sorted(REVIEW_STATUSES)}")
    blockers = review.get("blocking_issues")
    warnings = review.get("warnings")
    if not isinstance(blockers, list) or not isinstance(warnings, list):
        errors.append(f"{prefix} blocking_issues and warnings must be lists")
    if status == "pass" and blockers:
        errors.append(f"{prefix} cannot pass with blocking issues")
    return errors, domain, len(blockers) if isinstance(blockers, list) else 0


def _asset_decision_errors(
    payload: dict[str, Any],
    candidate: dict[str, Any],
    mode: str,
) -> list[str]:
    assets = candidate.get("assets")
    expected = {
        str(item.get("candidate_id") or "")
        for item in assets
        if isinstance(item, dict)
    } if isinstance(assets, list) else set()
    decisions = payload.get("asset_decisions")
    if not isinstance(decisions, list):
        return ["domain review asset_decisions must be a list"]
    errors, seen = _asset_decision_list_errors(decisions, expected=expected, mode=mode)
    if set(seen) != expected or len(seen) != len(set(seen)):
        errors.append("asset decisions must cover every reconstruction asset exactly once")
    return errors


def _asset_decision_list_errors(
    decisions: list[object],
    *,
    expected: set[str],
    mode: str,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    seen: list[str] = []
    for index, decision in enumerate(decisions):
        item_errors, candidate_id = _asset_decision_item_errors(
            decision,
            index=index,
            expected=expected,
            mode=mode,
        )
        errors.extend(item_errors)
        seen.append(candidate_id)
    return errors, seen


def _asset_decision_item_errors(
    decision: object,
    *,
    index: int,
    expected: set[str],
    mode: str,
) -> tuple[list[str], str]:
    prefix = f"asset_decisions[{index}]"
    if not isinstance(decision, dict):
        return [f"{prefix} must be an object"], ""
    errors: list[str] = []
    candidate_id = str(decision.get("candidate_id") or "")
    if candidate_id not in expected:
        errors.append(f"{prefix}.candidate_id is not in the reconstruction")
    value = str(decision.get("decision") or "")
    if value not in ASSET_DECISIONS:
        errors.append(f"{prefix}.decision must be one of {sorted(ASSET_DECISIONS)}")
    if mode == "analysis" and value != "analysis_only":
        errors.append(f"{prefix} must be analysis_only in analysis mode")
    invalid_lists = [
        field
        for field in ("blocking_issues", "warnings")
        if not isinstance(decision.get(field), list)
    ]
    errors.extend(f"{prefix}.{field} must be a list" for field in invalid_lists)
    if value == "promote" and decision.get("blocking_issues"):
        errors.append(f"{prefix} cannot promote with blocking issues")
    return errors, candidate_id
