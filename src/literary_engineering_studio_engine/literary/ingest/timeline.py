"""Temporal extraction validation and deterministic cycle detection."""

from __future__ import annotations

from typing import Any


TEMPORAL_KINDS = {
    "before",
    "after",
    "same_time",
    "within",
    "absolute",
    "relative",
    "unknown",
}


def validate_event_candidates(
    events: Any,
    *,
    candidate_ids: set[str],
    expected_evidence_refs: set[str],
) -> list[str]:
    if not isinstance(events, list):
        return []
    errors: list[str] = []
    event_ids = {
        str(item.get("candidate_id") or "").strip()
        for item in events
        if isinstance(item, dict)
    }
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        errors.extend(
            _event_errors(
                event,
                index=index,
                entity_ids=candidate_ids,
                event_ids=event_ids,
                expected_evidence_refs=expected_evidence_refs,
            )
        )
    return errors


def _event_errors(
    event: dict[str, Any],
    *,
    index: int,
    entity_ids: set[str],
    event_ids: set[str],
    expected_evidence_refs: set[str],
) -> list[str]:
    errors: list[str] = []
    if not str(event.get("summary") or "").strip():
        errors.append(f"events[{index}].summary is required")
    participants = event.get("participant_refs")
    if not isinstance(participants, list):
        errors.append(f"events[{index}].participant_refs must be a list")
    else:
        unknown = sorted(str(item) for item in participants if str(item) not in entity_ids)
        if unknown:
            errors.append(
                f"events[{index}].participant_refs references unknown entities: "
                + ", ".join(unknown)
            )
    constraints = event.get("temporal_constraints")
    if not isinstance(constraints, list):
        return [*errors, f"events[{index}].temporal_constraints must be a list"]
    for constraint_index, constraint in enumerate(constraints):
        prefix = f"events[{index}].temporal_constraints[{constraint_index}]"
        errors.extend(
            _temporal_constraint_errors(
                constraint,
                prefix=prefix,
                event_ids=event_ids,
                expected_evidence_refs=expected_evidence_refs,
            )
        )
    return errors


def _temporal_constraint_errors(
    constraint: Any,
    *,
    prefix: str,
    event_ids: set[str],
    expected_evidence_refs: set[str],
) -> list[str]:
    if not isinstance(constraint, dict):
        return [f"{prefix} must be an object"]
    errors: list[str] = []
    kind = str(constraint.get("kind") or "").strip().lower()
    if kind not in TEMPORAL_KINDS:
        errors.append(
            f"{prefix}.kind must be one of {', '.join(sorted(TEMPORAL_KINDS))}"
        )
    errors.extend(
        _temporal_target_errors(
            constraint,
            kind=kind,
            prefix=prefix,
            event_ids=event_ids,
        )
    )
    if kind in {"within", "absolute", "relative"} and not str(
        constraint.get("value") or ""
    ).strip():
        errors.append(f"{prefix}.value is required for {kind}")
    errors.extend(
        _temporal_evidence_errors(
            constraint,
            prefix=prefix,
            expected_evidence_refs=expected_evidence_refs,
        )
    )
    return errors


def _temporal_target_errors(
    constraint: dict[str, Any],
    *,
    kind: str,
    prefix: str,
    event_ids: set[str],
) -> list[str]:
    if kind not in {"before", "after", "same_time"}:
        return []
    target = str(constraint.get("target_event_id") or "").strip()
    if not target:
        return [f"{prefix}.target_event_id is required for {kind}"]
    if target not in event_ids:
        return [f"{prefix} references unknown event: {target}"]
    return []


def _temporal_evidence_errors(
    constraint: dict[str, Any],
    *,
    prefix: str,
    expected_evidence_refs: set[str],
) -> list[str]:
    refs = constraint.get("evidence_refs")
    if not isinstance(refs, list) or not refs:
        return [f"{prefix}.evidence_refs must be a non-empty list"]
    unknown_refs = sorted(set(str(item) for item in refs) - expected_evidence_refs)
    if unknown_refs:
        return [
            f"{prefix}.evidence_refs contains evidence outside the source chunk: "
            + ", ".join(unknown_refs)
        ]
    return []


def temporal_cycle_conflicts(
    event_occurrences: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return explicit alternatives for impossible before/after cycles."""

    edges, edge_evidence = _temporal_graph(event_occurrences)
    return [
        _cycle_conflict(component, edges=edges, edge_evidence=edge_evidence)
        for component in _strongly_connected_components(edges)
        if len(component) >= 2
    ]


def _temporal_graph(
    event_occurrences: list[dict[str, Any]],
) -> tuple[dict[str, set[str]], dict[tuple[str, str], list[str]]]:
    edges: dict[str, set[str]] = {}
    edge_evidence: dict[tuple[str, str], list[str]] = {}
    for event in event_occurrences:
        source = str(event.get("candidate_ref") or "")
        local_namespace = source.rsplit("::", 1)[0]
        for constraint in event.get("temporal_constraints") or []:
            if not isinstance(constraint, dict):
                continue
            kind = str(constraint.get("kind") or "").lower()
            target_id = str(constraint.get("target_event_id") or "")
            if kind not in {"before", "after"} or not target_id:
                continue
            target = f"{local_namespace}::{target_id}"
            left, right = (source, target) if kind == "before" else (target, source)
            edges.setdefault(left, set()).add(right)
            edge_evidence[(left, right)] = [
                str(item) for item in constraint.get("evidence_refs") or []
            ]
    return edges, edge_evidence


def _cycle_conflict(
    component: set[str],
    *,
    edges: dict[str, set[str]],
    edge_evidence: dict[tuple[str, str], list[str]],
) -> dict[str, Any]:
    evidence_refs: list[str] = []
    for left in component:
        for right in edges.get(left, set()) & component:
            for evidence_ref in edge_evidence.get((left, right), []):
                if evidence_ref not in evidence_refs:
                    evidence_refs.append(evidence_ref)
    return {
        "conflict_type": "temporal_cycle",
        "severity": "blocking",
        "candidate_refs": sorted(component),
        "evidence_refs": evidence_refs,
        "alternatives": [
            {
                "kind": "constraint_revision",
                "description": (
                    "At least one before/after constraint in this cycle must be "
                    "reinterpreted, weakened, or rejected after evidence review."
                ),
            }
        ],
        "resolution": "unresolved",
    }


def _strongly_connected_components(edges: dict[str, set[str]]) -> list[set[str]]:
    index = 0
    stack: list[str] = []
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    on_stack: set[str] = set()
    components: list[set[str]] = []
    nodes = set(edges)
    for targets in edges.values():
        nodes.update(targets)

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for target in sorted(edges.get(node, set())):
            if target not in indices:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[target])
        if lowlinks[node] != indices[node]:
            return
        component: set[str] = set()
        while stack:
            member = stack.pop()
            on_stack.remove(member)
            component.add(member)
            if member == node:
                break
        components.append(component)

    for node in sorted(nodes):
        if node not in indices:
            visit(node)
    return components
