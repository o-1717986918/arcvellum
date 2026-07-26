"""Read-only, bounded layout-hint contract for the narrative projection."""

from __future__ import annotations

from typing import Any


LAYOUT_HINT_SCHEMA = "arcvellum/layout-hints/v1"


def build_layout_hints(grammar: str, level: str, nodes: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe the accepted hint surface without granting layout authority."""
    return {
        "schema": LAYOUT_HINT_SCHEMA,
        "grammar": grammar,
        "level": level,
        "primary_axis": "depth" if grammar in {"spine", "strata", "stage"} else "braid",
        "focus_bias": "lower-right" if grammar == "braid" else "center",
        "node_count": len(nodes),
        "policy": {
            "read_only": True,
            "stable_node_ids_required": True,
            "collision_validation_required": True,
            "primary_offset_limit": 1.2,
            "satellite_offset_limit": 3.2,
        },
        "agent_layout_intent": {
            "status": "disabled",
            "enabled": False,
            "provider": "",
        },
        "node_offsets": [],
    }


__all__ = ["LAYOUT_HINT_SCHEMA", "build_layout_hints"]
