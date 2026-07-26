"""Feature settings for behavior-preserving orchestration rollout."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class OrchestrationMode(StrEnum):
    FIXED = "fixed"
    SHADOW = "shadow"
    ASSISTED = "assisted"
    SUPERVISED_ADAPTIVE = "supervised_adaptive"
    FULL_ADAPTIVE = "full_adaptive"


class StrategyPreset(StrEnum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    EXPLORATORY = "exploratory"


@dataclass(frozen=True)
class OrchestrationSettings:
    enabled: bool
    configured_mode: OrchestrationMode
    effective_mode: OrchestrationMode
    strategy_preset: StrategyPreset
    constitution_version: str


def orchestration_settings(config: dict[str, Any]) -> OrchestrationSettings:
    raw = config.get("orchestration")
    payload = raw if isinstance(raw, dict) else {}
    enabled = bool(payload.get("enabled", False))
    try:
        configured_mode = OrchestrationMode(str(payload.get("mode") or OrchestrationMode.FIXED))
    except ValueError as exc:
        raise ValueError("unsupported orchestration mode") from exc
    try:
        preset = StrategyPreset(str(payload.get("strategy_preset") or StrategyPreset.BALANCED))
    except ValueError as exc:
        raise ValueError("unsupported orchestration strategy preset") from exc
    constitution_version = str(payload.get("constitution_version") or "1").strip()
    if constitution_version != "1":
        raise ValueError("unsupported orchestration constitution version")
    return OrchestrationSettings(
        enabled=enabled,
        configured_mode=configured_mode,
        effective_mode=configured_mode if enabled else OrchestrationMode.FIXED,
        strategy_preset=preset,
        constitution_version=constitution_version,
    )
