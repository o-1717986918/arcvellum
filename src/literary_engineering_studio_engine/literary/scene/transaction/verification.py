"""Deterministic verification for lean creative output."""

from __future__ import annotations

from collections.abc import Collection
import re

from ....foundation.draft_text import count_delivery_chinese_content_chars
from ...style.anti_ai import style_lint_gate
from ...style.punctuation import lint_punctuation
from .contracts import (
    CreativeResult,
    IssueSeverity,
    SceneBrief,
    VerificationIssue,
    VerificationReport,
)
from .policy import ScenePolicy


_PROCESS_TRACE_PATTERNS = (
    re.compile(r"\[AGENT_TASK\s*:", re.IGNORECASE),
    re.compile(
        r"(?:^|\n)\s*#{1,6}\s*(?:工作流|流程记录|canon\s+audit|review\s+report)",
        re.IGNORECASE,
    ),
    re.compile(r"(?:task[_ -]?complete|completion[_ -]?marker|expected_outputs)", re.IGNORECASE),
)

_HARD_PUNCTUATION_RULES = frozenset(
    {
        "ascii-punctuation-in-chinese",
        "ascii-ellipsis",
        "ascii-dash",
        "western-quotes-in-chinese",
        "corner-quotes-in-horizontal-prose",
        "punctuation-spacing",
        "repeated-terminal-punctuation",
        "repeated-punctuation",
    }
)


def verify_creative_result(
    brief: SceneBrief,
    result: CreativeResult,
    policy: ScenePolicy,
    *,
    known_refs: Collection[str] = (),
    quality_profile: dict[str, object] | None = None,
) -> VerificationReport:
    """Check machine-verifiable output without making literary judgments."""

    issues: list[VerificationIssue] = []
    prose = result.prose.strip()
    body_hanzi = count_delivery_chinese_content_chars(prose)

    if not prose:
        issues.append(_issue("empty-prose", IssueSeverity.HARD, "scene prose is empty"))
    if not result.decision_summary.strip():
        issues.append(
            _issue(
                "missing-decision-summary",
                IssueSeverity.HARD,
                "creative result must explain the scene-level decision briefly",
            )
        )
    if policy.explicit_decision_trace_required and not result.decision_trace:
        issues.append(
            _issue(
                "missing-decision-trace",
                IssueSeverity.HARD,
                "high-risk policy requires a compact decision trace",
            )
        )

    for pattern in _PROCESS_TRACE_PATTERNS:
        match = pattern.search(prose)
        if match:
            issues.append(
                _issue(
                    "process-trace-in-prose",
                    IssueSeverity.HARD,
                    "formal prose contains workflow or agent-task residue",
                    match.group(0)[:120],
                )
            )
            break

    _append_length_issues(issues, brief, body_hanzi)
    _append_language_issues(issues, prose, quality_profile, scope=brief.scene_id)
    _append_delta_issues(issues, result, known_refs)
    if result.escalation_reasons:
        issues.append(
            _issue(
                "writer-requested-escalation",
                IssueSeverity.WARNING,
                "the writer requested additional review",
                "; ".join(result.escalation_reasons),
            )
        )
    return VerificationReport(
        scene_id=brief.scene_id,
        body_hanzi=body_hanzi,
        issues=tuple(issues),
    )


def _append_length_issues(
    issues: list[VerificationIssue],
    brief: SceneBrief,
    body_hanzi: int,
) -> None:
    target = brief.length
    if target.soft_min and body_hanzi < target.soft_min:
        issues.append(
            _issue(
                "below-soft-length",
                IssueSeverity.WARNING,
                f"body has {body_hanzi} Chinese content characters; soft minimum is {target.soft_min}",
            )
        )
    if target.soft_max and body_hanzi > target.soft_max:
        issues.append(
            _issue(
                "above-soft-length",
                IssueSeverity.WARNING,
                f"body has {body_hanzi} Chinese content characters; soft maximum is {target.soft_max}",
            )
        )


def _append_delta_issues(
    issues: list[VerificationIssue],
    result: CreativeResult,
    known_refs: Collection[str],
) -> None:
    known = set(known_refs)
    seen: set[tuple[str, str, str]] = set()
    existing_groups = (
        result.scene_delta.character_changes,
        result.scene_delta.canon_candidates,
        result.scene_delta.continuity_changes,
        result.scene_delta.promise_updates,
        result.scene_delta.reader_question_updates,
    )
    for proposals in existing_groups:
        for proposal in proposals:
            if not proposal.target_ref.strip():
                issues.append(
                    _issue(
                        "missing-delta-target",
                        IssueSeverity.HARD,
                        "a semantic change is missing target_ref",
                        proposal.summary,
                    )
                )
            elif known and proposal.target_ref not in known:
                issues.append(
                    _issue(
                        "unknown-delta-target",
                        IssueSeverity.HARD,
                        f"SceneDelta target does not exist in the prepared context: {proposal.target_ref}",
                    )
                )
            if not proposal.summary.strip():
                issues.append(
                    _issue(
                        "missing-delta-summary",
                        IssueSeverity.HARD,
                        "a semantic change is missing its summary",
                        proposal.target_ref,
                    )
                )
            fingerprint = (proposal.target_ref, proposal.operation, proposal.summary)
            if fingerprint in seen:
                issues.append(
                    _issue(
                        "duplicate-delta-change",
                        IssueSeverity.WARNING,
                        "SceneDelta repeats the same semantic change",
                        proposal.target_ref,
                    )
                )
            seen.add(fingerprint)

    for proposal in result.scene_delta.new_asset_candidates:
        if not proposal.summary.strip():
            issues.append(
                _issue(
                    "missing-new-asset-summary",
                    IssueSeverity.HARD,
                    "a new asset candidate requires a summary",
                    proposal.target_ref,
                )
            )


def _append_language_issues(
    issues: list[VerificationIssue],
    prose: str,
    profile: dict[str, object] | None,
    *,
    scope: str,
) -> None:
    style = style_lint_gate(prose, profile=profile, scope=scope)
    for row in style.get("blocking", []):
        if not isinstance(row, dict):
            continue
        issues.append(
            _issue(
                f"style-{row.get('rule') or 'lint'}",
                IssueSeverity.HARD,
                str(row.get("message") or "prose failed the configured style lint"),
                str(row.get("sample") or ""),
            )
        )
    for row in style.get("notes", []):
        if not isinstance(row, dict):
            continue
        issues.append(
            _issue(
                f"style-{row.get('rule') or 'lint'}",
                IssueSeverity.WARNING,
                str(row.get("message") or "prose has a style lint note"),
                str(row.get("sample") or ""),
            )
        )
    for finding in lint_punctuation(prose, profile=profile, scope=scope):
        severity = (
            IssueSeverity.HARD
            if finding.rule in _HARD_PUNCTUATION_RULES
            else IssueSeverity.WARNING
        )
        issues.append(
            _issue(
                f"punctuation-{finding.rule}",
                severity,
                finding.message,
                finding.sample,
            )
        )


def _issue(
    code: str,
    severity: IssueSeverity,
    message: str,
    evidence: str = "",
) -> VerificationIssue:
    return VerificationIssue(code=code, severity=severity, message=message, evidence=evidence)


__all__ = ["verify_creative_result"]
