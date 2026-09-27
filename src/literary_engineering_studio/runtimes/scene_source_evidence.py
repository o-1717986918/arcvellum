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
    remaining = _source_budget(purpose, recipe.soft_character_limit, reserve_chars)
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
        body = _source_excerpt(reference, body, brief.scene_id)
        header = _source_header(reference)
        separator = 2 if blocks else 0
        if remaining <= len(header) + separator:
            break
        excerpt = body[:remaining - len(header) - separator]
        blocks.append(f"{header}{excerpt}")
        remaining -= len(header) + len(excerpt) + separator
        if remaining <= 0:
            break
    return "\n\n".join(blocks)


def _source_budget(purpose: str, soft_limit: int, reserve_chars: int) -> int:
    return min(9_000 if purpose == "create" else 7_000, max(0, soft_limit - 8_000 - reserve_chars))


def _source_excerpt(reference: str, body: str, scene_id: str) -> str:
    """Share source attention across the current brief, previous ending and latest direction."""

    if reference == f"scenes/{scene_id}.yaml":
        limit = 900  # Most of this plan is already present in SceneBrief.
    elif reference.startswith("drafts/scenes/"):
        limit = 1_800  # The previous scene's ending is the important handoff.
    elif reference.startswith("workflow/scene_deltas/"):
        limit = 1_800  # Preserve the reader questions, promises and handoff.
    elif reference == "workflow/continuity/current.json":
        limit = 1_500
    elif reference.endswith("user_directions.md"):
        limit = 1_500  # Later entries supersede earlier direction.
    elif reference.startswith("characters/"):
        limit = 850
    else:
        limit = 1_000
    if len(body) <= limit:
        return body
    if reference.startswith("drafts/scenes/"):
        return body[:300] + "\n[…中段已省略…]\n" + body[-(limit - 320):]
    if reference == "workflow/continuity/current.json" or reference.startswith("workflow/scene_deltas/"):
        return _structured_scene_excerpt(reference, body, limit)
    if reference.endswith("user_directions.md"):
        return body[-limit:]
    return body[:limit]


def _structured_scene_excerpt(reference: str, body: str, limit: int) -> str:
    try:
        data = json.loads(body)
    except ValueError:
        return body[-limit:]
    if not isinstance(data, dict):
        return body[-limit:]
    if reference == "workflow/continuity/current.json":
        entries = data.get("entries")
        compact = ({"schema": data.get("schema"), "recent_entries": entries[-8:]}
                   if isinstance(entries, list) else {"schema": data.get("schema")})
    else:
        compact = {key: data.get(key) for key in (
            "scene_id", "next_handoff", "reader_question_updates", "promise_updates",
            "character_changes", "continuity_changes", "canon_candidates",
        ) if data.get(key)}
    return _bounded_json_excerpt(compact, limit)


def _source_header(reference: str) -> str:
    if reference.startswith("drafts/scenes/"):
        status = "已提交正文，可作为已发生的叙述"
    elif reference.startswith("workflow/scene_deltas/"):
        status = "已提交场景交接；其中提议与 canon_candidates 仍是待确认候选"
    elif reference == "workflow/continuity/current.json":
        status = "连续性投射；按条目来源与状态判断，不等于 Canon 确认"
    else:
        status = "来源摘录"
    return f"### {reference} · {status}\n"


def _bounded_json_excerpt(payload: dict[str, object], limit: int) -> str:
    compact = json.loads(json.dumps(payload, ensure_ascii=False))
    encode = lambda: json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
    while len(encode()) > limit:
        lists = [value for value in compact.values() if isinstance(value, list) and len(value) > 1]
        if not lists:
            break
        max(lists, key=len).pop(0)
    if len(encode()) > limit:
        for key, value in list(compact.items()):
            if isinstance(value, list):
                compact[key] = [_short_json_value(item) for item in value]
    while len(encode()) > limit:
        removable = next((key for key in reversed(compact) if key not in {"scene_id", "schema"}), None)
        if removable is None:
            break
        compact.pop(removable)
    return encode()[:limit]


def _short_json_value(value: object) -> object:
    if isinstance(value, str):
        return value[:160]
    if isinstance(value, dict):
        return {key: _short_json_value(item) for key, item in value.items()
                if key in {"kind", "target_ref", "summary", "status", "operation", "source", "evidence"}}
    return value


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
        "premise": str(plan.get("premise") or "")[:180],
        "central_question": str(plan.get("central_question") or "")[:150],
        "ending_choice": str(plan.get("ending_choice") or "")[:200],
        "narrative_design": {key: str(value)[:120] for key, value in design.items()},
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
