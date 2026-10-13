"""Source validation for extracted natural-language scene reviews."""

from __future__ import annotations

from typing import Any, Mapping
from .natural_transport_repair import NaturalSourceClarificationError,NaturalExtractionError
from .commission_source_format import restore_review_evidence,quoted_review_evidence
from literary_engineering_studio_engine.public.literary import validate_current_review, SceneConsistencyError


_ISSUE_PROGRESS = {"resolved", "persists", "changed", "uncertain"}


def validate_review_extraction(payload: Mapping[str, Any], context: Mapping[str, Any], source_answer=None) -> None:
    if context.get('creation_integrity_contract'):
        try:
            validate_current_review(payload, str(context.get('prose') or ''))
        except SceneConsistencyError as error:
            raise NaturalSourceClarificationError(str(error), fields=error.fields, payload=dict(payload)) from error
    _reject_inherited_judgments(payload,context,source_answer)
    prose = str(context.get("prose") or "")
    restore_review_evidence(prose,payload)
    _project_partial_progress(payload)
    open_ids = _open_issue_ids(context)
    _project_historical_progress(payload,context,open_ids,source_answer)
    try:
        for group, evidence_required in (("strengths", True), ("major_issues", True),
                                         ("optional_explorations", False)):
            _validate_findings(payload.get(group) or [], group, evidence_required, prose, open_ids)
        _validate_progress(payload.get("issue_progress") or [], prose, open_ids)
    except ValueError as error:
        if context.get('creation_integrity_contract'):
            raise NaturalSourceClarificationError(str(error)+'；由原审读者更正编号或当前稿判断。',
                fields=('/major_issues', '/issue_progress', '/decision', '/summary'), payload=dict(payload)) from error
        _require_review_source_clarification(payload,prose,open_ids,source_answer,error)
        raise


def _reject_inherited_judgments(payload,context,source):
    if not isinstance(source,str):
        return
    previous=((context.get('review_continuity') or {}).get('previous') or {}).get('review') or {}
    summary=str(payload.get('summary') or '').strip()
    directions=payload.get('revision_instructions')
    if (summary and summary not in source and str(previous.get('summary') or '').startswith(summary)
            and directions and directions==previous.get('revision_instructions')):
        raise NaturalExtractionError('review extraction copied historical judgments instead of the current source',
            fields=('/summary','/major_issues','/optional_explorations','/revision_instructions'),payload=dict(payload))


def _project_partial_progress(payload):
    for row in payload.get('issue_progress') or []:
        if isinstance(row, dict) and row.get('status') == 'partially_resolved':
            row['source_progress_status'] = row['status']
            row['status'] = 'persists'


def _project_historical_progress(payload,context,open_ids,source):
    if not isinstance(source,str):
        return
    previous=(context.get('review_continuity') or {}).get('previous') or {}
    closed={row.get('issue_id') for row in previous.get('issues') or [] if row.get('status')=='resolved'}
    historical=[];current=[]
    for row in payload.get('issue_progress') or []:
        identifier=row.get('issue_id') if isinstance(row,dict) else None
        if identifier in closed and identifier not in open_ids and row.get('status')=='resolved' and identifier in source:
            historical.append(row)
        else:
            current.append(row)
    if historical:
        payload['historical_issue_progress']=historical
        payload['issue_progress']=current


def _require_review_source_clarification(payload,prose,open_ids,answer,error):
    if not isinstance(answer,str):
        return
    if 'quote the current prose exactly' in str(error):
        technical,fields=_evidence_failures(payload,prose,answer)
        if technical:
            raise NaturalExtractionError(str(error),fields=technical) from error
        if fields:
            raise NaturalSourceClarificationError(str(error)+'；仅对齐失败引句，保持原判断及总结。',
                fields=fields,payload=dict(payload)) from error
    if 'review issue progress' in str(error) and not all(ident in answer for ident in open_ids):
        raise NaturalSourceClarificationError(str(error)+'；请逐项写出当前已有问题的编号与本稿证据。',
                fields=("/issue_progress",),payload=dict(payload)) from error


def _evidence_failures(payload,prose,answer):
    technical,semantic=[],[]
    for group in ('strengths','major_issues','optional_explorations','issue_progress'):
        for index,row in enumerate(payload.get(group) or []):
            evidence=row.get('evidence','') if isinstance(row,dict) else ''
            if evidence and evidence not in prose:
                target=semantic if quoted_review_evidence(answer,evidence) else technical
                target.append(f'/{group}/{index}/evidence')
    return technical,semantic


def _open_issue_ids(context: Mapping[str, Any]) -> set[str]:
    continuity = context.get("review_continuity") or {}
    return {str(item.get("issue_id") or "") for item in continuity.get("open_issues") or []
            if isinstance(item, Mapping) and item.get("issue_id")}


def _validate_findings(rows: Any, group: str, required: bool, prose: str, open_ids: set[str]) -> None:
    if not isinstance(rows, list):
        raise ValueError(f"review extraction {group} must be a list")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"review extraction {group} contains an invalid item")
        evidence = str(row.get("evidence") or "")
        if required and not evidence.strip():
            raise ValueError(f"review {group} needs exact prose evidence")
        _validate_current_evidence(evidence, prose, f"review {group} evidence")
        _validate_prior_issue_link(str(row.get("prior_issue_id") or ""), open_ids)


def _validate_progress(rows: Any, prose: str, open_ids: set[str]) -> None:
    if not isinstance(rows, list):
        raise ValueError("review issue progress must be a list")
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("review issue progress contains an invalid item")
        identifier = str(row.get("issue_id") or "")
        status = str(row.get("status") or "")
        if identifier not in open_ids or identifier in seen:
            raise ValueError("review issue progress must reference each current open issue once")
        if status not in _ISSUE_PROGRESS:
            raise ValueError("review issue progress status is invalid")
        seen.add(identifier)
        _validate_current_evidence(str(row.get("evidence") or ""), prose,
                                   "review issue progress evidence")
    if seen != open_ids:
        raise ValueError("review issue progress must cover all current open issues")


def _validate_prior_issue_link(identifier: str, open_ids: set[str]) -> None:
    if identifier and identifier not in open_ids:
        raise ValueError("review issue link is outside the open issue list")


def _validate_current_evidence(evidence: str, prose: str, label: str) -> None:
    if evidence and evidence not in prose:
        raise ValueError(f"{label} must quote the current prose exactly")


__all__ = ["validate_review_extraction"]
