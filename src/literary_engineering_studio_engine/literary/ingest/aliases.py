"""Deterministic alias observations without automatic identity merging."""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def normalize_alias(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"\s+", "", text).strip("，。！？；：、“”‘’（）()[]【】")


def build_alias_groups(
    entity_occurrences: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Group lexical observations while preserving every identity alternative."""

    grouped: dict[str, dict[str, Any]] = {}
    for occurrence in entity_occurrences:
        candidate_ref = str(occurrence.get("candidate_ref") or "")
        names = [
            occurrence.get("name"),
            *(occurrence.get("aliases") or []),
        ]
        for raw_name in names:
            display = str(raw_name or "").strip()
            normalized = normalize_alias(display)
            if not normalized:
                continue
            group = grouped.setdefault(
                normalized,
                {
                    "normalized_alias": normalized,
                    "observed_forms": [],
                    "candidate_refs": [],
                    "evidence_refs": [],
                },
            )
            _append_unique(group["observed_forms"], display)
            _append_unique(group["candidate_refs"], candidate_ref)
            for evidence_ref in occurrence.get("evidence_refs") or []:
                _append_unique(group["evidence_refs"], str(evidence_ref))

    result: list[dict[str, Any]] = []
    for normalized, group in sorted(grouped.items()):
        candidate_refs = group["candidate_refs"]
        result.append(
            {
                **group,
                "resolution": "unresolved" if len(candidate_refs) > 1 else "single_observation",
                "requires_agent_resolution": len(candidate_refs) > 1,
                "merge_applied": False,
                "reason": (
                    "The same lexical alias appears on multiple provisional entities; "
                    "identity must be resolved from evidence."
                    if len(candidate_refs) > 1
                    else "Only one provisional entity uses this lexical alias."
                ),
            }
        )
    return result


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)
