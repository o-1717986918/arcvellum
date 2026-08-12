"""Shared semantics for actionable and informational scene-review findings."""

from __future__ import annotations

from typing import Any


NON_BLOCKING_RESOLUTIONS = {
    "noted_below_threshold",
    "waived",
    "not_required",
    "non_blocking",
    "non-blocking",
}
NON_BLOCKING_SEVERITIES = {"info", "note", "neutral", "positive"}


def finding_requires_followup(value: object) -> bool:
    """Return whether a warning/deviation represents unresolved work."""

    if not isinstance(value, dict):
        return True
    if value.get("blocks_pass") is False:
        return False
    resolution = str(value.get("resolution") or value.get("status") or "").strip().lower()
    if resolution in NON_BLOCKING_RESOLUTIONS:
        return False
    severity = str(value.get("severity") or "").strip().lower()
    if severity in NON_BLOCKING_SEVERITIES:
        return False
    text = " ".join(
        str(value.get(key) or "")
        for key in ("message", "detail", "description", "note")
    ).lower()
    markers = (
        "不作为阻塞",
        "不阻塞",
        "低于阈值",
        "已登记豁免",
        "not blocking",
        "below threshold",
        "waived",
    )
    return not any(marker in text for marker in markers)


def actionable_review_findings(payload: dict[str, Any]) -> list[str]:
    """List unresolved semantic findings without counting the verdict itself."""

    findings: list[str] = []
    for key in ("blocking_issues", "revision_actions"):
        if isinstance(payload.get(key), list) and payload.get(key):
            findings.append(key)
    warnings = payload.get("warnings")
    if isinstance(warnings, list) and any(finding_requires_followup(item) for item in warnings):
        findings.append("warnings")
    style = payload.get("style_adherence")
    if isinstance(style, dict):
        status = str(style.get("status") or "").strip().lower()
        if status in {"pass_with_notes", "revise_required", "reject"}:
            findings.append(f"style_adherence.status={status}")
        deviations = style.get("deviations")
        if isinstance(deviations, list) and any(
            finding_requires_followup(item) for item in deviations
        ):
            findings.append("style_adherence.deviations")
        if isinstance(style.get("revision_actions"), list) and style.get("revision_actions"):
            findings.append("style_adherence.revision_actions")
    return findings


def review_semantic_consistency_issues(payload: dict[str, Any]) -> list[str]:
    """Reject verdict/finding combinations that manufacture revision loops."""

    conclusion = str(payload.get("conclusion") or "").strip().lower()
    actionable = actionable_review_findings(payload)
    issues: list[str] = []
    if conclusion == "pass" and actionable:
        issues.append("conclusion=pass contains unresolved actionable findings: " + ", ".join(actionable))
    if conclusion in {"pass_with_notes", "revise_required"} and not actionable:
        issues.append(
            f"conclusion={conclusion} has no actionable finding; informational or below-threshold observations belong under clean pass"
        )
    for index, item in enumerate(payload.get("revision_actions") or []):
        if isinstance(item, dict) and item.get("blocks_pass") is False:
            issues.append(
                f"revision_actions[{index}] declares blocks_pass=false; move it to a non-blocking warning/style note or make it genuinely actionable"
            )
    return issues


__all__ = [
    "actionable_review_findings",
    "finding_requires_followup",
    "review_semantic_consistency_issues",
]
