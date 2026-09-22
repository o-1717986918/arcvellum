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
        plan = _read_json(plan_path)
        if plan:
            _check_plan(plan, digest)
        else:
            prompt = _initial_prompt(root, budget)
            answer = self._ask(root, prompt, phase="initial")
            try:
                plan = normalize_initial_plan(answer, budget, project_digest=digest)
            except ValueError as exc:
                self._emit_validation_failure("initial", exc)
                answer = self._ask(
                    root,
                    _initial_repair_prompt(answer, budget, exc),
                    phase="initial-repair",
                )
                plan = normalize_initial_plan(answer, budget, project_digest=digest)
            _write_json(plan_path, plan)
        if not budget_path.is_file():
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
        updated = {**plan, "scenes": [*plan["scenes"], *scenes]}
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
        "你是作品主创。给出能支撑目标篇幅的因果骨架和每章不同的戏剧转向。",
        "只返回一个 JSON 对象；不写任务回执、文件路径、ID、字数或模型说明。",
        "chapters 必须与下列章节预算顺序相同；first_window 只写第一章场景，数量精确匹配预算。",
        "用户若指定章序、结局所在章节或最终画面，必须原位保留；除非用户明确要求，不得在结局后追加尾声、第三方视角、续集钩子或新结局。",
        "场景字段：name, function, participants(人名数组), conflict, information_release, consequence, setup_payoff_role, rhythm_role, obligation。rhythm_role 只能填写 setup、escalation、climax、payoff、aftermath、bridge、transition 之一，不写说明句。",
        "返回字段：premise, central_question, ending_choice, volume_obligations(每卷一条), chapters(每章含 title, dramatic_turn, obligation, reader_question), first_window(场景数组), characters(主要人物数组), world_facts(稳定世界事实数组)。",
        "每个人物只写 name, role, importance(major/secondary/cameo), background, desire。只列全书重要人物；first_window 中所有有专名的 participants 必须逐字复用 characters 的 name，临时路人使用无专名角色称谓。不要编造不确定的世界事实，现实题材可返回空数组。用户明确指定的人物白名单、禁止新专名、现实解释等跨场景硬限制，必须逐条保存在 world_facts；不得只写进某一场景后丢失。",
        "全书采用一致的日期、年份和时间差口径；未知数值保持未知，不得为增强戏剧性另造相互冲突的时间版本。",
        "每章要有具体且不同的选择、代价或认知改变；禁止用重复事件撑字数。每场只分配一次不可替代的核心事件，function、participants、conflict、information_release、consequence 与 obligation 必须彼此一致；未列入 participants 的重要人物不得在该场提前登场或完成后续场景的职责。相邻场景不得重复首次见面、同一调取/发现/交付、同一问答或同一决定；需要回顾时只写已经造成的新压力，不重演事件。",
        "无关精确数字默认不用，先区分‘一个又一个’等虚指反复与精确计数。日期、年龄、编号、时长、距离、尺寸、次数、比例或读数若承担当场问答、谈判、身份或债务辨认、选择、因果、连续性或后文核验中的一项实际功能，即可按需要的精度规划；既定数值事实必须准确，不强求所有功能同时成立。普通动作、陈设和停顿用状态、范围或后果表达，不用计件、计次、计时制造伪真实感。",
        "相邻场景的功能变化应带来可感的节奏变化，除非因果上必须持续施压，不要连续使用相同 rhythm_role。快节奏来自信息、动作和选择的推进，不等于全篇使用短句。后续场景将按章滚动展开。",
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
        "target": {
            "scene_count": budget_row["scene_count"],
            "target_words": budget_row["target_words"],
        },
    }
    return "\n".join([
        "# 下一章场景窗口",
        "你是作品主创。承接既有后果，为当前章节设计具体场景。",
        "只返回 JSON 对象，字段 scenes 是场景数组；不要输出编号、字数、路径或任务协议。",
        "场景数量必须与目标一致，每场包含 name, function, participants(人名数组), conflict, information_release, consequence, setup_payoff_role, rhythm_role, obligation。rhythm_role 只能填写 setup、escalation、climax、payoff、aftermath、bridge、transition 之一。",
        "有专名的 participants 必须逐字复用 registered_characters；不得用同义姓名替换已登记人物，临时角色保持无专名。严格遵守 chapter_spine 的章序与 ending_choice 位置，除非用户明确要求，不追加尾声或续集钩子。",
        "沿用 world_facts 和既有后果中的日期、年份、数量与时间差；来源不确定时保持未知，不创建第二套时间口径。",
        "让场景因果相接，详略随章节转向变化；每场只承担一次核心事件，场景字段必须与 participants 对齐，未列入本场的主要人物不得提前登场或替后续场景完成首次见面、调取、发现、交付、问答或决定。相邻场景只承接后果，不重演同一事件；不要重复上一章的戏剧动作，也不要在功能已经改变时沿用上一场 rhythm_role。",
        "无关精确数字默认不用，‘一个又一个’等虚指反复不当作精确计数。日期、年龄、编号、时长、距离、尺寸、次数、比例或读数若承担当场问答、谈判、事实辨认、选择、因果、连续性或后文核验中的一项实际功能，即可保留必要精度；沿用既定数值事实，不强求当场有用的值日后再次兑现。普通动作、陈设和停顿改写为状态、范围或结果。快节奏仍需保留句群层次，收束、余波和关系变化应获得相应的呼吸空间。",
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
        "返修不得改动用户指定的章序、结局章节或最终画面，不得追加尾声或续集钩子；所有有专名的场景参与者必须复用 characters 中的姓名，并保持单一时间口径。用户明确指定的人物白名单、禁止新专名、现实解释等跨场景硬限制必须继续逐条保存在 world_facts。",
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
