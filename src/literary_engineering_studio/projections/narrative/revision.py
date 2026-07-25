"""Revision assembly for the v3 narrative read model."""

from __future__ import annotations

from typing import Any, Callable


def build_source_revisions(
    base: dict[str, Any],
    dashboard_payload: object,
    library_payload: object,
    reader_payload: dict[str, Any],
    rhythm_hints: object,
    digest: Callable[[Any], str],
) -> dict[str, str]:
    dashboard = dashboard_payload if isinstance(dashboard_payload, dict) else {}
    return {
        "narrative_v2": str(base.get("revision") or ""),
        "dashboard": digest(dashboard),
        "library": digest(library_payload if isinstance(library_payload, dict) else {}),
        "reader": digest(
            {
                "revision": reader_payload.get("revision"),
                "units": reader_payload.get("units"),
                "total_chinese_content_chars": reader_payload.get("total_chinese_content_chars"),
            }
        ),
        "jobs": digest(
            {
                "current_task": dashboard.get("current_task"),
                "next_actions": dashboard.get("next_actions"),
                "active_run": dashboard.get("active_run"),
            }
        ),
        "rhythm": digest(rhythm_hints),
    }


def build_projection_revision(
    *,
    base_revision: object,
    grammar: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
    focus_scope: dict[str, object],
    relation_profiles: list[dict[str, Any]],
    character_references: list[dict[str, object]],
    source_revisions: dict[str, str],
    digest: Callable[[Any], str],
) -> str:
    return digest(
        {
            "base": base_revision,
            "grammar": grammar,
            "nodes": nodes,
            "edges": edges,
            "clusters": clusters,
            "focus_scope": focus_scope,
            "relation_profiles": relation_profiles,
            "character_references": character_references,
            "source_revisions": source_revisions,
        }
    )
