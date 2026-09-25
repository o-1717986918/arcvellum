"""Bounded project-local source evidence for lean scene prompts."""

from __future__ import annotations

import json
from pathlib import Path

from literary_engineering_studio_engine.public.literary import SceneBrief
from ..application.style.owner_directive import read_owner_style_directive
from ..runtime.prompt_recipes import lean_scene_prompt_recipe


def scene_source_evidence(
    project_root: Path,
    brief: SceneBrief,
    *,
    purpose: str,
    indexed_style: bool,
    reserve_chars: int = 0,
    max_chars: int | None = None,
) -> str:
    recipe = lean_scene_prompt_recipe(purpose)
    remaining = max(0, recipe.soft_character_limit - 8_000 - reserve_chars)
    if max_chars is not None:
        remaining = min(remaining, max(0, max_chars))
    north_star = _author_north_star(project_root, brief.scene_id)
    if len(north_star) > remaining:
        north_star = ""
    blocks: list[str] = [north_star] if north_star else []
    remaining = max(0, remaining - len(north_star))
    directive = _owner_style_block(project_root, remaining)
    if directive:
        blocks.append(directive)
        remaining -= len(directive) + 2
    for reference in brief.source_refs:
        if indexed_style and Path(reference).name == "style-profile.md":
            continue
        if reference in {"plot/rhythm_plan.json", "plot/word_budget/word_budget.json"}:
            continue  # SceneBrief already carries this scene's rhythm and length.
        path = (project_root / Path(reference)).resolve()
        if not path.is_relative_to(project_root) or not path.is_file():
            continue
        body = path.read_text(encoding="utf-8", errors="replace").strip()
        if not body:
            continue
        header = f"### {reference}\n"
        separator = 2 if blocks else 0
        if remaining <= len(header) + separator:
            break
        excerpt = body[:remaining - len(header) - separator]
        blocks.append(f"{header}{excerpt}")
        remaining -= len(header) + len(excerpt) + separator
        if remaining <= 0:
            break
    return "\n\n".join(blocks)


def _owner_style_block(project_root: Path, remaining: int) -> str:
    owner_style = read_owner_style_directive(project_root)
    if not owner_style["active"]:
        return ""
    directive = "### 作者自写文风指令（当前作品，优先落实于表达）\n" + str(owner_style["content"])
    return directive if len(directive) + 2 <= remaining else ""


def _author_north_star(project_root: Path, scene_id: str) -> str:
    path = project_root / "plot" / "lean_project_plan.json"
    if not path.is_file():
        return ""
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    if not isinstance(plan, dict):
        return ""
    payload = _north_star_payload(plan, scene_id)
    if not any(payload[key] for key in ("premise", "central_question", "ending_choice")):
        return ""
    return "### plot/lean_project_plan.json · 全篇创作意图（只读摘录）\n" + json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"))


def _north_star_payload(plan: dict[str, object], scene_id: str) -> dict[str, object]:
    scenes = _rows(plan, "scenes")
    chapters = _rows(plan, "chapters")
    scene = _find_row(scenes, "scene_id", scene_id)
    chapter_id = scene.get("chapter_id")
    chapter = _find_row(chapters, "chapter_id", chapter_id)
    design = plan.get("narrative_design")
    design = design if isinstance(design, dict) else {}
    return {
        "premise": str(plan.get("premise") or "")[:250],
        "central_question": str(plan.get("central_question") or "")[:150],
        "ending_choice": str(plan.get("ending_choice") or "")[:250],
        "narrative_design": {key: str(value)[:180] for key, value in design.items()},
        "scene_story_time": str(scene.get("story_time") or "")[:160],
        "current_chapter": {key: str(chapter.get(key) or "")[:150]
                            for key in ("chapter_id", "title", "dramatic_turn", "obligation", "reader_question")},
        "chapter_spine": _chapter_spine(chapters, chapter_id),
    }


def _rows(plan: dict[str, object], key: str) -> list[object]:
    value = plan.get(key)
    return value if isinstance(value, list) else []


def _find_row(rows: list[object], key: str, value: object) -> dict[str, object]:
    return next((row for row in rows if isinstance(row, dict) and row.get(key) == value), {})


def _chapter_spine(chapters: list[object], chapter_id: object) -> list[dict[str, object]]:
    spine = [
        {"chapter_id": row.get("chapter_id"), "dramatic_turn": str(row.get("dramatic_turn") or "")[:100]}
        for row in chapters if isinstance(row, dict)
    ]
    if len(spine) > 5:
        position = next((index for index, row in enumerate(spine) if row["chapter_id"] == chapter_id), 0)
        selected = (0, position - 1, position, position + 1, len(spine) - 1)
        spine = [spine[index] for index in sorted(set(selected)) if 0 <= index < len(spine)]
    return spine


__all__ = ["scene_source_evidence"]
