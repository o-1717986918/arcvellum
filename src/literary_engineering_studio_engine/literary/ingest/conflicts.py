"""Conflict discovery that preserves alternatives instead of choosing winners."""

from __future__ import annotations

import json
from typing import Any

from .aliases import normalize_alias
from .timeline import temporal_cycle_conflicts


def discover_extraction_conflicts(
    *,
    entity_occurrences: list[dict[str, Any]],
    claim_occurrences: list[dict[str, Any]],
    event_occurrences: list[dict[str, Any]],
    relation_occurrences: list[dict[str, Any]],
    alias_groups: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    conflicts = [
        _alias_conflict(group)
        for group in alias_groups
        if group.get("requires_agent_resolution") is True
    ]
    conflicts.extend(
        _claim_conflicts(
            claim_occurrences,
            entity_occurrences=entity_occurrences,
        )
    )
    conflicts.extend(temporal_cycle_conflicts(event_occurrences))
    conflicts.extend(
        _declared_contradictions(
            entity_occurrences,
            event_occurrences,
            relation_occurrences,
            claim_occurrences,
        )
    )
    return sorted(
        conflicts,
        key=lambda item: (
            str(item.get("conflict_type") or ""),
            json.dumps(item.get("candidate_refs") or [], ensure_ascii=False),
        ),
    )


def _alias_conflict(group: dict[str, Any]) -> dict[str, Any]:
    return {
        "conflict_type": "alias_identity_ambiguity",
        "severity": "requires_resolution",
        "candidate_refs": list(group.get("candidate_refs") or []),
        "evidence_refs": list(group.get("evidence_refs") or []),
        "alternatives": [
            {
                "kind": "same_entity",
                "description": "Treat the observations as aliases of one entity.",
            },
            {
                "kind": "different_entities",
                "description": "Keep the observations as distinct entities sharing a name.",
            },
            {
                "kind": "partially_resolved",
                "description": "Merge only the evidence-supported subset.",
            },
        ],
        "resolution": "unresolved",
    }


def _claim_conflicts(
    claims: list[dict[str, Any]],
    *,
    entity_occurrences: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entity_names = {
        str(item.get("candidate_ref") or ""): normalize_alias(item.get("name"))
        for item in entity_occurrences
    }
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for claim in claims:
        subject_ref = str(claim.get("subject_ref") or "")
        key = (
            str(claim.get("domain") or "").strip().casefold(),
            entity_names.get(subject_ref, normalize_alias(subject_ref)),
            str(claim.get("predicate") or "").strip().casefold(),
        )
        grouped.setdefault(key, []).append(claim)

    conflicts: list[dict[str, Any]] = []
    for key, values in sorted(grouped.items()):
        alternatives: dict[str, dict[str, Any]] = {}
        for claim in values:
            encoded = json.dumps(
                claim.get("value"),
                ensure_ascii=False,
                sort_keys=True,
            )
            alternative = alternatives.setdefault(
                encoded,
                {
                    "value": claim.get("value"),
                    "candidate_refs": [],
                    "evidence_refs": [],
                },
            )
            _extend_unique(
                alternative["candidate_refs"],
                [str(claim.get("candidate_ref") or "")],
            )
            _extend_unique(
                alternative["evidence_refs"],
                [str(item) for item in claim.get("evidence_refs") or []],
            )
        if len(alternatives) < 2:
            continue
        candidate_refs: list[str] = []
        evidence_refs: list[str] = []
        for alternative in alternatives.values():
            _extend_unique(candidate_refs, alternative["candidate_refs"])
            _extend_unique(evidence_refs, alternative["evidence_refs"])
        conflicts.append(
            {
                "conflict_type": "claim_value_conflict",
                "severity": "requires_resolution",
                "claim_key": {
                    "domain": key[0],
                    "subject": key[1],
                    "predicate": key[2],
                },
                "candidate_refs": candidate_refs,
                "evidence_refs": evidence_refs,
                "alternatives": list(alternatives.values()),
                "resolution": "unresolved",
            }
        )
    return conflicts


def _declared_contradictions(
    *collections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    for collection in collections:
        for occurrence in collection:
            notes = [
                str(item).strip()
                for item in occurrence.get("contradiction_notes") or []
                if str(item).strip()
            ]
            if not notes:
                continue
            conflicts.append(
                {
                    "conflict_type": "agent_declared_contradiction",
                    "severity": "requires_resolution",
                    "candidate_refs": [str(occurrence.get("candidate_ref") or "")],
                    "evidence_refs": [
                        str(item) for item in occurrence.get("evidence_refs") or []
                    ],
                    "alternatives": [
                        {"kind": "reported_interpretation", "description": note}
                        for note in notes
                    ],
                    "resolution": "unresolved",
                }
            )
    return conflicts


def _extend_unique(target: list[str], values: list[str]) -> None:
    for value in values:
        if value and value not in target:
            target.append(value)
