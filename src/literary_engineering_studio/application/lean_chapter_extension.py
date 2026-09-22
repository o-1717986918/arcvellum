"""Append scenes after a committed lean chapter and rebalance future inventory."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from literary_engineering_studio_engine.public.literary import (
    chapter_obligations,
    materialize_lean_window,
    normalize_scene_window,
    render_outline,
)
from literary_engineering_studio_engine.public.projects import atomic_write_batch

from ..runtime.role_conversation import RoleConversationGateway


def extend_lean_chapter(
    root: Path, gateway: RoleConversationGateway, *, chapter_id: str,
    additional_scenes: int, target_per_scene: int, direction: str,
) -> dict[str, Any]:
    """Grant a narrowly scoped, append-only planning action to Project Agent."""
    project = root.expanduser().resolve()
    if not 1 <= additional_scenes <= 8 or not 1800 <= target_per_scene <= 6000:
        raise ValueError("chapter extension requires 1-8 scenes and 1800-6000 characters per scene")
    if not direction.strip():
        raise ValueError("chapter extension requires an approved creative direction")
    plan_path = project / "plot" / "lean_project_plan.json"
    budget_path = project / "plot" / "word_budget" / "word_budget.json"
    plan_bytes, budget_bytes = plan_path.read_bytes(), budget_path.read_bytes()
    plan, budget = json.loads(plan_bytes), json.loads(budget_bytes)
    chapter, budget_row = _extension_context(project, plan, budget, chapter_id)
    existing = plan.get("scenes") or []
    new_scenes = _propose_extension(
        project, gateway, plan, chapter, budget_row, additional_scenes, target_per_scene, direction,
    )
    revised_plan = {**plan, "scenes": [*existing, *new_scenes]}
    revised_budget = _rebalance_budget(budget, chapter_id, additional_scenes, target_per_scene)
    _commit_extension(project, plan_path, budget_path, plan_bytes, budget_bytes, revised_plan, revised_budget)
    return {
        "chapter_id": chapter_id,
        "appended_scene_ids": [row["scene_id"] for row in new_scenes],
        "next_uncommitted_scene_id": new_scenes[0]["scene_id"],
        "chapter_scene_count": next(row["scene_count"] for row in revised_budget["chapter_budgets"] if row["chapter_id"] == chapter_id),
        "chapter_target_chinese_chars": budget_row["target_words"],
        "book_scene_count": revised_budget["totals"]["scene_count"],
        "book_target_chinese_chars": revised_budget["totals"]["target_chinese_chars"],
        "checkpoint_state": "pending-new-scenes; prior paused run reason is historical until the run resumes",
        "next_action": "resume-existing-goal",
    }


def _extension_context(
    root: Path, plan: dict[str, Any], budget: dict[str, Any], chapter_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    existing = plan.get("scenes") or []
    if not existing or str(existing[-1].get("chapter_id")) != chapter_id:
        raise ValueError("only the latest planned chapter can be extended")
    chapter = next((row for row in plan["chapters"] if row["chapter_id"] == chapter_id), None)
    budget_row = next((row for row in budget["chapter_budgets"] if row["chapter_id"] == chapter_id), None)
    if chapter is None or budget_row is None:
        raise ValueError("chapter is absent from the plan or word budget")
    _require_committed_prefix(root, existing, chapter_id)
    return chapter, budget_row


def _propose_extension(
    root: Path, gateway: RoleConversationGateway, plan: dict[str, Any], chapter: dict[str, Any],
    budget_row: dict[str, Any], count: int, target_per_scene: int, direction: str,
) -> list[dict[str, Any]]:
    answer = gateway.run(
        root, _extension_prompt(root, plan, chapter, budget_row, count, target_per_scene, direction),
        role="worker", timeout=900,
    ).answer.strip()
    if answer.startswith("```"):
        answer = "\n".join(answer.splitlines()[1:-1]).strip()
    response = json.loads(answer)
    if not isinstance(response, dict):
        raise ValueError("chapter extension response must be a JSON object")
    new_scenes = normalize_scene_window(
        response.get("scenes"),
        {**budget_row, "scene_count": count, "target_words": count * target_per_scene},
        start_index=len(plan["scenes"]) + 1,
    )
    registered = {str(item["name"]) for item in plan.get("characters") or []}
    for scene in new_scenes:
        if any(name not in registered for name in scene["participants"]):
            raise ValueError("extension uses a participant not registered in the project plan")
    return new_scenes


def _commit_extension(
    root: Path, plan_path: Path, budget_path: Path, plan_bytes: bytes, budget_bytes: bytes,
    plan: dict[str, Any], budget: dict[str, Any],
) -> None:
    if plan_path.read_bytes() != plan_bytes or budget_path.read_bytes() != budget_bytes:
        raise ValueError("chapter plan or budget changed while the extension was being prepared")
    writes = {
        plan_path: json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
        budget_path: json.dumps(budget, ensure_ascii=False, indent=2) + "\n",
    }
    atomic_write_batch(writes)
    try:
        materialize_lean_window(
            root,
            scenes=plan["scenes"],
            obligations=chapter_obligations(plan),
            sources=(root / "project.yaml", plan_path, budget_path),
            outline_text=render_outline(plan),
        )
    except Exception:
        atomic_write_batch({plan_path: plan_bytes.decode("utf-8"), budget_path: budget_bytes.decode("utf-8")})
        raise


def _require_committed_prefix(root: Path, scenes: list[dict[str, Any]], chapter_id: str) -> None:
    for scene in scenes:
        if scene["chapter_id"] != chapter_id:
            continue
        scene_id = str(scene["scene_id"])
        if not (root / "workflow" / "scene_commits" / f"{scene_id}.json").is_file():
            raise ValueError("chapter extension requires every prior scene to be committed")
        if not (root / "drafts" / "scenes" / f"{scene_id}.md").is_file():
            raise ValueError("chapter extension requires every prior scene body to exist")


def _extension_prompt(
    root: Path, plan: dict[str, Any], chapter: dict[str, Any], budget_row: dict[str, Any],
    count: int, target_per_scene: int, direction: str,
) -> str:
    last = plan["scenes"][-1]
    tail_path = root / "drafts" / "scenes" / f"{last['scene_id']}.md"
    tail = tail_path.read_text(encoding="utf-8")[-3500:]
    chapter_index = next(index for index, row in enumerate(plan["chapters"]) if row["chapter_id"] == chapter["chapter_id"])
    following = plan["chapters"][chapter_index + 1] if chapter_index + 1 < len(plan["chapters"]) else None
    return "\n".join([
        "# 当前章场景续补", "你是作品主创。只返回 JSON 对象，字段 scenes 是场景数组。",
        f"必须恰好追加 {count} 场，时间顺序在现有已晋升场景之后；不得把新场景倒插到已成稿事件之间，不得重演已发生的会面、发现或选择。",
        f"新增场景各自约 {target_per_scene} 中文内容字符的叙事负载；本章原定总量 {budget_row['target_words']}，不可修改已成稿或全书目标。",
        "每场字段为 name, function, participants(人名数组), conflict, information_release, consequence, setup_payoff_role, rhythm_role, obligation；rhythm_role 用 setup/escalation/climax/payoff/aftermath/bridge/transition 之一。",
        "每场必须有独立的动作阻力、人物选择和可追踪后果；不要用空白过场补字数。不得提前完成下一章戏剧转向或更改既定结局位置。",
        "participants 只能使用注册人物的姓名；一次性无名路人可以写进场景功能，但不要列为 participants。保留最新正文里的账目、线索和人物知识边界。",
        "## 用户认可的补场方向\n" + direction[:3000],
        "## 章节职责\n" + json.dumps(chapter, ensure_ascii=False),
        "## 下一章边界\n" + json.dumps(following, ensure_ascii=False),
        "## 已有本章场景\n" + json.dumps([row for row in plan["scenes"] if row["chapter_id"] == chapter["chapter_id"]], ensure_ascii=False),
        "## 注册人物\n" + json.dumps([row["name"] for row in plan.get("characters") or []], ensure_ascii=False),
        "## 已晋升末场正文结尾\n" + tail,
    ])


def _rebalance_budget(
    budget: dict[str, Any], chapter_id: str, added: int, target_per_scene: int,
) -> dict[str, Any]:
    revised = json.loads(json.dumps(budget, ensure_ascii=False))
    seen = False
    for row in revised["chapter_budgets"]:
        if row["chapter_id"] == chapter_id:
            row["scene_count"] += added
            seen = True
        elif seen:
            row["scene_count"] = math.ceil(int(row["target_words"]) / target_per_scene)
        row["avg_scene_words"] = round(int(row["target_words"]) / int(row["scene_count"]))
    for volume in revised["volume_budgets"]:
        rows = [row for row in revised["chapter_budgets"] if row["volume_id"] == volume["volume_id"]]
        volume["scene_count"] = sum(int(row["scene_count"]) for row in rows)
        volume["avg_scene_words"] = round(int(volume["target_words"]) / volume["scene_count"])
    total = revised["totals"]
    total["scene_count"] = sum(int(row["scene_count"]) for row in revised["chapter_budgets"])
    total["avg_scene_words"] = round(int(total["target_words"]) / total["scene_count"])
    binding = revised.get("scene_inventory_binding")
    if isinstance(binding, dict):
        for row in binding.get("chapter_rows") or []:
            source = next((item for item in revised["chapter_budgets"] if item["chapter_id"] == row.get("chapter_id")), None)
            if source is not None:
                row["target_scene_count"] = source["scene_count"]
                row["avg_scene_words"] = source["avg_scene_words"]
    return revised


__all__ = ["extend_lean_chapter"]
