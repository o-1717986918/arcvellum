"""Rolling longform planning through one creative Pi conversation per window."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from literary_engineering_studio_engine.public.literary import (
    PLAN_SCHEMA,
    calculate_word_budget,
    chapter_obligations,
    materialize_lean_window,
    normalize_initial_plan,
    normalize_scene_window,
    rebalance_lean_budget,
    render_outline,
)
from literary_engineering_studio_engine.public.projects import atomic_write_text

from .project_manager import read_directions
from .lean_source_context import imported_source_context
from ..runtime.role_conversation import RoleConversationGateway


class LeanLongformPlanningService:
    def __init__(
        self,
        config: dict[str, Any],
        *,
        data_root: Path,
        gateway: RoleConversationGateway | None = None,
        event_sink: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.gateway = gateway or RoleConversationGateway(
            config, data_root=data_root / "pi-conversations"
        )
        self.event_sink = event_sink

    def ensure_initial(self, project_root: Path) -> dict[str, Any]:
        root = project_root.expanduser().resolve()
        plan_path, budget_path = _paths(root)
        if not (root / "project.yaml").is_file():
            raise FileNotFoundError("project.yaml is missing")
        digest = _project_contract_digest(root)
        budget = _read_json(budget_path) or calculate_word_budget(root)
        base_budget = budget
        plan = _read_json(plan_path)
        if plan:
            _check_plan(plan, digest)
        else:
            prompt = _initial_prompt(root, budget)
            answer = self._ask(root, prompt, phase="initial")
            try:
                budget = rebalance_lean_budget(base_budget, answer)
                plan = normalize_initial_plan(answer, budget, project_digest=digest)
            except ValueError as exc:
                self._emit_validation_failure("initial", exc)
                answer = self._ask(
                    root,
                    _initial_repair_prompt(answer, budget, exc),
                    phase="initial-repair",
                )
                budget = rebalance_lean_budget(base_budget, answer)
                plan = normalize_initial_plan(answer, budget, project_digest=digest)
            _write_json(plan_path, plan)
        if not budget_path.is_file() or _read_json(budget_path) != budget:
            _write_json(budget_path, budget)
        self._materialize(root, plan, plan_path, budget_path)
        return plan

    def expand_next_window(self, project_root: Path) -> bool:
        root = project_root.expanduser().resolve()
        plan = self.ensure_initial(root)
        plan_path, budget_path = _paths(root)
        budget = _read_json(budget_path)
        rows = budget.get("chapter_budgets")
        rows = rows if isinstance(rows, list) else []
        planned = {str(scene["chapter_id"]) for scene in plan["scenes"]}
        next_row = next(
            (row for row in rows if str(row["chapter_id"]) not in planned), None
        )
        if next_row is None:
            return False
        chapter = next(
            item for item in plan["chapters"]
            if item["chapter_id"] == next_row["chapter_id"]
        )
        prompt = _window_prompt(root, plan, chapter, next_row)
        answer = self._ask(root, prompt, phase="chapter-window")
        try:
            scenes = normalize_scene_window(
                answer.get("scenes"), next_row, start_index=len(plan["scenes"]) + 1
            )
        except ValueError as exc:
            self._emit_validation_failure("chapter-window", exc)
            answer = self._ask(
                root,
                _window_repair_prompt(answer, next_row, exc),
                phase="chapter-window-repair",
            )
            scenes = normalize_scene_window(
                answer.get("scenes"), next_row, start_index=len(plan["scenes"]) + 1
            )
        updated_events = [
            {
                **item,
                "scene_ids": [scene["scene_id"] for scene in scenes],
            }
            if isinstance(item, dict) and item.get("chapter_id") == chapter["chapter_id"]
            else item
            for item in _event_budget_rows(plan)
        ]
        updated = {
            **plan,
            "scenes": [*plan["scenes"], *scenes],
            "event_budget": updated_events,
        }
        _write_json(plan_path, updated)
        self._materialize(root, updated, plan_path, budget_path)
        return True

    def _materialize(
        self, root: Path, plan: dict[str, Any], plan_path: Path, budget_path: Path
    ) -> None:
        materialize_lean_window(
            root,
            scenes=list(plan["scenes"]),
            obligations=chapter_obligations(plan),
            sources=(root / "project.yaml", plan_path, budget_path),
            outline_text=render_outline(plan),
        )

    def _ask(self, root: Path, prompt: str, *, phase: str) -> dict[str, Any]:
        def observe(event: str, data: dict[str, Any]) -> None:
            if self.event_sink is not None:
                self.event_sink(event, {**data, "planning_phase": phase})

        response = self.gateway.run(
            root, prompt, role="worker", timeout=900, event_sink=observe
        )
        return _json_answer(response.answer)

    def _emit_validation_failure(self, phase: str, error: ValueError) -> None:
        if self.event_sink is not None:
            self.event_sink(
                "planning.validation_failed",
                {
                    "planning_phase": phase,
                    "message": str(error),
                    "recovery": "bounded-structure-repair",
                },
            )


def _initial_prompt(root: Path, budget: dict[str, Any]) -> str:
    directions = [str(row.get("message") or "") for row in read_directions(root, limit=10)]
    _, source_context = imported_source_context(root)
    existing_outline = root / "plot" / "outline.md"
    chapter_rows = [
        {key: row[key] for key in ("chapter_id", "volume_id", "target_words", "scene_count")}
        for row in budget["chapter_budgets"]
    ]
    return "\n".join([
        "# 长篇创作规划",
        "你是作品主创。先设计这部作品独有的组织形式，再安排因果骨架、全书节奏与每章戏剧转向。选择叙事模式、视角组织、事件呈现顺序与故事时间关系；可以顺叙、倒叙、交错或其他与作品相称的形式。高自由度或开放式作品可以把 ending_choice 写成有条件的可能结局，让后来人物的实际选择决定它的形状；开篇挑真正会彼此改变关系的少数人物入场，让第一场早早出现值得回应的称呼、误解、邀约、冒犯、袒露或临场变卦。其他人物可等他们有自己的戏时再出现，职业流程只做生活背景。",
        "只返回一个 JSON 对象；不写任务回执、文件路径、ID、字数或模型说明。",
        "chapters 与下列章节容量顺序相同；first_window 只写第一章场景，数量匹配预算。用户指定的章序、终局位置与最终画面优先。",
        "场景字段：name, function, participants(人名数组), conflict, information_release, consequence, setup_payoff_role, rhythm_role, obligation；可加 story_time 和 length_weight。story_time 写本场在故事时间中的位置，场景排列是阅读顺序。rhythm_role 取 setup、escalation、climax、payoff、aftermath、bridge、transition 之一。",
        "返回字段：premise, central_question, ending_choice, narrative_design, volume_obligations, volume_length_weights, chapters, first_window, characters, world_facts。narrative_design 可写 narrative_mode、temporal_structure、viewpoint_design、pacing_design、structural_signature。每章写 title、dramatic_turn、obligation、reader_question，并可写 length_weight。volume_length_weights 是按卷排列的相对篇幅权重。长度权重只表达详略，内核按全书目标核算；场景数是容量，事件由你决定。",
        "每个人物只写 name, role, importance(major/secondary/cameo), background, desire。只列全书重要人物；first_window 中所有有专名的 participants 必须逐字复用 characters 的 name，临时路人使用无专名角色称谓。world_facts 只写当前故事确需成立的虚构世界事实与机制；章场数量、人物出场范围、视角和语言形式留在规划或用户方向中。尚未确定的世界事实保持开放，现实题材可返回空数组。",
        "用角色选择与后果支撑章节转向；让时间调度、视角切换和章节长短共同服务阅读体验。人物之间的生活语言、玩笑、误会、亲疏与突然改变的看法本身就能支撑戏剧变化；每人有自己的兴趣和词域。给单场保留可供对话、心理、环境生长的中心压力：conflict 写冲突的双方与欲望，consequence 可以写条件性的可能变化；尚待角色在场说出的话、做出的举动及其具体结果留给推演与正文。其他世界信息可以随人物认识逐步展开。相邻场景承接已经发生的变化。既定时间和数值事实保持一致，未知事实保留未知。后续场景按章滚动展开。",
        "\n## 作品约束\n" + (root / "project.yaml").read_text(encoding="utf-8")[:5000],
        "\n## 用户方向\n" + ("\n".join(directions)[-5000:] or "无额外方向"),
        "\n## 已有大纲\n" + (
            existing_outline.read_text(encoding="utf-8")[:5000]
            if existing_outline.is_file() else "无"
        ),
        "\n## 导入作品的可追溯片段\n" + (source_context or "无导入来源")
        + "\n片段不代表全文；不确定的既有事实需留待来源核对，不可编造。",
        "\n## 体量与章节分配\n" + json.dumps(
            {"totals": budget["totals"], "chapters": chapter_rows},
            ensure_ascii=False, separators=(",", ":"),
        ),
    ])


def _window_prompt(
    root: Path, plan: dict[str, Any], chapter: dict[str, str], budget_row: dict[str, Any]
) -> str:
    directions = [str(row.get("message") or "") for row in read_directions(root, limit=10)]
    _, source_context = imported_source_context(root, max_chars=5000)
    context = {
        "premise": plan["premise"],
        "central_question": plan["central_question"],
        "ending_choice": plan["ending_choice"],
        "narrative_design": plan.get("narrative_design", {}),
        "chapter": chapter,
        "chapter_spine": plan["chapters"],
        "registered_characters": plan.get("characters", []),
        "world_facts": plan.get("world_facts", []),
        "previous_scene_consequences": [
            scene["consequence"] for scene in plan["scenes"][-3:]
        ],
        "previous_scene_rhythm_roles": [
            scene["rhythm_role"] for scene in plan["scenes"][-3:]
        ],
        "used_events": [
            {
                "scene_id": scene["scene_id"],
                "function": scene["function"],
                "information_release": scene["information_release"],
                "consequence": scene["consequence"],
            }
            for scene in plan["scenes"]
        ],
        "event_budget": next(
            (
                item for item in _event_budget_rows(plan)
                if isinstance(item, dict) and item.get("chapter_id") == chapter["chapter_id"]
            ),
            {},
        ),
        "target": {
            "scene_count": budget_row["scene_count"],
            "target_words": budget_row["target_words"],
        },
    }
    return "\n".join([
        "# 下一章场景窗口",
        "你是作品主创。按全书的叙事设计承接既有后果，为当前章节安排阅读顺序、故事时间、场景轻重与具体行动。",
        "只返回 JSON 对象，字段 scenes 是场景数组；不要输出编号、字数、路径或任务协议。",
        "场景数量与目标一致，每场包含 name, function, participants(人名数组), conflict, information_release, consequence, setup_payoff_role, rhythm_role, obligation；可加 story_time、length_weight 表达非线性故事时间与篇幅轻重。rhythm_role 取 setup、escalation、climax、payoff、aftermath、bridge、transition 之一。",
        "有专名的 participants 必须逐字复用 registered_characters；不得用同义姓名替换已登记人物，临时角色保持无专名。严格遵守 chapter_spine 的章序与 ending_choice 位置，除非用户明确要求，不追加尾声或续集钩子。",
        "沿用已确认的人物、世界事实与时间口径；用 scene.story_time 标清倒叙或交错叙事中的位置。场景详略按事件、人物关系、心理和空间需要分配；每场带来可辨认的新局面。used_events 是已使用事件的摘要，用于安排新的后果与读者认识。",
        "## 最近的用户方向\n" + ("\n".join(directions)[-5000:] or "无额外方向"),
        "## 导入来源片段\n" + (source_context or "无导入来源"),
        json.dumps(context, ensure_ascii=False, separators=(",", ":")),
    ])


def _initial_repair_prompt(
    answer: dict[str, Any], budget: dict[str, Any], error: ValueError
) -> str:
    chapter_rows = budget.get("chapter_budgets")
    chapter_rows = chapter_rows if isinstance(chapter_rows, list) else []
    volume_rows = budget.get("volume_budgets")
    volume_rows = volume_rows if isinstance(volume_rows, list) else []
    first_scene_count = int(chapter_rows[0]["scene_count"]) if chapter_rows else 0
    contract = {
        "chapters": len(chapter_rows),
        "volume_obligations": len(volume_rows),
        "first_window_scenes": first_scene_count,
    }
    return "\n".join([
        "# 长篇规划结构返修",
        "上一份规划没有通过机器契约。只返回修正后的完整 JSON 对象，不写解释或代码围栏。",
        "保留有效的创作决策；若场景数量超出契约，请由你合并或重排其戏剧功能，不要简单截断内容。",
        "所有原字段仍必须存在，场景和人物字段要求与上一轮相同。",
        "返修保持用户指定的章序、结局章节、最终画面、已登记人物姓名和时间口径。world_facts 只写虚构世界内部的事实与机制；场景与人物范围由既有规划和用户方向承载。",
        "## 精确数量契约",
        json.dumps(contract, ensure_ascii=False, separators=(",", ":")),
        "## 校验错误",
        str(error),
        "## 上一份回答",
        json.dumps(answer, ensure_ascii=False, separators=(",", ":")),
    ])


def _window_repair_prompt(
    answer: dict[str, Any], budget_row: dict[str, Any], error: ValueError
) -> str:
    contract = {
        "chapter_id": str(budget_row["chapter_id"]),
        "scene_count": int(budget_row["scene_count"]),
        "target_words": int(budget_row["target_words"]),
    }
    return "\n".join([
        "# 章节场景窗口结构返修",
        "上一份场景窗口没有通过机器契约。只返回修正后的完整 JSON 对象，唯一顶层字段为 scenes；不写解释或代码围栏。",
        "保留有效的创作决策；若场景数量超出契约，请由你合并或重排其戏剧功能，不要简单截断内容。",
        "每场仍须包含 name, function, participants, conflict, information_release, consequence, setup_payoff_role, rhythm_role, obligation。",
        "返修只解决契约错误，不改动既定章序、结局位置、已登记人物姓名或时间口径，也不新增尾声与续集钩子。",
        "## 精确数量契约",
        json.dumps(contract, ensure_ascii=False, separators=(",", ":")),
        "## 校验错误",
        str(error),
        "## 上一份回答",
        json.dumps(answer, ensure_ascii=False, separators=(",", ":")),
    ])


def _paths(root: Path) -> tuple[Path, Path]:
    return (
        root / "plot" / "lean_project_plan.json",
        root / "plot" / "word_budget" / "word_budget.json",
    )


def _event_budget_rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    existing = plan.get("event_budget")
    if isinstance(existing, list) and existing:
        return [item for item in existing if isinstance(item, dict)]
    return [
        {
            "chapter_id": chapter["chapter_id"],
            "irreversible_change": chapter["dramatic_turn"],
            "scene_ids": [
                scene["scene_id"]
                for scene in plan.get("scenes") or []
                if scene.get("chapter_id") == chapter["chapter_id"]
            ],
        }
        for chapter in plan.get("chapters") or []
        if isinstance(chapter, dict)
    ]


def _project_contract_digest(root: Path) -> str:
    digest = hashlib.sha256()
    digest.update((root / "project.yaml").read_bytes())
    return digest.hexdigest()


def _check_plan(plan: dict[str, Any], digest: str) -> None:
    if plan.get("schema") != PLAN_SCHEMA or not isinstance(plan.get("scenes"), list):
        raise ValueError("lean project plan is invalid")
    if plan.get("project_digest") != digest:
        raise ValueError("project direction changed after planning; reconcile the plan before resuming")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"invalid planning JSON: {path.name}")
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _json_answer(answer: str) -> dict[str, Any]:
    text = answer.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("planning response must be a JSON object")
    return value


__all__ = ["LeanLongformPlanningService"]
