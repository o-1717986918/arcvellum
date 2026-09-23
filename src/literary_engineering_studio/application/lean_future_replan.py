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
    if not committed:
        raise ValueError("future replan requires at least one committed scene")
    counts, active_chapters = _validated_counts(plan, budget, committed, chapter_scene_counts)
    future, event_budget = _ask_for_future(
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
    current = str(committed[-1].get("chapter_id") or "")
    if current not in chapter_ids:
        raise ValueError("committed scene chapter is absent from word budget")
    active = chapter_ids[chapter_ids.index(current):]
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
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
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
    return future, events


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
        "你是作品主创。只返回 JSON 对象，顶层字段 chapters 是按请求顺序排列的数组。",
        "每章对象只含 chapter_id, irreversible_change, scenes。irreversible_change 必须说明本章结束后哪项人物处境、关系、资源、知识或承诺不能回到章首。",
        "scenes 数量必须精确匹配 remaining_scene_count。每场只含 name, function, participants(人名数组), conflict, information_release, consequence, setup_payoff_role, rhythm_role, obligation。rhythm_role 使用 setup/escalation/climax/payoff/aftermath/bridge/transition。",
        "这是完整未来后缀的一次全局事件分配；每个场景字段用一条明确句子，单字段不超过八十个汉字，不重复解释，以确保 JSON 完整。",
        "这是事件预算，不是字数填槽。先分配不可逆事件、兑现和后果，再形成场景；字数只决定事件展开的厚度。事件不足时宁可让一场承载更复杂的行动—反作用—选择链，不得创造确认场、复述场或让变量复位。",
        "不得重演已提交场景中的会面、听名、核对、追问、递话、发现、拒绝、沉默或决定；不得把曾经发生过的认知再次写成‘第一次’。悬念只能推进、兑现或改变持有人，不能靠‘仍不拆、不问、不动、不说’维持原状。",
        "每场 consequence 必须留下可追踪的新状态；相邻场景的人物组合、行动阻力、信息增量和选择代价至少有两项不同。不得更改已提交正文、既有事实、章序和终局位置。",
        "章节请求内 chapter.dramatic_turn 与 chapter.obligation 是不可删、不可换章的硬义务：本章场景必须在行动层完整实现该 dramatic_turn；兑现锚只能嵌入既定章纲，不能取代章纲。",
        "先在内部把用户要求的每个不可逆兑现锚分配到唯一章节与唯一场景组，再生成 chapters。一个锚一旦兑现，后续章节只能承接其新后果，绝不能重新拆信、重新核出差额、重新确认姓名、重新过第一次夜或再次做同一交接。输出前逐场比较全书已提交事件和本次所有新场，删除或合并任何语义相同而只换名称的场景。",
        "全书最后一章若含分手、死亡、永久离开、无重逢等终局动作，终局必须发生在最后一场；所有揭示、取件、交接、核账、归还和导致终局选择的事件必须按因果排在它之前。不得在人物已经各自离开后倒叙补办‘分手前数日’的必要事件，也不得让前一场的 consequence 被下一场时间复位。",
        "participants 只能逐字复用注册人物姓名；一次性无名路人不列入 participants。不要用无关精确数字制造写实感。",
        "## 用户认可的重排方向\n" + direction[:5000],
        "## 终局\n" + str(plan.get("ending_choice") or ""),
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
    project_text: str, plan: dict[str, Any], budget: dict[str, Any],
) -> None:
    if (
        project_path.read_bytes() != project_bytes
        or plan_path.read_bytes() != plan_bytes
        or budget_path.read_bytes() != budget_bytes
    ):
        raise ValueError("project contract, chapter plan or budget changed while the future replan was being prepared")
    atomic_write_batch({
        project_path: project_text,
        plan_path: json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
        budget_path: json.dumps(budget, ensure_ascii=False, indent=2) + "\n",
    })
    try:
        materialize_lean_window(
            root,
            scenes=plan["scenes"],
            obligations=chapter_obligations(plan),
            sources=(root / "project.yaml", plan_path, budget_path),
            outline_text=render_outline(plan),
            replace_uncommitted=True,
        )
    except Exception:
        atomic_write_batch({
            project_path: project_bytes.decode("utf-8"),
            plan_path: plan_bytes.decode("utf-8"),
            budget_path: budget_bytes.decode("utf-8"),
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
