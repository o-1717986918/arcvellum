"""Validate formal scene prompt sources before assembling the prompt pack."""

from __future__ import annotations

from pathlib import Path

from literary_engineering_studio_engine.literary.scene.context.broker import (
    context_trace_status,
    default_context_trace_path,
)
from literary_engineering_studio_engine.tasking.gates import ensure_composition_ready_for_generation


def validated_scene_prompt_inputs(
    project_root: Path,
    scene_path: Path,
    context_path: Path,
    composition: Path | None,
    *,
    allow_unselected_composition: bool,
    allow_missing_composition: bool,
) -> tuple[Path, Path, Path, Path, Path | None, str]:
    root = project_root.resolve()
    scene = _resolve(root, scene_path)
    context = _resolve(root, context_path)
    trace = default_context_trace_path(context)
    if not trace.exists():
        raise FileNotFoundError(
            f"context trace not found: {trace.relative_to(root).as_posix()}. "
            "Run context again so formal generation can audit loaded canon/character/style/word-budget inputs."
        )
    scene_id = scene.stem or "scene"
    status = context_trace_status(root, scene_id, context)
    if not status.passed:
        raise ValueError(
            f"context trace is not fresh: {status.message}. "
            "Rerun the formal context task before compiling a prose prompt pack."
        )
    fallback = root / "drafts" / "compositions" / f"{scene_id}_composition.md"
    selected = _resolve(root, composition) if composition else fallback
    selected = selected if selected.exists() else None
    ensure_composition_ready_for_generation(
        root,
        selected,
        allow_unselected_composition=allow_unselected_composition,
        allow_missing_composition=allow_missing_composition,
    )
    return root, scene, context, trace, selected, scene_id


def _resolve(root: Path, path: Path) -> Path:
    target = path if path.is_absolute() else root / path
    return target.resolve()


__all__ = ["validated_scene_prompt_inputs"]
