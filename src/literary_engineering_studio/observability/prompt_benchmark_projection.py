"""Content-safe Prompt Program projection for Runtime benchmark reports."""

from __future__ import annotations

from typing import Mapping


def prompt_program_projection(manifest: Mapping[str, object]) -> dict[str, object]:
    materialization = _mapping(manifest.get("prompt_program"))
    formal = _mapping(materialization.get("formal"))
    shadow = _mapping(materialization.get("shadow"))
    return {
        "formal_version": str(formal.get("version") or "unavailable"),
        "formal_metrics": _prompt_metrics(formal),
        "shadow_version": str(shadow.get("version") or "unavailable"),
        "shadow_metrics": _prompt_metrics(shadow),
        "rollout_reason": str(_mapping(materialization.get("rollout")).get("reason") or "unavailable"),
    }


def _prompt_metrics(value: Mapping[str, object]) -> dict[str, object]:
    metrics = _mapping(value.get("metrics"))
    return {
        key: metrics.get(key)
        for key in (
            "total_characters",
            "estimated_input_tokens",
            "duplicate_character_ratio",
            "constraint_repetition_ratio",
            "prompt_sha256",
        )
        if key in metrics
    }


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


__all__ = ["prompt_program_projection"]
