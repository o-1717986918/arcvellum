"""Replace only the uncommitted suffix of a lean long-form plan."""

from __future__ import annotations

import hashlib
from io import StringIO
import json
from pathlib import Path
from typing import Any, Mapping

from literary_engineering_studio_engine.public.literary import (
    chapter_obligations,
    materialize_lean_window,
    normalize_scene_window,
    render_outline,
)
from literary_engineering_studio_engine.public.projects import atomic_write_batch
from ruamel.yaml import YAML

from ..runtime.role_conversation import RoleConversationGateway


def replan_lean_future(
    root: Path,
    gateway: RoleConversationGateway,
    *,
    chapter_scene_counts: Mapping[str, int],
    direction: str,
) -> dict[str, Any]:
    """Rebuild a contiguous future suffix while preserving committed work."""

    project = root.expanduser().resolve()
    if not direction.strip():
        raise ValueError("future replan requires an approved creative direction")
    plan_path = project / "plot" / "lean_project_plan.json"
    budget_path = project / "plot" / "word_budget" / "word_budget.json"
    project_path = project / "project.yaml"
    project_bytes = project_path.read_bytes()
    plan_bytes, budget_bytes = plan_path.read_bytes(), budget_path.read_bytes()
    plan, budget = json.loads(plan_bytes), json.loads(budget_bytes)
    committed = _committed_prefix(project, list(plan.get("scenes") or []))
    counts, active_chapters = _validated_counts(plan, budget, committed, chapter_scene_counts)
    future, event_budget, narrative_design = _ask_for_future(
        project, gateway, plan, budget, committed, counts, direction,
    )
    revised_budget = _rebalance_budget(budget, counts)
    revised_project = _revised_project_contract(
        project_bytes, int(revised_budget["totals"]["scene_count"]),
    )
    revised_plan = {
        **plan,
        "project_digest": hashlib.sha256(revised_project.encode("utf-8")).hexdigest(),
        "scenes": [*committed, *future],
        "narrative_design": narrative_design or plan.get("narrative_design", {}),
        "event_budget": [
            *[
                item for item in plan.get("event_budget") or []
                if isinstance(item, dict) and str(item.get("chapter_id") or "") not in active_chapters
            ],
            *event_budget,
        ],
    }
    history = _history_writes(
        project, project_bytes, plan_bytes, budget_bytes, committed, direction,
    )
    atomic_write_batch(history)
    _commit_replan(
        project, project_path, plan_path, budget_path,
        project_bytes, plan_bytes, budget_bytes,
        revised_project, revised_plan, revised_budget,
        committed_count=len(committed),
    )
    return {
        "committed_prefix_count": len(committed),
        "future_scene_ids": [scene["scene_id"] for scene in future],
        "future_scene_count": len(future),
        "book_scene_count": revised_budget["totals"]["scene_count"],
        "book_target_chinese_chars": revised_budget["totals"]["target_chinese_chars"],
        "chapter_scene_counts": counts,
        "event_budget": event_budget,
        "history_path": next(iter(history)).parent.relative_to(project).as_posix(),
        "next_uncommitted_scene_id": future[0]["scene_id"] if future else "",
        "checkpoint_state": "future-plan-replaced; creation remains stopped until explicitly recovered",
    }


def _committed_prefix(root: Path, scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    committed: list[dict[str, Any]] = []
    found_gap = False
    for scene in scenes:
        scene_id = str(scene.get("scene_id") or "")
        receipt = root / "workflow" / "scene_commits" / f"{scene_id}.json"
        prose = root / "drafts" / "scenes" / f"{scene_id}.md"
        if receipt.is_file() and prose.is_file() and not found_gap:
            committed.append(scene)
            continue
        if receipt.is_file() or prose.is_file():
            raise ValueError("future replan found non-contiguous committed work")
        found_gap = True
    return committed


def _validated_counts(
    plan: dict[str, Any], budget: dict[str, Any], committed: list[dict[str, Any]],
    supplied: Mapping[str, int],
) -> tuple[dict[str, int], set[str]]:
    chapter_rows = list(budget.get("chapter_budgets") or [])
    chapter_ids = [str(row.get("chapter_id") or "") for row in chapter_rows]
    active = _active_chapter_ids(chapter_ids, committed)
    if set(supplied) != set(active):
        raise ValueError("future replan requires one final scene count for every remaining chapter")
    counts, committed_counts = _normalize_chapter_counts(active, committed, supplied)
    future_count = sum(counts[key] - committed_counts[key] for key in active)
    if future_count < 1 or future_count > 80:
        raise ValueError("future replan must contain 1-80 uncommitted scenes")
    plan_chapters = {str(row.get("chapter_id") or "") for row in plan.get("chapters") or []}
    if not set(active).issubset(plan_chapters):
        raise ValueError("future replan chapters are absent from the project spine")
    return counts, set(active)


def _active_chapter_ids(chapter_ids: list[str], committed: list[dict[str, Any]]) -> list[str]:
    if not chapter_ids:
        raise ValueError("future replan requires a chapter budget")
    current = str(committed[-1].get("chapter_id") or "") if committed else chapter_ids[0]
    if current not in chapter_ids:
        raise ValueError("committed scene chapter is absent from word budget")
    return chapter_ids[chapter_ids.index(current):]


def _normalize_chapter_counts(
    active: list[str], committed: list[dict[str, Any]], supplied: Mapping[str, int],
) -> tuple[dict[str, int], dict[str, int]]:
    committed_counts = {
        chapter_id: sum(scene.get("chapter_id") == chapter_id for scene in committed)
        for chapter_id in active
    }
    counts = {chapter_id: int(supplied[chapter_id]) for chapter_id in active}
    invalid = [
        chapter_id for chapter_id, value in counts.items()
        if value < max(1, committed_counts[chapter_id]) or value > 20
    ]
    if invalid:
        raise ValueError(
            "future replan chapter scene counts must preserve committed scenes and stay within 1-20"
        )
    return counts, committed_counts


def _ask_for_future(
    root: Path, gateway: RoleConversationGateway, plan: dict[str, Any], budget: dict[str, Any],
    committed: list[dict[str, Any]], counts: dict[str, int], direction: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    prompt = _future_prompt(plan, budget, committed, counts, direction)
    raw_answer = gateway.run(root, prompt, role="worker", timeout=900).answer
    response: dict[str, Any] = {"malformed_answer": raw_answer[-12000:]}
    try:
        response = _json_answer(raw_answer)
        future, events = _normalize_future(plan, budget, committed, counts, response)
        _reject_exact_event_replays(committed, future)
    except ValueError as exc:
        repaired = _repair_future(
            root, gateway, plan, budget, committed, counts, direction, response, exc,
        )
        future, events = _normalize_future(plan, budget, committed, counts, repaired)
        _reject_exact_event_replays(committed, future)
        response = repaired
    design = response.get("narrative_design")
    return future, events, (
        {key: str(value).strip()[:500] for key, value in design.items() if isinstance(key, str) and str(value).strip()}
        if isinstance(design, dict) else {}
    )


def _future_prompt(
    plan: dict[str, Any], budget: dict[str, Any], committed: list[dict[str, Any]],
    counts: dict[str, int], direction: str,
) -> str:
    committed_counts = {
        chapter_id: sum(1 for scene in committed if scene.get("chapter_id") == chapter_id)
        for chapter_id in counts
    }
    request = [
        {
            "chapter_id": chapter_id,
            "remaining_scene_count": total - committed_counts[chapter_id],
            "chapter": next(row for row in plan["chapters"] if row["chapter_id"] == chapter_id),
            "target_chinese_chars": next(
                int(row["target_words"]) for row in budget["chapter_budgets"]
                if row["chapter_id"] == chapter_id
            ),
        }
        for chapter_id, total in counts.items()
    ]
    used = [
        {
            "scene_id": scene["scene_id"],
            "function": scene["function"],
            "information_release": scene["information_release"],
            "consequence": scene["consequence"],
        }
        for scene in committed
    ]
    return "\n".join([
        "# 未写场景后缀重排",
        "你是作品主创。只返回 JSON 对象：chapters 是按请求顺序排列的数组；可同时返回 narrative_design，更新全书叙事模式、时间结构、视角、节奏与组织特色。",
        "每章对象只含 chapter_id, irreversible_change, scenes。irreversible_change 必须说明本章结束后哪项人物处境、关系、资源、知识或承诺不能回到章首。",
        "scenes 数量匹配 remaining_scene_count。每场包含 name, function, participants(人名数组), conflict, information_release, consequence, setup_payoff_role, rhythm_role, obligation；可加 story_time 和 length_weight 重新组织故事时间与相对篇幅。rhythm_role 使用 setup/escalation/climax/payoff/aftermath/bridge/transition。",
        "统筹完整未来后缀：按用户认可的方向安排各章不同的不可逆转向，承接已提交事件的后果，分配兑现与余波。章节的 dramatic_turn 与 obligation 在本章行动中实现；已提交正文和既定事实保持不变。",
        "阅读顺序与故事时间可以不同，story_time 标记故事时间；时间调度服务作品的叙事设计。length_weight 表达场景详略，按选择、阻力、人物关系、心理与空间的需要分配。",
        "participants 逐字复用注册人物姓名；一次性无名路人可用角色称谓。",
        "## 用户认可的重排方向\n" + direction[:5000],
        "## 终局\n" + str(plan.get("ending_choice") or ""),
        "## 全书叙事设计\n" + json.dumps(plan.get("narrative_design") or {}, ensure_ascii=False),
        "## 注册人物\n" + json.dumps([row["name"] for row in plan.get("characters") or []], ensure_ascii=False),
        "## 章节请求\n" + json.dumps(request, ensure_ascii=False),
        "## 已提交事件（均不得重演）\n" + json.dumps(used, ensure_ascii=False),
    ])


def _repair_future(
    root: Path, gateway: RoleConversationGateway, plan: dict[str, Any], budget: dict[str, Any],
    committed: list[dict[str, Any]], counts: dict[str, int], direction: str,
    answer: dict[str, Any], error: ValueError,
) -> dict[str, Any]:
    prompt = "\n".join([
        _future_prompt(plan, budget, committed, counts, direction),
        "## 结构或重复错误",
        str(error),
        "返回完整修正版；保留有效事件，但合并或替换重复事件，不能只换说法。",
        "## 上一份回答",
        json.dumps(answer, ensure_ascii=False),
    ])
    return _json_answer(gateway.run(root, prompt, role="worker", timeout=900).answer)


def _normalize_future(
    plan: dict[str, Any], budget: dict[str, Any], committed: list[dict[str, Any]],
    counts: dict[str, int], response: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = response.get("chapters")
    if not isinstance(rows, list) or [str(row.get("chapter_id") or "") for row in rows if isinstance(row, dict)] != list(counts):
        raise ValueError("future replan response must cover remaining chapters exactly once in order")
    registered = {str(item["name"]) for item in plan.get("characters") or []}
    future: list[dict[str, Any]] = []
    event_budget: list[dict[str, Any]] = []
    start_index = len(committed) + 1
    for row in rows:
        chapter_id, irreversible, scenes = _normalize_future_chapter(
            row, budget, committed, counts, start_index,
        )
        for scene in scenes:
            if any(name not in registered for name in scene["participants"]):
                raise ValueError("future replan uses a participant not registered in the project plan")
        future.extend(scenes)
        event_budget.append({
            "chapter_id": chapter_id,
            "irreversible_change": irreversible,
            "scene_ids": [scene["scene_id"] for scene in scenes],
        })
        start_index += len(scenes)
    return future, event_budget


def _normalize_future_chapter(
    row: object, budget: dict[str, Any], committed: list[dict[str, Any]],
    counts: dict[str, int], start_index: int,
) -> tuple[str, str, list[dict[str, Any]]]:
    if not isinstance(row, dict):
        raise ValueError("future replan chapter must be an object")
    chapter_id = str(row["chapter_id"])
    irreversible = str(row.get("irreversible_change") or "").strip()
    if not irreversible:
        raise ValueError(f"future replan chapter {chapter_id} requires an irreversible change")
    existing = [scene for scene in committed if scene.get("chapter_id") == chapter_id]
    remaining_count = counts[chapter_id] - len(existing)
    if remaining_count == 0:
        if row.get("scenes") != []:
            raise ValueError(f"future replan chapter {chapter_id} must contain no unwritten scenes")
        return chapter_id, irreversible, []
    budget_row = next(item for item in budget["chapter_budgets"] if item["chapter_id"] == chapter_id)
    remaining_target = max(
        int(budget_row["target_words"])
        - sum(int(scene.get("target_chars") or 0) for scene in existing),
        remaining_count * 1800,
    )
    scenes = normalize_scene_window(
        row.get("scenes"),
        {**budget_row, "scene_count": remaining_count, "target_words": remaining_target},
        start_index=start_index,
    )
    return chapter_id, irreversible, scenes


def _reject_exact_event_replays(
    committed: list[dict[str, Any]], future: list[dict[str, Any]],
) -> None:
    seen: dict[str, str] = {}
    duplicates: list[str] = []
    for scene in [*committed, *future]:
        scene_id = str(scene["scene_id"])
        signature = "|".join(
            "".join(str(scene.get(field) or "").split()).casefold()
            for field in ("function", "information_release", "consequence")
        )
        previous = seen.get(signature)
        if previous and scene in future:
            duplicates.append(f"{scene_id} repeats the event package of {previous}")
        else:
            seen[signature] = scene_id
    if duplicates:
        raise ValueError("future replan repeats existing events: " + "; ".join(duplicates[:8]))


def _rebalance_budget(budget: dict[str, Any], counts: dict[str, int]) -> dict[str, Any]:
    revised = json.loads(json.dumps(budget, ensure_ascii=False))
    for row in revised["chapter_budgets"]:
        chapter_id = str(row["chapter_id"])
        if chapter_id in counts:
            row["scene_count"] = counts[chapter_id]
        row["avg_scene_words"] = round(int(row["target_words"]) / int(row["scene_count"]))
    for volume in revised["volume_budgets"]:
        rows = [row for row in revised["chapter_budgets"] if row["volume_id"] == volume["volume_id"]]
        volume["scene_count"] = sum(int(row["scene_count"]) for row in rows)
        volume["avg_scene_words"] = round(int(volume["target_words"]) / volume["scene_count"])
    total = revised["totals"]
    total["scene_count"] = sum(int(row["scene_count"]) for row in revised["chapter_budgets"])
    total["avg_scene_words"] = round(int(total["target_words"]) / total["scene_count"])
    target = revised.get("target")
    if isinstance(target, dict):
        target["target_scenes"] = total["scene_count"]
        target["structure_source"] = "event_budget_replan"
    binding = revised.get("scene_inventory_binding")
    if isinstance(binding, dict):
        for row in binding.get("chapter_rows") or []:
            source = next(
                (item for item in revised["chapter_budgets"] if item["chapter_id"] == row.get("chapter_id")),
                None,
            )
            if source is not None:
                row["target_scene_count"] = source["scene_count"]
                row["avg_scene_words"] = source["avg_scene_words"]
    return revised


def _revised_project_contract(project_bytes: bytes, scene_count: int) -> str:
    yaml = YAML()
    value = yaml.load(project_bytes.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("project.yaml must contain a mapping")
    longform = value.get("longform_budget")
    if not isinstance(longform, dict):
        longform = {}
        value["longform_budget"] = longform
    longform["target_scenes"] = scene_count
    stream = StringIO()
    yaml.allow_unicode = True
    yaml.dump(value, stream)
    return stream.getvalue()


def _history_writes(
    root: Path, project_bytes: bytes, plan_bytes: bytes, budget_bytes: bytes,
    committed: list[dict[str, Any]], direction: str,
) -> dict[Path, str]:
    digest = hashlib.sha256(
        project_bytes + plan_bytes + budget_bytes + direction.encode("utf-8")
    ).hexdigest()[:16]
    folder = root / "workflow" / "plan_history" / f"future-replan-{digest}"
    writes: dict[Path, str] = {
        folder / "project.yaml": project_bytes.decode("utf-8"),
        folder / "lean_project_plan.json": plan_bytes.decode("utf-8"),
        folder / "word_budget.json": budget_bytes.decode("utf-8"),
        folder / "receipt.json": json.dumps({
            "operation": "future-replan",
            "committed_prefix_count": len(committed),
            "direction": direction,
        }, ensure_ascii=False, indent=2) + "\n",
    }
    for path in sorted((root / "scenes").glob("scene_*.yaml")):
        index = int(path.stem.rsplit("_", 1)[-1])
        if index > len(committed):
            writes[folder / "scenes" / path.name] = path.read_text(encoding="utf-8")
    return writes


def _commit_replan(
    root: Path, project_path: Path, plan_path: Path, budget_path: Path,
    project_bytes: bytes, plan_bytes: bytes, budget_bytes: bytes,
    project_text: str, plan: dict[str, Any], budget: dict[str, Any], *, committed_count: int,
) -> None:
    if (
        project_path.read_bytes() != project_bytes
        or plan_path.read_bytes() != plan_bytes
        or budget_path.read_bytes() != budget_bytes
    ):
        raise ValueError("project contract, chapter plan or budget changed while the future replan was being prepared")
    scene_root = (root / "scenes").resolve()
    original_uncommitted = {
        path: path.read_text(encoding="utf-8")
        for path in scene_root.glob("scene_*.yaml")
        if path.resolve().is_relative_to(scene_root)
        and path.stem.rsplit("_", 1)[-1].isdigit()
        and int(path.stem.rsplit("_", 1)[-1]) > committed_count
    }
    planned_paths = {scene_root / f"{scene['scene_id']}.yaml" for scene in plan["scenes"]}
    obsolete = set(original_uncommitted) - planned_paths
    atomic_write_batch({
        project_path: project_text,
        plan_path: json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
        budget_path: json.dumps(budget, ensure_ascii=False, indent=2) + "\n",
    })
    try:
        for path in obsolete:
            path.unlink()
        materialize_lean_window(
            root,
            scenes=plan["scenes"],
            obligations=chapter_obligations(plan),
            sources=(root / "project.yaml", plan_path, budget_path),
            outline_text=render_outline(plan),
            replace_uncommitted=True,
        )
    except Exception:
        for path in scene_root.glob("scene_*.yaml"):
            if path not in original_uncommitted and path.stem.rsplit("_", 1)[-1].isdigit() and int(path.stem.rsplit("_", 1)[-1]) > committed_count:
                path.unlink()
        atomic_write_batch({
            project_path: project_bytes.decode("utf-8"),
            plan_path: plan_bytes.decode("utf-8"),
            budget_path: budget_bytes.decode("utf-8"),
            **original_uncommitted,
        })
        raise


def _json_answer(answer: str) -> dict[str, Any]:
    text = answer.strip()
    if text.startswith("```"):
        text = "\n".join(text.splitlines()[1:-1]).strip()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("future replan response must be a JSON object")
    return value


__all__ = ["replan_lean_future"]
