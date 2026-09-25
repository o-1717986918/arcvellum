"""Small creative planning contract for the rolling lean literary route."""

from __future__ import annotations

from copy import deepcopy
import math
from typing import Any


PLAN_SCHEMA = "arcvellum/lean-project-plan/v1"
RHYTHM_ROLES = (
    "setup", "escalation", "climax", "payoff", "aftermath", "bridge", "transition",
)
_SCENE_FIELDS = (
    "name", "function", "conflict", "information_release", "consequence",
    "setup_payoff_role", "obligation",
)
_NARRATIVE_FIELDS = (
    "narrative_mode", "temporal_structure", "viewpoint_design",
    "pacing_design", "structural_signature",
)


def rebalance_lean_budget(budget: dict[str, Any], answer: dict[str, Any]) -> dict[str, Any]:
    """Apply the creator's relative length choices while preserving book totals and IDs."""
    revised = deepcopy(budget)
    volumes = revised.get("volume_budgets") or []
    chapters = revised.get("chapter_budgets") or []
    proposed_chapters = answer.get("chapters")
    if not isinstance(proposed_chapters, list) or len(proposed_chapters) != len(chapters):
        return revised
    proposed_volumes = answer.get("volume_length_weights")
    _rebalance_volumes(revised, volumes, proposed_volumes)
    _rebalance_chapters(chapters, volumes, proposed_chapters, proposed_volumes)
    _sync_chapter_binding(revised, chapters)
    return revised


def _rebalance_chapters(
    chapters: list[dict[str, Any]], volumes: list[dict[str, Any]],
    proposed_chapters: list[object], proposed_volumes: Any,
) -> None:
    for volume in volumes:
        members = [row for row in chapters if row["volume_id"] == volume["volume_id"]]
        proposed = [proposed_chapters[index] for index, row in enumerate(chapters) if row["volume_id"] == volume["volume_id"]]
        if not any(isinstance(item, dict) and "length_weight" in item for item in proposed) and not isinstance(proposed_volumes, list):
            continue
        weights = [item.get("length_weight", 1) if isinstance(item, dict) else 1 for item in proposed]
        targets = _weighted_targets(int(volume["target_words"]), weights)
        for row, target in zip(members, targets):
            row["target_words"] = target
            row["avg_scene_words"] = round(target / int(row["scene_count"]))


def _rebalance_volumes(revised: dict[str, Any], volumes: list[dict[str, Any]], proposed: Any) -> None:
    if not isinstance(proposed, list) or len(proposed) != len(volumes):
        return
    totals = _weighted_targets(int(revised["totals"]["target_words"]), proposed)
    for volume, target in zip(volumes, totals):
        volume["target_words"] = target
        volume["avg_chapter_words"] = round(target / int(volume["chapter_count"]))
        volume["avg_scene_words"] = round(target / int(volume["scene_count"]))


def _sync_chapter_binding(revised: dict[str, Any], chapters: list[dict[str, Any]]) -> None:
    binding = revised.get("scene_inventory_binding")
    if not isinstance(binding, dict):
        return
    by_id = {str(row["chapter_id"]): row for row in chapters}
    for row in binding.get("chapter_rows") or []:
        if not isinstance(row, dict) or str(row.get("chapter_id")) not in by_id:
            continue
        chapter = by_id[str(row["chapter_id"])]
        row["target_words"] = chapter["target_words"]
        row["avg_scene_words"] = chapter["avg_scene_words"]
        row["word_shortfall"] = max(int(chapter["target_words"]) - int(row.get("actual_draft_chinese_chars") or 0), 0)
    binding["word_shortfall"] = sum(int(row.get("word_shortfall") or 0) for row in binding.get("chapter_rows") or [])


def _weighted_targets(total: int, raw_weights: list[object]) -> list[int]:
    if not raw_weights:
        return []
    weights = []
    for value in raw_weights:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 1.0
        weights.append(number if math.isfinite(number) and number > 0 else 1.0)
    exact = [total * weight / sum(weights) for weight in weights]
    targets = [int(value) for value in exact]
    for index in sorted(range(len(weights)), key=lambda i: exact[i] - int(exact[i]), reverse=True)[:total - sum(targets)]:
        targets[index] += 1
    for index, value in enumerate(targets):
        if value < 1:
            donor = max(range(len(targets)), key=lambda i: targets[i])
            if targets[donor] <= 1:
                raise ValueError("length target cannot cover every planned unit")
            targets[donor] -= 1
            targets[index] = 1
    return targets


def normalize_initial_plan(
    answer: dict[str, Any], budget: dict[str, Any], *, project_digest: str
) -> dict[str, Any]:
    """Bind a creative chapter spine and first window to machine-owned IDs."""
    rows = budget.get("chapter_budgets")
    rows = rows if isinstance(rows, list) else []
    chapters = answer.get("chapters")
    if not rows or not isinstance(chapters, list) or len(chapters) != len(rows):
        raise ValueError(f"planning requires exactly {len(rows)} chapter turns")
    volumes = budget.get("volume_budgets")
    volumes = volumes if isinstance(volumes, list) else []
    obligations = answer.get("volume_obligations")
    if not isinstance(obligations, list) or len(obligations) != len(volumes):
        raise ValueError(f"planning requires exactly {len(volumes)} volume obligations")
    clean_volumes = [_text(item, "volume obligation") for item in obligations]
    clean_chapters = _chapters(rows, chapters)
    first_window = normalize_scene_window(
        answer.get("first_window"), rows[0], start_index=1
    )
    clean_characters = _characters(answer.get("characters"))
    world_facts = answer.get("world_facts")
    if world_facts is not None and not isinstance(world_facts, list):
        raise ValueError("planning world facts must be a list")
    return {
        "schema": PLAN_SCHEMA,
        "project_digest": project_digest,
        "premise": _text(answer.get("premise"), "premise"),
        "central_question": _text(answer.get("central_question"), "central question"),
        "ending_choice": _text(answer.get("ending_choice"), "ending choice"),
        "narrative_design": _narrative_design(answer.get("narrative_design")),
        "volume_obligations": clean_volumes,
        "chapters": clean_chapters,
        "event_budget": _event_budget(clean_chapters, first_window),
        "scenes": first_window,
        "characters": clean_characters,
        "world_facts": [_text(item, "world fact") for item in world_facts or []],
    }


def _event_budget(
    chapters: list[dict[str, str]], scenes: list[dict[str, Any]],
) -> list[dict[str, object]]:
    return [
        {
            "chapter_id": chapter["chapter_id"],
            "irreversible_change": chapter["dramatic_turn"],
            "scene_ids": [
                scene["scene_id"] for scene in scenes
                if scene["chapter_id"] == chapter["chapter_id"]
            ],
        }
        for chapter in chapters
    ]


def _chapters(rows: list[dict[str, Any]], chapters: list[object]) -> list[dict[str, str]]:
    clean: list[dict[str, str]] = []
    seen_turns: set[str] = set()
    for row, item in zip(rows, chapters):
        if not isinstance(item, dict):
            raise ValueError("chapter plan must be an object")
        turn = _text(item.get("dramatic_turn"), "chapter dramatic turn")
        if turn in seen_turns:
            raise ValueError("chapter dramatic turns must be distinct")
        seen_turns.add(turn)
        clean.append({
            "chapter_id": str(row["chapter_id"]),
            "volume_id": str(row["volume_id"]),
            "title": _text(item.get("title"), "chapter title"),
            "dramatic_turn": turn,
            "obligation": _text(item.get("obligation"), "chapter obligation"),
            "reader_question": _text(item.get("reader_question"), "reader question"),
        })
    return clean


def _narrative_design(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {field: str(value.get(field) or "").strip()[:500]
            for field in _NARRATIVE_FIELDS if str(value.get(field) or "").strip()}


def _characters(characters: object) -> list[dict[str, str]]:
    if characters is not None and not isinstance(characters, list):
        raise ValueError("planning characters must be a list")
    clean: list[dict[str, str]] = []
    known_names: set[str] = set()
    for item in characters or []:
        if not isinstance(item, dict):
            raise ValueError("planning character must be an object")
        name = _text(item.get("name"), "character name")
        if name in known_names:
            raise ValueError(f"duplicate planning character: {name}")
        known_names.add(name)
        importance = str(item.get("importance") or "secondary").strip()
        if importance not in {"major", "secondary", "cameo"}:
            raise ValueError(f"invalid character importance: {importance}")
        clean.append({
            "name": name,
            "role": _text(item.get("role"), "character role"),
            "importance": importance,
            "background": _text(item.get("background"), "character background"),
            "desire": _text(item.get("desire"), "character desire"),
        })
    return clean


def normalize_scene_window(
    answer: object, chapter_budget: dict[str, Any], *, start_index: int
) -> list[dict[str, Any]]:
    """Assign IDs and exact character targets after creative scene selection."""
    expected = int(chapter_budget["scene_count"])
    if expected < 1 or not isinstance(answer, list) or len(answer) != expected:
        raise ValueError(f"chapter window requires exactly {expected} scenes")
    target = int(chapter_budget["target_words"])
    weights = [item.get("length_weight", 1) if isinstance(item, dict) else 1 for item in answer]
    targets = _weighted_targets(target, weights)
    normalized: list[dict[str, Any]] = []
    for offset, item in enumerate(answer):
        if not isinstance(item, dict):
            raise ValueError("scene plan must be an object")
        participants = item.get("participants")
        if not isinstance(participants, list) or not participants:
            raise ValueError("scene participants must be a nonempty list")
        people = [_text(person, "scene participant") for person in participants]
        normalized.append({
            "scene_id": f"scene_{start_index + offset:04d}",
            "chapter_id": str(chapter_budget["chapter_id"]),
            "volume_id": str(chapter_budget["volume_id"]),
            "target_chars": targets[offset],
            "story_time": str(item.get("story_time") or "").strip()[:200],
            "participants": people,
            **{field: _text(item.get(field), f"scene {field}") for field in _SCENE_FIELDS},
            "rhythm_role": normalize_rhythm_role(
                item.get("rhythm_role"), item.get("function")
            ),
        })
    return normalized


def chapter_obligations(plan: dict[str, Any]) -> dict[str, dict[str, str]]:
    return {
        str(chapter["chapter_id"]): {
            "reader_question": str(chapter["reader_question"]),
            "promised_reward": str(chapter["obligation"]),
            "withheld_information": "",
            "payoff_or_delay": str(chapter["dramatic_turn"]),
            "anti_summary_requirement": "关键改变须通过行动和后果呈现。",
            "chapter_ending_hook": str(chapter["dramatic_turn"]),
        }
        for chapter in plan["chapters"]
    }


def render_outline(plan: dict[str, Any]) -> str:
    lines = [
        str(plan["premise"]),
        f"中心问题：{plan['central_question']}",
        f"终局选择：{plan['ending_choice']}",
    ]
    design = plan.get("narrative_design") or {}
    if isinstance(design, dict):
        lines.extend(f"{field}：{value}" for field, value in design.items() if value)
    previous_volume = ""
    for chapter in plan["chapters"]:
        volume_id = str(chapter["volume_id"])
        if volume_id != previous_volume:
            index = int(volume_id.rsplit("_", 1)[-1]) - 1
            lines.extend(["", f"## {volume_id}", str(plan["volume_obligations"][index])])
            previous_volume = volume_id
        lines.extend([
            "",
            f"### {chapter['chapter_id']} {chapter['title']}",
            str(chapter["obligation"]),
            f"转向：{chapter['dramatic_turn']}",
        ])
    return "\n".join(lines)


def normalize_rhythm_role(value: object, function: object = "") -> str:
    """Reduce creative rhythm prose to the small machine-owned role vocabulary."""

    raw = str(value or "").strip().lower().replace("-", "_")
    if raw in RHYTHM_ROLES:
        return raw
    text = f"{raw} {str(function or '').strip().lower()}"
    markers = (
        ("setup", ("铺垫", "建立", "引入", "开场", "慢起", "setup")),
        ("payoff", ("兑现", "回收", "和解", "解答", "终局", "payoff")),
        ("aftermath", ("余波", "善后", "事后", "收束", "aftermath")),
        ("climax", ("高潮", "决战", "决裂", "climax")),
        ("bridge", ("关系", "衔接", "承接", "bridge")),
        ("transition", ("过场", "转场", "迁移", "transition")),
        ("escalation", ("升级", "加速", "冲突", "递进", "翻转", "escalation")),
    )
    for role, words in markers:
        if any(word in text for word in words):
            return role
    return "escalation"


def _text(value: object, label: str) -> str:
    result = str(value or "").strip()
    if not result or result.lower() in {"none", "null", "todo", "tbd"}:
        raise ValueError(f"{label} cannot be empty or a placeholder")
    return result


__all__ = [
    "PLAN_SCHEMA", "RHYTHM_ROLES", "chapter_obligations", "normalize_initial_plan",
    "normalize_rhythm_role", "normalize_scene_window", "rebalance_lean_budget", "render_outline",
]
