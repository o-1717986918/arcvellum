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
    is_blank_scene_scaffold,
    load_scene_facts,
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
        planning_delivery=None,
    ) -> None:
        self.gateway = gateway or RoleConversationGateway(
            config, data_root=data_root / "pi-conversations"
        )
        self.event_sink = event_sink
        self.planning_delivery = planning_delivery

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
                _check_existing_first_window(root, plan)
            except ValueError as exc:
                self._emit_validation_failure("initial", exc)
                answer = self._ask(
                    root,
                    _initial_repair_prompt(answer, budget, exc),
                    phase="initial-repair",
                )
                budget = rebalance_lean_budget(base_budget, answer)
                plan = normalize_initial_plan(answer, budget, project_digest=digest)
                _check_existing_first_window(root, plan)
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

        if self.planning_delivery:
            return self.planning_delivery(root, self.gateway, prompt,
                layer_id="planning.v2.initial" if phase.startswith("initial") else "planning.v2.window",
                kind="planning-initial" if phase.startswith("initial") else "planning-window",
                context={"phase": phase}, event_sink=observe)
        response = self.gateway.run(root, prompt, role="worker", timeout=900, event_sink=observe)
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
    directions = list(dict.fromkeys(
        f"[{row.get('source_kind', '')}] {row.get('message', '')}" for row in read_directions(root, limit=200) if row.get("status") == "active"
    ))
    _, source_context = imported_source_context(root)
    existing_outline = root / "plot" / "outline.md"
    existing_scenes = [
        f"### {path.name}\n{path.read_text(encoding='utf-8')[:5000]}"
        for path in sorted((root / "scenes").glob("scene_*.yaml"))[:8]
        if path.is_file() and not is_blank_scene_scaffold(path)
    ]
    chapter_rows = [
        {key: row[key] for key in ("chapter_id", "volume_id", "target_words", "scene_count")}
        for row in budget["chapter_budgets"]
    ]
    return "\n".join([
        "# 长篇创作规划",
        "你是作品主创。先理解作者希望读者进入怎样的世界、听见怎样的讲述声音、经历怎样的阅读旅程，再设计各阶段与章节的文学任务。世界的展开、人物相遇、时间流逝、风俗与群体生活、事件概述、情感与关系、发现与高潮都可以承担章节价值。选择与作品相称的叙事模式、叙述者声音、视角、时间和详略，让它们随章节任务变化。高自由度或开放式作品可用 ending_choice 记录条件性的收束可能，让后来创作发展其形状。开篇可以由世界、讲述者、时间概述或人物相遇引入，选择最能建立本作审美期待的方式。",
        "用自然文字交付完整规划，按卷、章和正文单元展开创作札记，列明文学任务、阅读经验、叙述策略与篇幅权重。",
        "chapters 与下列章节容量顺序相同；first_window 只写第一章场景，数量匹配预算。用户指定的章序、终局位置与最终画面优先。",
        "scenes 是按阅读顺序安排的正文单元，可以是现场、概述、世界介绍、插叙、风俗叙述或自由组合。字段：name, function, obligation；participants 写实际参与的人名数组，叙述者讲述的单元可填 []。按需要填写 conflict, information_release, consequence, setup_payoff_role；consequence 也可以记录读者理解或作品尺度的变化。narrative_strategy 自由写本段的叙述声音、时间跨度、详略与主要表达方式；story_time 与 length_weight 表达时间和篇幅选择。rhythm_role 取 setup、escalation、climax、payoff、aftermath、bridge、transition 之一。",
        "已有场景档案是作者已定的场面事实；first_window 保持其场次、章节、参与人物与目标容量，围绕其中尚未决定的情节展开。",
        "返回字段：premise, central_question, ending_choice, narrative_design, volume_obligations, volume_length_weights, chapters, first_window, characters, world_facts。narrative_design 可写 narrative_mode、temporal_structure、viewpoint_design、pacing_design、structural_signature、narrator_voice、world_presentation。每章写 title、dramatic_turn、obligation、reader_question、literary_task，并可写 length_weight。literary_task 写该章在全书中的文学意义；dramatic_turn 可以是人物局面、世界认识或阅读经验的转向。volume_length_weights 是按卷排列的相对篇幅权重；长度权重表达详略，内核按全书目标核算。",
        "每个人物只写 name, role, importance(major/secondary/cameo), background, desire。只列全书重要人物；first_window 中所有有专名的 participants 必须逐字复用 characters 的 name，临时路人使用无专名角色称谓。world_facts 只写当前故事确需成立的虚构世界事实与机制；章场数量、人物出场范围、视角和语言形式留在规划或用户方向中。尚未确定的世界事实保持开放，现实题材可返回空数组。",
        "安排值得展开的核心经验与适合概述的过程，让世界尺度与人物距离各有伸缩。叙述者可以直接讲述世界、连接时段、观察群体、发表有本作声音的评论；人物互动可以承载自主反应与关系变化。选择信息进入作品的最佳位置和讲述方式。单元的篇幅由文学任务支撑，细节的密度随阅读兴趣和整体节奏变化。人物在场说出的话和具体举动留给推演与正文发展。相邻单元承接已发生的事实，既定时间和数值事实保持一致，后续章节按实际创作滚动展开。",
        "\n## 作品约束\n" + (root / "project.yaml").read_text(encoding="utf-8")[:5000],
        "\n## 用户方向\n" + ("\n".join(directions)[-5000:] or "无额外方向"),
        "\n## 已有大纲\n" + (
            existing_outline.read_text(encoding="utf-8")[:5000]
            if existing_outline.is_file() else "无"
        ),
        "\n## 已填场景档案\n" + ("\n".join(existing_scenes)[:14000] or "无"),
        "\n## 导入作品的可追溯片段\n" + (source_context or "无导入来源")
        + "\n片段不代表全文；既有事实按来源记录，待确认设想另列创作札记。",
        "\n## 体量与章节分配\n" + json.dumps(
            {"totals": budget["totals"], "chapters": chapter_rows},
            ensure_ascii=False, separators=(",", ":"),
        ),
    ])


def _window_prompt(
    root: Path, plan: dict[str, Any], chapter: dict[str, str], budget_row: dict[str, Any]
) -> str:
    directions = [f"[{row.get('source_kind', '')}] {row.get('message', '')}" for row in read_directions(root, limit=200) if row.get("status") == "active"]
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
        "你是作品主创。先判断当前章节在全书阶段中的文学任务，再按实际创作发展叙述声音、阅读顺序、时间跨度与详略。世界介绍、事件概述、群体生活、插叙与人物现场都可成为正文单元，并可自由组合。",
        "用自然文字逐一交付本章正文单元，说明各自文学任务、阅读经验、叙述策略、参与人物与篇幅权重。",
        "单元数量与预算一致，每项包含 name, function, obligation；participants 写实际参与的人名数组，纯叙述可填 []。conflict, information_release, consequence, setup_payoff_role 按文学任务填写；narrative_strategy 自由表达叙述声音、时间尺度、详略与组织方式。可加 story_time、length_weight。rhythm_role 取 setup、escalation、climax、payoff、aftermath、bridge、transition 之一。",
        "有专名的 participants 必须逐字复用 registered_characters；不得用同义姓名替换已登记人物，临时角色保持无专名。严格遵守 chapter_spine 的章序与 ending_choice 位置，除非用户明确要求，不追加尾声或续集钩子。",
        "沿用已确认的人物、世界事实与时间口径；用 scene.story_time 标清倒叙或交错叙事中的位置。单元详略按世界认识、风俗趣味、思想、情感、时间和人物经验分配。used_events 是已使用事件的摘要，用于安排新的后果与读者认识。",
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
        "依据校验反馈，以自然文字重新交付完整规划，使卷、章和正文单元的对应关系清楚。",
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
        "依据校验反馈，以自然文字重新交付本章完整单元规划，清楚列明各单元的文学任务与组织。",
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


def _check_existing_first_window(root: Path, plan: dict[str, Any]) -> None:
    planned = {scene["scene_id"]: scene for scene in plan["scenes"]}
    for path in sorted((root / "scenes").glob("scene_*.yaml")):
        if is_blank_scene_scaffold(path):
            continue
        facts = load_scene_facts(path)
        scene = planned.get(path.stem)
        if scene is None:
            raise ValueError(f"existing authored scene {path.stem} is absent from first_window")
        if facts.scene_id != scene["scene_id"] or facts.chapter_id != scene["chapter_id"]:
            raise ValueError(f"existing authored scene {path.stem} identity or chapter differs")
        if facts.word_count_target and facts.word_count_target != scene["target_chars"]:
            raise ValueError(
                f"existing authored scene {path.stem} target is {facts.word_count_target}, "
                f"first_window target is {scene['target_chars']}"
            )
        if facts.participants and set(facts.participants) != set(scene["participants"]):
            raise ValueError(
                f"existing authored scene {path.stem} participants are {facts.participants}, "
                f"first_window participants are {scene['participants']}"
            )


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
