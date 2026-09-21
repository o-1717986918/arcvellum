"""Pure projection of committed SceneDelta evidence into longform continuity."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .contracts import ChangeProposal, SceneDelta


CONTINUITY_PROJECTION_SCHEMA = "arcvellum/continuity-projection/v1"


def project_committed_scene_delta(
    *,
    scene_id: str,
    transaction_id: str,
    delta: SceneDelta,
    current_projection: dict[str, Any] | None = None,
    current_facts: dict[str, Any] | None = None,
    current_timeline: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Return deterministic derived facts without confirming model candidates.

    Replaying the same scene replaces its derived rows.  Existing confirmed
    Canon and unrelated timeline events are preserved verbatim.
    """

    projection = _continuity_projection(
        scene_id, transaction_id, delta, current_projection or {},
    )
    facts = _facts_projection(scene_id, transaction_id, delta, current_facts or {})
    timeline = _timeline_projection(scene_id, delta, current_timeline or {})
    return projection, facts, timeline


def _continuity_projection(
    scene_id: str,
    transaction_id: str,
    delta: SceneDelta,
    current: dict[str, Any],
) -> dict[str, Any]:
    projection = dict(current)
    entries = [
        item for item in _dict_rows(projection.get("entries"))
        if str(item.get("scene_id") or "") != scene_id
    ]
    for group, proposals in _proposal_groups(delta):
        entries.extend(_entry(scene_id, transaction_id, group, item) for item in proposals)
    projection.update(
        {
            "schema": CONTINUITY_PROJECTION_SCHEMA,
            "entries": entries,
            "scene_count": len({str(item.get("scene_id") or "") for item in entries}),
            "open_identity_candidates": _identity_candidates(entries),
            "identity_conflicts": _identity_conflicts(entries),
        }
    )
    return projection


def _facts_projection(
    scene_id: str,
    transaction_id: str,
    delta: SceneDelta,
    current: dict[str, Any],
) -> dict[str, Any]:
    facts = dict(current)
    facts["facts"] = list(facts.get("facts")) if isinstance(facts.get("facts"), list) else []
    facts["conflicts"] = list(facts.get("conflicts")) if isinstance(facts.get("conflicts"), list) else []
    candidates = [
        item for item in _dict_rows(facts.get("candidates"))
        if str(item.get("source_scene") or "") != scene_id
    ]
    for group, proposals in (
        ("canon_candidate", delta.canon_candidates),
        ("continuity_candidate", delta.continuity_changes),
    ):
        candidates.extend(_canon_candidate(scene_id, transaction_id, group, item) for item in proposals)
    facts["candidates"] = candidates
    return facts


def _timeline_projection(
    scene_id: str,
    delta: SceneDelta,
    current: dict[str, Any],
) -> dict[str, Any]:
    timeline = dict(current)
    events = [
        item for item in _dict_rows(timeline.get("events"))
        if str(item.get("scene_id") or "") != scene_id
    ]
    summaries = [item.summary for item in delta.proposals() if item.summary.strip()]
    if summaries or delta.next_handoff:
        events.append(
            {
                "id": f"commit-{scene_id}",
                "scene_id": scene_id,
                "status": "committed",
                "changes": summaries,
                "next_handoff": list(delta.next_handoff),
                "source": f"workflow/scene_deltas/{scene_id}.json",
            }
        )
    timeline["events"] = events
    return timeline


def _proposal_groups(delta: SceneDelta):
    return (
        ("character_change", delta.character_changes),
        ("canon_candidate", delta.canon_candidates),
        ("continuity_change", delta.continuity_changes),
        ("promise_update", delta.promise_updates),
        ("reader_question_update", delta.reader_question_updates),
        ("new_asset_candidate", delta.new_asset_candidates),
    )


def _entry(
    scene_id: str,
    transaction_id: str,
    group: str,
    proposal: ChangeProposal,
) -> dict[str, Any]:
    return {
        "entry_id": _stable_id(scene_id, group, proposal),
        "scene_id": scene_id,
        "transaction_id": transaction_id,
        "kind": group,
        "target_ref": proposal.target_ref,
        "summary": proposal.summary,
        "evidence": proposal.evidence,
        "operation": proposal.operation,
        "attributes": dict(proposal.attributes),
        "source": f"workflow/scene_deltas/{scene_id}.json",
    }


def _canon_candidate(
    scene_id: str,
    transaction_id: str,
    kind: str,
    proposal: ChangeProposal,
) -> dict[str, Any]:
    return {
        "candidate_id": _stable_id(scene_id, kind, proposal),
        "status": "pending_confirmation",
        "kind": kind,
        "target_ref": proposal.target_ref,
        "statement": proposal.summary,
        "evidence": proposal.evidence,
        "source_scene": scene_id,
        "source_transaction": transaction_id,
        "source": f"workflow/scene_deltas/{scene_id}.json",
    }


def _identity_candidates(entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "target_ref": str(item.get("target_ref") or ""),
            "summary": str(item.get("summary") or ""),
            "scene_id": str(item.get("scene_id") or ""),
            "status": "pending_registration",
        }
        for item in entries
        if item.get("kind") == "new_asset_candidate"
    ]


def _identity_conflicts(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expose reused identity refs with incompatible descriptions for review.

    This is evidence, not a gate: the next scene and the top-level Agent can see
    that one apparent identity was introduced with more than one meaning.
    """

    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in entries:
        if item.get("kind") != "new_asset_candidate":
            continue
        target_ref = str(item.get("target_ref") or "").strip()
        if target_ref:
            grouped.setdefault(target_ref.casefold(), []).append(item)
    conflicts: list[dict[str, Any]] = []
    for rows in grouped.values():
        summaries = {str(item.get("summary") or "").strip() for item in rows}
        scenes = {str(item.get("scene_id") or "").strip() for item in rows}
        if len(summaries - {""}) < 2 or len(scenes - {""}) < 2:
            continue
        conflicts.append(
            {
                "target_ref": str(rows[0].get("target_ref") or ""),
                "scene_ids": sorted(scenes - {""}),
                "summaries": sorted(summaries - {""}),
                "status": "needs_identity_resolution",
            }
        )
    return conflicts


def _stable_id(scene_id: str, group: str, proposal: ChangeProposal) -> str:
    payload = json.dumps(
        [scene_id, group, proposal.target_ref, proposal.summary, proposal.evidence],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _dict_rows(value: object) -> list[dict[str, Any]]:
    return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []


__all__ = ["CONTINUITY_PROJECTION_SCHEMA", "project_committed_scene_delta"]
