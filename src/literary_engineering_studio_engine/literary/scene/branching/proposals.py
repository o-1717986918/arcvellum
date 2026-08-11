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
    "beat_plan",
)

REQUIRED_BEAT_OBLIGATIONS = frozenset(
    {"incoming_bridge", "goal", "turn", "cost", "reader_effect", "outgoing_hook"}
)
REQUIRED_BEAT_FIELDS = (
    "beat_id",
    "function",
    "visible_action",
    "causal_change",
    "pace",
    "detail_level",
    "serves",
)
WRITEBACK_FIELDS = (
    "new_facts",
    "character_changes",
    "relationship_changes",
    "foreshadowing_changes",
    "next_scene_inputs",
)


def branch_proposal_scaffold(slot: int = 1) -> dict[str, Any]:
    """Return the single authoritative Agent-facing proposal shape.

    Placeholder values intentionally fail the quality gate.  The scaffold is
    an editing aid, not a deterministic proposal or a way to bypass creative
    judgment.
    """

    number = max(1, int(slot))
    return {
        "branch_id": f"agent_branch_replace_{number}",
        "title": "<replace: scene-specific title>",
        "strategy": "<replace: causal strategy, not a renamed fallback>",
        "causal_premise": "<replace: choice causes consequence>",
        "action_chain": [
            "<replace: concrete action 1>",
            "<replace: concrete action 2>",
        ],
        "cost": "<replace: irreversible or accumulating cost>",
        "reader_effect": "<replace: reader expectation or emotion change>",
        "state_writeback": {
            "new_facts": [],
            "character_changes": [],
            "relationship_changes": [],
            "foreshadowing_changes": [],
            "next_scene_inputs": ["<replace: concrete next-scene pressure>"],
        },
        "beat_plan": [
            {
                "beat_id": f"branch_{number}_beat_1",
                "function": "<replace: opening beat function>",
                "visible_action": "<replace: observable action>",
                "causal_change": "<replace: state changed by this action>",
                "pace": "measured",
                "detail_level": "standard",
                "serves": ["incoming_bridge", "goal"],
            },
            {
                "beat_id": f"branch_{number}_beat_2",
                "function": "<replace: turn and consequence function>",
                "visible_action": "<replace: observable action>",
                "causal_change": "<replace: state changed by this action>",
                "pace": "accelerating",
                "detail_level": "expanded",
                "serves": ["turn", "cost", "reader_effect", "outgoing_hook"],
            },
        ],
    }


def branch_proposal_contract(proposal_count: int = 0) -> dict[str, Any]:
    """Project the exact mechanical contract without making creative choices."""

    return {
        "proposal_count": max(0, int(proposal_count)),
        "proposal_shape": branch_proposal_scaffold(),
        "proposal_required_fields": list(REQUIRED_PROPOSAL_FIELDS),
        "beat_required_fields": list(REQUIRED_BEAT_FIELDS),
        "beat_obligations": sorted(REQUIRED_BEAT_OBLIGATIONS),
        "state_writeback_fields": list(WRITEBACK_FIELDS),
        "identity_rule": "branch_id must match agent_branch_<slug>",
    }


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
    if branch_id.startswith("agent_branch_replace_"):
        errors.append(f"branch proposal `{label}` still contains scaffold identity: {relative}")
    for field in ("title", "strategy", "causal_premise", "cost", "reader_effect"):
        if not str(proposal.get(field) or "").strip():
            errors.append(f"branch proposal `{label}` requires non-empty {field}: {relative}")
        elif _contains_placeholder(proposal.get(field)):
            errors.append(f"branch proposal `{label}` must replace placeholder {field}: {relative}")
    actions = proposal.get("action_chain")
    if not isinstance(actions, list) or len(_nonempty_values(actions)) < 2:
        errors.append(f"branch proposal `{label}` requires at least two concrete actions: {relative}")
    elif any(_contains_placeholder(item) for item in actions):
        errors.append(f"branch proposal `{label}` must replace action_chain placeholders: {relative}")
    writeback = proposal.get("state_writeback")
    if not isinstance(writeback, dict) or not _has_writeback_change(writeback):
        errors.append(f"branch proposal `{label}` requires a concrete state writeback: {relative}")
    errors.extend(_beat_plan_errors(proposal.get("beat_plan"), label, relative))
    return errors


def _beat_plan_errors(value: Any, label: str, relative: str) -> list[str]:
    if not isinstance(value, list) or not 2 <= len(value) <= 8:
        return [f"branch proposal `{label}` requires a 2-8 item beat_plan: {relative}"]
    errors: list[str] = []
    ids: list[str] = []
    covered: set[str] = set()
    for index, beat in enumerate(value):
        if not isinstance(beat, dict):
            errors.append(f"branch proposal `{label}` beat {index + 1} must be an object: {relative}")
            continue
        for field in REQUIRED_BEAT_FIELDS:
            if field not in beat or not _meaningful_beat_value(beat.get(field)):
                errors.append(f"branch proposal `{label}` beat {index + 1} requires {field}: {relative}")
        ids.append(str(beat.get("beat_id") or "").strip())
        serves = beat.get("serves")
        if isinstance(serves, list):
            covered.update(str(item).strip() for item in serves if str(item).strip())
    if len(ids) != len(set(ids)):
        errors.append(f"branch proposal `{label}` requires unique beat_id values: {relative}")
    missing = sorted(REQUIRED_BEAT_OBLIGATIONS - covered)
    if missing:
        errors.append(f"branch proposal `{label}` beat_plan misses obligations {', '.join(missing)}: {relative}")
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


def _meaningful_beat_value(value: Any) -> bool:
    if isinstance(value, list):
        return bool(_nonempty_values(value)) and not any(_contains_placeholder(item) for item in value)
    return bool(str(value or "").strip()) and not _contains_placeholder(value)


def _contains_placeholder(value: Any) -> bool:
    return "<replace:" in str(value or "").casefold()


def _signature(value: Any) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value or "")
    return re.sub(r"\s+", "", text).casefold()
