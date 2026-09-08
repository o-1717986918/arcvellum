"""Serialization boundary for persisted lean scene transactions."""

from __future__ import annotations

from typing import Any

from literary_engineering_studio_engine.public.literary import (
    ChangeProposal,
    CreativeResult,
    IssueSeverity,
    LengthTarget,
    ReviewDecision,
    ReviewResult,
    RhythmDirective,
    SceneBrief,
    SceneDelta,
    SceneExecutionMode,
    ScenePolicy,
    SceneRisk,
    SceneRiskLevel,
    SceneTransactionStatus,
    StyleMountRef,
    VerificationIssue,
    VerificationReport,
)

from .scene_transaction import SceneCommitReceipt, SceneTransaction


def scene_transaction_from_dict(payload: dict[str, Any]) -> SceneTransaction:
    return SceneTransaction(
        transaction_id=str(payload["transaction_id"]),
        project_root=str(payload["project_root"]),
        scene_id=str(payload["scene_id"]),
        mode=SceneExecutionMode(str(payload["mode"])),
        status=SceneTransactionStatus(str(payload["status"])),
        base_revision=str(payload["base_revision"]),
        brief=_brief(dict(payload["brief"])),
        policy=_policy(dict(payload["policy"])),
        creative_result=_creative_result(payload.get("creative_result")),
        verification=_verification(payload.get("verification")),
        review=_review(payload.get("review")),
        commit_receipt=_receipt(payload.get("commit_receipt")),
        revision_attempts=int(payload.get("revision_attempts") or 0),
        blocked_from=str(payload.get("blocked_from") or ""),
        last_error=str(payload.get("last_error") or ""),
        version=int(payload.get("version") or 0),
    )


def _brief(value: dict[str, Any]) -> SceneBrief:
    risk = _risk(dict(value["risk"]))
    return SceneBrief(
        scene_id=str(value["scene_id"]),
        objective=str(value["objective"]),
        scene_function=str(value["scene_function"]),
        participants=tuple(value.get("participants") or ()),
        canon_constraints=tuple(value.get("canon_constraints") or ()),
        incoming_handoff=tuple(value.get("incoming_handoff") or ()),
        chapter_obligations=tuple(value.get("chapter_obligations") or ()),
        rhythm=RhythmDirective(**dict(value.get("rhythm") or {})),
        length=LengthTarget(**dict(value.get("length") or {})),
        style_mount=StyleMountRef(**dict(value.get("style_mount") or {})),
        risk=risk,
        source_refs=tuple(value.get("source_refs") or ()),
        viewpoint=str(value.get("viewpoint") or ""),
        location=str(value.get("location") or ""),
        external_conflict=str(value.get("external_conflict") or ""),
        internal_conflict=str(value.get("internal_conflict") or ""),
    )


def _policy(value: dict[str, Any]) -> ScenePolicy:
    return ScenePolicy(
        mode=SceneExecutionMode(str(value["mode"])),
        risk=_risk(dict(value["risk"])),
        independent_review_required=bool(value["independent_review_required"]),
        explicit_decision_trace_required=bool(value["explicit_decision_trace_required"]),
        defer_semantic_review_to_chapter=bool(value["defer_semantic_review_to_chapter"]),
        automatic_revision_allowed=bool(value["automatic_revision_allowed"]),
        max_revision_attempts=int(value["max_revision_attempts"]),
        steward_approval_required=bool(value["steward_approval_required"]),
    )


def _risk(value: dict[str, Any]) -> SceneRisk:
    return SceneRisk(
        SceneRiskLevel(str(value["level"])),
        tuple(value.get("reasons") or ()),
    )


def _creative_result(value: Any) -> CreativeResult | None:
    if not isinstance(value, dict):
        return None
    delta = dict(value.get("scene_delta") or {})
    return CreativeResult(
        prose=str(value.get("prose") or ""),
        decision_summary=str(value.get("decision_summary") or ""),
        scene_delta=_scene_delta(delta),
        decision_trace=tuple(value.get("decision_trace") or ()),
        escalation_reasons=tuple(value.get("escalation_reasons") or ()),
    )


def _scene_delta(value: dict[str, Any]) -> SceneDelta:
    return SceneDelta(
        character_changes=_proposals(value.get("character_changes")),
        canon_candidates=_proposals(value.get("canon_candidates")),
        continuity_changes=_proposals(value.get("continuity_changes")),
        promise_updates=_proposals(value.get("promise_updates")),
        reader_question_updates=_proposals(value.get("reader_question_updates")),
        next_handoff=tuple(value.get("next_handoff") or ()),
        new_asset_candidates=_proposals(value.get("new_asset_candidates")),
    )


def _proposals(value: Any) -> tuple[ChangeProposal, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(
        ChangeProposal(
            target_ref=str(item.get("target_ref") or ""),
            summary=str(item.get("summary") or ""),
            evidence=str(item.get("evidence") or ""),
            operation=str(item.get("operation") or "update"),
            attributes=tuple(tuple(pair) for pair in item.get("attributes") or ()),
        )
        for item in value
        if isinstance(item, dict)
    )


def _verification(value: Any) -> VerificationReport | None:
    if not isinstance(value, dict):
        return None
    return VerificationReport(
        scene_id=str(value.get("scene_id") or ""),
        body_hanzi=int(value.get("body_hanzi") or 0),
        issues=tuple(_verification_issue(item) for item in value.get("issues") or () if isinstance(item, dict)),
    )


def _verification_issue(value: dict[str, Any]) -> VerificationIssue:
    return VerificationIssue(
        code=str(value.get("code") or ""),
        severity=IssueSeverity(str(value.get("severity") or "warning")),
        message=str(value.get("message") or ""),
        evidence=str(value.get("evidence") or ""),
    )


def _review(value: Any) -> ReviewResult | None:
    if not isinstance(value, dict):
        return None
    return ReviewResult(
        decision=ReviewDecision(str(value.get("decision") or "pass")),
        summary=str(value.get("summary") or ""),
        revision_instructions=tuple(value.get("revision_instructions") or ()),
        evidence=tuple(value.get("evidence") or ()),
    )


def _receipt(value: Any) -> SceneCommitReceipt | None:
    if not isinstance(value, dict):
        return None
    return SceneCommitReceipt(
        transaction_id=str(value.get("transaction_id") or ""),
        scene_id=str(value.get("scene_id") or ""),
        committed_revision=str(value.get("committed_revision") or ""),
        written_refs=tuple(value.get("written_refs") or ()),
    )


__all__ = ["scene_transaction_from_dict"]
