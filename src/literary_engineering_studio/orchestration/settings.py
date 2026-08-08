"""Feature settings for behavior-preserving orchestration rollout."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class OrchestrationMode(str, Enum):
    FIXED = "fixed"
    SHADOW = "shadow"
    ASSISTED = "assisted"
    SUPERVISED_ADAPTIVE = "supervised_adaptive"
    FULL_ADAPTIVE = "full_adaptive"


class StrategyPreset(str, Enum):
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
    production_chapter_horizon: bool = False
    chapter_horizon_size: int = 3
    bundle_execution: bool = False


def orchestration_settings(config: dict[str, Any]) -> OrchestrationSettings:
    raw = config.get("orchestration")
    payload = raw if isinstance(raw, dict) else {}
    enabled = bool(payload.get("enabled", False))
    try:
        configured_mode = OrchestrationMode(
            str(payload.get("mode") or OrchestrationMode.FIXED.value)
        )
    except ValueError as exc:
        raise ValueError("unsupported orchestration mode") from exc
    try:
        preset = StrategyPreset(
            str(payload.get("strategy_preset") or StrategyPreset.BALANCED.value)
        )
    except ValueError as exc:
        raise ValueError("unsupported orchestration strategy preset") from exc
    constitution_version = str(payload.get("constitution_version") or "1").strip()
    if constitution_version != "1":
        raise ValueError("unsupported orchestration constitution version")
    chapter_horizon_size = int(payload.get("chapter_horizon_size") or 3)
    if not 2 <= chapter_horizon_size <= 4:
        raise ValueError("chapter_horizon_size must be between 2 and 4")
    return OrchestrationSettings(
        enabled=enabled,
        configured_mode=configured_mode,
        effective_mode=configured_mode if enabled else OrchestrationMode.FIXED,
        strategy_preset=preset,
        constitution_version=constitution_version,
        production_chapter_horizon=bool(
            payload.get("production_chapter_horizon", False)
        ),
        chapter_horizon_size=chapter_horizon_size,
        bundle_execution=bool(payload.get("bundle_execution", False)),
    )
