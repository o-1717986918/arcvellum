"""Public candidate-asset projections for the Narrative Archive."""

from __future__ import annotations


def project_candidate_list(items: tuple[dict[str, object], ...]) -> dict[str, object]:
    return {
        "schema": "arcvellum/archive-candidate-list/v1",
        "items": list(items),
        "count": len(items),
    }


def project_candidate_detail(candidate: dict[str, object]) -> dict[str, object]:
    return {
        "schema": "arcvellum/archive-candidate-detail-response/v1",
        "candidate": candidate,
    }
