"""Pure SceneBrief construction from already-resolved literary facts."""

from __future__ import annotations

from collections.abc import Iterable

from ..facts import SceneFacts
from .contracts import (
    LengthTarget,
    RhythmDirective,
    SceneBrief,
    SceneRisk,
    StyleMountRef,
)


def build_scene_brief(
    facts: SceneFacts,
    *,
    risk: SceneRisk,
    scene_function: str = "",
    canon_constraints: Iterable[str] = (),
    incoming_handoff: Iterable[str] = (),
    chapter_obligations: Iterable[str] = (),
    rhythm: RhythmDirective | None = None,
    length: LengthTarget | None = None,
    style_mount: StyleMountRef | None = None,
    source_refs: Iterable[str] = (),
) -> SceneBrief:
    """Build the minimal creative brief without reading project files."""

    resolved_length = length or LengthTarget(
        target_hanzi=facts.word_count_target,
        soft_min=facts.word_count_min,
        soft_max=facts.word_count_max,
    )
    resolved_handoff = tuple(_clean_items(incoming_handoff))
    if not resolved_handoff and facts.incoming_pressure:
        resolved_handoff = (facts.incoming_pressure,)
    return SceneBrief(
        scene_id=facts.scene_id,
        objective=facts.scene_goal,
        scene_function=scene_function.strip(),
        participants=tuple(_clean_items(facts.participants)),
        canon_constraints=tuple(_clean_items(canon_constraints)),
        incoming_handoff=resolved_handoff,
        chapter_obligations=tuple(_clean_items(chapter_obligations)),
        rhythm=rhythm or RhythmDirective(),
        length=resolved_length,
        style_mount=style_mount or StyleMountRef(),
        risk=risk,
        source_refs=tuple(_clean_items(source_refs)),
        viewpoint=facts.viewpoint,
        location=facts.location,
        external_conflict=facts.external_conflict,
        internal_conflict=facts.internal_conflict,
    )


def scene_brief_issues(brief: SceneBrief) -> tuple[str, ...]:
    """Return structural brief errors suitable for deterministic preflight."""

    issues: list[str] = []
    if not brief.scene_id.strip():
        issues.append("scene_id is required")
    if not brief.objective.strip():
        issues.append("objective is required")
    if brief.length.target_hanzi < 0 or brief.length.soft_min < 0 or brief.length.soft_max < 0:
        issues.append("length values must be non-negative")
    if brief.length.soft_max and brief.length.soft_min > brief.length.soft_max:
        issues.append("soft_min must not exceed soft_max")
    return tuple(issues)


def _clean_items(values: Iterable[str]) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]


__all__ = ["build_scene_brief", "scene_brief_issues"]
