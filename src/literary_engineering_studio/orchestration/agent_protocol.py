"""Structured Planner/Reviewer exchange without project write authority."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any, Mapping

from .profiles import OrchestrationAgentRole, orchestration_profile


AGENT_REQUEST_SCHEMA = "arcvellum/orchestration-agent-request/v1"
REVIEW_JUDGMENT_SCHEMA = "arcvellum/orchestration-review-judgment/v1"
REVIEW_RECEIPT_SCHEMA = "arcvellum/orchestration-review/v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class OrchestrationReviewVerdict(str, Enum):
    PASS = "pass"
    PASS_WITH_NOTES = "pass_with_notes"
    FAIL = "fail"


@dataclass(frozen=True)
class OrchestrationAgentRequest:
    request_id: str
    session_id: str
    role: OrchestrationAgentRole
    objective: str
    context_ledger_id: str
    context_ledger_digest: str
    subject_digests: tuple[str, ...]

    def __post_init__(self) -> None:
        profile = orchestration_profile(self.role)
        for name, value in (
            ("request_id", self.request_id),
            ("session_id", self.session_id),
            ("objective", self.objective),
            ("context_ledger_id", self.context_ledger_id),
        ):
            if not value.strip():
                raise ValueError(f"orchestration request {name} is required")
        _require_digest(self.context_ledger_digest, "context ledger")
        for digest in self.subject_digests:
            _require_digest(digest, "subject")
        if profile.can_write_formal_files or profile.can_activate_plan:
            raise ValueError("orchestration profiles cannot own formal write authority")

    def as_dict(self) -> dict[str, object]:
        profile = orchestration_profile(self.role)
        return {
            "schema": AGENT_REQUEST_SCHEMA,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "role": self.role.value,
            "profile": profile.as_dict(),
            "objective": self.objective,
            "context_ledger_id": self.context_ledger_id,
            "context_ledger_digest": self.context_ledger_digest,
            "subject_digests": list(self.subject_digests),
            "output_schema": profile.output_schema,
            "emission_mode": profile.emission_mode,
        }


@dataclass(frozen=True)
class ReviewFinding:
    severity: str
    rule_id: str
    message: str
    required_change: str

    def __post_init__(self) -> None:
        if self.severity not in {"note", "warning", "error"}:
            raise ValueError(f"unsupported review finding severity: {self.severity}")
        if not self.rule_id.strip() or not self.message.strip():
            raise ValueError("review finding rule_id and message are required")
        if self.severity == "error" and not self.required_change.strip():
            raise ValueError("error findings require a concrete change")

    def as_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "rule_id": self.rule_id,
            "message": self.message,
            "required_change": self.required_change,
        }


@dataclass(frozen=True)
class ReviewJudgmentCandidate:
    verdict: OrchestrationReviewVerdict
    summary: str
    findings: tuple[ReviewFinding, ...]


@dataclass(frozen=True)
class OrchestrationReviewReceipt:
    plan_id: str
    plan_revision: int
    planner_session_id: str
    reviewer_session_id: str
    context_ledger_digest: str
    candidate_digest: str
    plan_digest: str
    graph_digest: str
    simulation_digest: str
    verdict: OrchestrationReviewVerdict
    summary: str
    findings: tuple[ReviewFinding, ...]

    def __post_init__(self) -> None:
        _validate_review_identity(self)
        _validate_review_digests(self)
        _validate_review_verdict(self)

    @property
    def activation_eligible(self) -> bool:
        return self.verdict is OrchestrationReviewVerdict.PASS

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": REVIEW_RECEIPT_SCHEMA,
            "status": self.verdict.value,
            "plan_id": self.plan_id,
            "plan_revision": self.plan_revision,
            "planner_session_id": self.planner_session_id,
            "reviewer_session_id": self.reviewer_session_id,
            "independent_reviewer": True,
            "context_ledger_digest": self.context_ledger_digest,
            "candidate_digest": self.candidate_digest,
            "plan_digest": self.plan_digest,
            "graph_digest": self.graph_digest,
            "simulation_digest": self.simulation_digest,
            "summary": self.summary,
            "findings": [item.as_dict() for item in self.findings],
        }


def parse_review_judgment(payload: Mapping[str, Any]) -> ReviewJudgmentCandidate:
    if str(payload.get("schema") or "") != REVIEW_JUDGMENT_SCHEMA:
        raise ValueError(f"review judgment schema must be {REVIEW_JUDGMENT_SCHEMA}")
    allowed = {"schema", "verdict", "summary", "findings"}
    unknown = sorted(set(payload).difference(allowed))
    if unknown:
        raise ValueError("review judgment contains machine-owned or unknown fields: " + ", ".join(unknown))
    findings_payload = payload.get("findings")
    if not isinstance(findings_payload, list):
        raise ValueError("review judgment findings must be a list")
    findings = tuple(
        ReviewFinding(
            severity=_required(item, "severity"),
            rule_id=_required(item, "rule_id"),
            message=_required(item, "message"),
            required_change=str(item.get("required_change") or "").strip(),
        )
        for item in findings_payload
        if isinstance(item, Mapping)
    )
    if len(findings) != len(findings_payload):
        raise ValueError("review judgment findings must contain objects")
    return ReviewJudgmentCandidate(
        verdict=OrchestrationReviewVerdict(_required(payload, "verdict")),
        summary=_required(payload, "summary"),
        findings=findings,
    )


def seal_orchestration_review(
    judgment: ReviewJudgmentCandidate,
    *,
    plan_id: str,
    plan_revision: int,
    planner_session_id: str,
    reviewer_session_id: str,
    context_ledger_digest: str,
    candidate_digest: str,
    plan_digest: str,
    graph_digest: str,
    simulation_digest: str,
) -> OrchestrationReviewReceipt:
    return OrchestrationReviewReceipt(
        plan_id=plan_id,
        plan_revision=plan_revision,
        planner_session_id=planner_session_id,
        reviewer_session_id=reviewer_session_id,
        context_ledger_digest=context_ledger_digest,
        candidate_digest=candidate_digest,
        plan_digest=plan_digest,
        graph_digest=graph_digest,
        simulation_digest=simulation_digest,
        verdict=judgment.verdict,
        summary=judgment.summary,
        findings=judgment.findings,
    )


def _required(payload: Mapping[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise ValueError(f"review judgment {key} is required")
    return value


def _validate_review_identity(receipt: OrchestrationReviewReceipt) -> None:
    if not receipt.plan_id.strip() or receipt.plan_revision < 1:
        raise ValueError("orchestration review plan identity is invalid")
    if not receipt.planner_session_id.strip() or not receipt.reviewer_session_id.strip():
        raise ValueError("orchestration review requires both session identities")
    if receipt.planner_session_id == receipt.reviewer_session_id:
        raise ValueError("orchestration reviewer must use an independent session")
    if not receipt.summary.strip():
        raise ValueError("orchestration review summary is required")


def _validate_review_digests(receipt: OrchestrationReviewReceipt) -> None:
    for name, digest in (
        ("context ledger", receipt.context_ledger_digest),
        ("candidate", receipt.candidate_digest),
        ("plan", receipt.plan_digest),
        ("graph", receipt.graph_digest),
        ("simulation", receipt.simulation_digest),
    ):
        _require_digest(digest, name)


def _validate_review_verdict(receipt: OrchestrationReviewReceipt) -> None:
    has_error = any(item.severity == "error" for item in receipt.findings)
    if receipt.verdict == OrchestrationReviewVerdict.PASS and receipt.findings:
        raise ValueError("a passing orchestration review cannot retain findings")
    if receipt.verdict == OrchestrationReviewVerdict.PASS_WITH_NOTES and not receipt.findings:
        raise ValueError("pass_with_notes requires at least one finding")
    if receipt.verdict == OrchestrationReviewVerdict.PASS_WITH_NOTES and has_error:
        raise ValueError("pass_with_notes cannot retain error findings")
    if receipt.verdict == OrchestrationReviewVerdict.FAIL and not has_error:
        raise ValueError("a failed orchestration review requires an error finding")


def _require_digest(value: str, label: str) -> None:
    if not _SHA256.fullmatch(value):
        raise ValueError(f"{label} digest must be a lowercase SHA-256")
