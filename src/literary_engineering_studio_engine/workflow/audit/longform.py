"""Longform-planning evidence gates."""
from __future__ import annotations

from pathlib import Path

from ...agent_tasks import agent_task_completion_status
from ...literary.planning.review import planning_review_pass_status
from ...route_audit_common import _add_gate, _project_target_words
def _add_longform_budget_gates(gates: list[dict[str, str]], root: Path, *, force: bool) -> None:
    target_words = _project_target_words(root)
    if not force and target_words < 100000:
        return
    budget_json = root / "plot" / "word_budget" / "word_budget.json"
    prefix = "longform" if force else "longform-required"
    _add_gate(
        gates,
        f"{prefix}:word-budget-json",
        budget_json.exists(),
        "blocking",
        "word budget JSON exists",
        "目标达到中长篇规模或正在执行 longform-planning；先运行 word-budget / longform-budget，不能直接批量写正文。",
    )
    if not budget_json.exists():
        return

    _add_budget_review_gates(gates, root, prefix)
    _add_chapter_obligation_gates(gates, root, prefix)
    _add_scene_inventory_gates(gates, root, prefix)


def _add_budget_review_gates(gates: list[dict[str, str]], root: Path, prefix: str) -> None:
    budget_task = root / "plot" / "word_budget" / "word_budget.agent_tasks.md"
    candidate = root / "plot" / "candidates" / "outlines" / "word_budget_expansion.md"

    budget_review_pass, budget_review_message = planning_review_pass_status(root, "budget")
    _add_gate(
        gates,
        f"{prefix}:word-budget-review",
        budget_review_pass,
        "blocking",
        "word-budget independent review passes",
        budget_review_message,
    )
    budget_completion = agent_task_completion_status(budget_task, root=root)
    _add_gate(
        gates,
        f"{prefix}:budgeted-outline-candidate",
        candidate.exists(),
        "blocking",
        "budgeted outline candidate exists",
        "平台 Agent 需完成独立的预算化大纲候选，不能只保留数字预算。",
    )
    _add_gate(
        gates,
        f"{prefix}:word-budget-task-complete",
        budget_completion.get("complete") is True,
        "blocking",
        "word-budget platform-agent task completed",
        f"word_budget.agent_tasks.md 未完成：{budget_completion.get('message')}",
    )


def _add_chapter_obligation_gates(gates: list[dict[str, str]], root: Path, prefix: str) -> None:
    obligation_task = root / "plot" / "chapter_obligations" / "chapter_obligations.agent_tasks.md"
    obligation_plan = root / "plot" / "candidates" / "chapters" / "chapter_obligation_plan.md"
    _add_gate(
        gates,
        f"{prefix}:chapter-obligation-task",
        obligation_task.exists(),
        "blocking",
        "chapter obligation planning task exists",
        "word-budget 后必须生成 plot/chapter_obligations/chapter_obligations.agent_tasks.md，用于把数字预算转成章节承诺和读者体验契约。",
    )
    obligation_completion = agent_task_completion_status(obligation_task, root=root)
    _add_gate(
        gates,
        f"{prefix}:chapter-obligation-task-complete",
        obligation_completion.get("complete") is True,
        "blocking",
        "chapter obligation planning task completed",
        f"chapter_obligations.agent_tasks.md 未完成：{obligation_completion.get('message')}",
    )
    obligation_review_pass, obligation_review_message = planning_review_pass_status(root, "chapter_obligation")
    _add_gate(
        gates,
        f"{prefix}:chapter-obligation-review",
        obligation_review_pass,
        "blocking",
        "chapter obligation independent review passes",
        obligation_review_message,
    )
    _add_gate(gates, f"{prefix}:chapter-obligation-plan", obligation_plan.exists(), "blocking", "chapter obligation plan candidate exists", "章节义务候选缺失。")


def _add_scene_inventory_gates(gates: list[dict[str, str]], root: Path, prefix: str) -> None:
    scene_task = root / "plot" / "word_budget" / "scene_inventory_expansion.agent_tasks.md"
    scene_plan = root / "plot" / "candidates" / "scenes" / "word_budget_scene_inventory.md"
    _add_gate(gates, f"{prefix}:scene-inventory-expansion", scene_plan.exists(), "blocking", "scene inventory expansion candidate exists", "平台 Agent 需完成全书场景库存候选。")
    scene_review_pass, scene_review_message = planning_review_pass_status(root, "scene_inventory")
    _add_gate(gates, f"{prefix}:scene-inventory-review", scene_review_pass, "blocking", "scene inventory independent review passes", scene_review_message)
    scene_completion = agent_task_completion_status(scene_task, root=root)
    _add_gate(
        gates,
        f"{prefix}:scene-inventory-task-complete",
        scene_completion.get("complete") is True,
        "blocking",
        "scene inventory platform-agent task completed",
        f"scene_inventory_expansion.agent_tasks.md 未完成：{scene_completion.get('message')}",
    )
