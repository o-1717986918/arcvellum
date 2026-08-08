"""Validation and normalization for Agent-authored scene branch proposals."""

from __future__ import annotations

import json
import re
from typing import Any


REQUIRED_PROPOSAL_FIELDS = (
    "branch_id",
    "title",
    "strategy",
    "causal_premise",
    "action_chain",
    "cost",
    "reader_effect",
    "state_writeback",
)


def branch_proposal_quality_errors(payload: dict[str, Any], relative: str) -> list[str]:
    """Reject schema-shaped proposals that are cosmetic variants."""

    proposals = payload.get("proposals")
    if not isinstance(proposals, list) or not 2 <= len(proposals) <= 5:
        return [f"branch semantic artifact requires 2-5 proposals: {relative}"]

    errors: list[str] = []
    valid: list[dict[str, Any]] = []
    for index, proposal in enumerate(proposals):
        if not isinstance(proposal, dict):
            errors.append(f"branch proposal {index + 1} must be an object: {relative}")
            continue
        errors.extend(_proposal_errors(proposal, index, relative))
        valid.append(proposal)
    errors.extend(_diversity_errors(valid, relative))
    findings = payload.get("findings")
    if not isinstance(findings, list) or not _nonempty_values(findings):
        errors.append(f"branch semantic artifact requires non-empty findings: {relative}")
    return errors


def branch_proposal_options(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Project validated proposal records into the existing branch interface."""

    proposals = payload.get("proposals")
    if not isinstance(proposals, list):
        return []
    options: list[dict[str, Any]] = []
    for proposal in proposals:
        if not isinstance(proposal, dict):
            continue
        option = dict(proposal)
        option["premise"] = str(proposal.get("causal_premise") or "")
        option["writeback_candidates"] = proposal.get("state_writeback") or {}
        option["scores"] = proposal.get("scores") if isinstance(proposal.get("scores"), dict) else {}
        option["risks"] = proposal.get("risks") if isinstance(proposal.get("risks"), list) else []
        option["status"] = "candidate"
        option["branch_origin"] = "agent-proposal"
        options.append(option)
    return options


def branch_option_ids(options: list[dict[str, Any]]) -> set[str]:
    return {str(item.get("branch_id") or "").strip() for item in options if str(item.get("branch_id") or "").strip()}


def _proposal_errors(proposal: dict[str, Any], index: int, relative: str) -> list[str]:
    label = str(proposal.get("branch_id") or f"proposal {index + 1}")
    errors: list[str] = []
    for field in REQUIRED_PROPOSAL_FIELDS:
        if field not in proposal:
            errors.append(f"branch proposal `{label}` is missing {field}: {relative}")
    branch_id = str(proposal.get("branch_id") or "").strip()
    if not re.fullmatch(r"agent_branch_[a-z0-9][a-z0-9_-]*", branch_id):
        errors.append(f"branch proposal id must use agent_branch_<slug>: {relative}")
    for field in ("title", "strategy", "causal_premise", "cost", "reader_effect"):
        if not str(proposal.get(field) or "").strip():
            errors.append(f"branch proposal `{label}` requires non-empty {field}: {relative}")
    actions = proposal.get("action_chain")
    if not isinstance(actions, list) or len(_nonempty_values(actions)) < 2:
        errors.append(f"branch proposal `{label}` requires at least two concrete actions: {relative}")
    writeback = proposal.get("state_writeback")
    if not isinstance(writeback, dict) or not _has_writeback_change(writeback):
        errors.append(f"branch proposal `{label}` requires a concrete state writeback: {relative}")
    return errors


def _diversity_errors(proposals: list[dict[str, Any]], relative: str) -> list[str]:
    if len(proposals) < 2:
        return []
    dimensions = {
        "distinct causal premises": [_signature(item.get("causal_premise")) for item in proposals],
        "distinct action chains": [_signature(item.get("action_chain")) for item in proposals],
        "distinct costs": [_signature(item.get("cost")) for item in proposals],
        "distinct reader effects": [_signature(item.get("reader_effect")) for item in proposals],
        "distinct state writebacks": [_signature(item.get("state_writeback")) for item in proposals],
    }
    errors: list[str] = []
    for label, signatures in dimensions.items():
        if len(set(signatures)) != len(signatures):
            errors.append(f"branch proposals require {label}, not renamed variants: {relative}")
    ids = [str(item.get("branch_id") or "").strip() for item in proposals]
    if len(set(ids)) != len(ids):
        errors.append(f"branch proposals require unique branch_id values: {relative}")
    return errors


def _has_writeback_change(writeback: dict[str, Any]) -> bool:
    return any(_nonempty_values(value) for value in writeback.values() if isinstance(value, list))


def _nonempty_values(values: list[Any]) -> list[Any]:
    return [value for value in values if str(value).strip()]


def _signature(value: Any) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value or "")
    return re.sub(r"\s+", "", text).casefold()
