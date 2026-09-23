"""Bounded project-local source evidence for lean scene prompts."""

from __future__ import annotations

from pathlib import Path

from literary_engineering_studio_engine.public.literary import SceneBrief
from ..runtime.prompt_recipes import lean_scene_prompt_recipe


def scene_source_evidence(
    project_root: Path,
    brief: SceneBrief,
    *,
    purpose: str,
    indexed_style: bool,
    reserve_chars: int = 0,
) -> str:
    recipe = lean_scene_prompt_recipe(purpose)
    remaining = max(0, recipe.soft_character_limit - 8_000 - reserve_chars)
    blocks: list[str] = []
    for reference in brief.source_refs:
        if indexed_style and Path(reference).name == "style-profile.md":
            continue
        path = (project_root / Path(reference)).resolve()
        if not path.is_relative_to(project_root) or not path.is_file():
            continue
        body = path.read_text(encoding="utf-8", errors="replace").strip()
        if not body:
            continue
        excerpt = body[:remaining]
        blocks.append(f"### {reference}\n{excerpt}")
        remaining -= len(excerpt)
        if remaining <= 0:
            break
    return "\n\n".join(blocks)


__all__ = ["scene_source_evidence"]
