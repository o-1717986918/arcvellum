"""Longform-planning evidence gates."""
from __future__ import annotations

from pathlib import Path

from ...agent_tasks import agent_task_completion_status
from ...route_audit_common import _add_gate, _project_target_words, _read_json
def _add_longform_budget_gates(gates: list[dict[str, str]], root: Path, *, force: bool) -> None:
    target_words = _project_target_words(root)
    if not force and target_words < 100000:
        return
    budget_json = root / "plot" / "word_budget" / "word_budget.json"
    budget_task = root / "plot" / "word_budget" / "word_budget.agent_tasks.md"
    scene_task = root / "plot" / "word_budget" / "scene_inventory_expansion.agent_tasks.md"
    obligation_task = root / "plot" / "chapter_obligations" / "chapter_obligations.agent_tasks.md"
    review = root / "reviews" / "word_budget" / "word_budget_review.md"
    obligation_review = root / "reviews" / "word_budget" / "chapter_obligation_review.md"
    candidate = root / "plot" / "candidates" / "outlines" / "word_budget_expansion.md"
    scene_plan = root / "plot" / "candidates" / "scenes" / "word_budget_scene_inventory.md"
    scene_review = root / "reviews" / "word_budget" / "scene_inventory_review.md"

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

    payload = _read_json(budget_json)
    status = str(payload.get("status") or "").strip().lower()
    _add_gate(
        gates,
        f"{prefix}:word-budget-review",
        review.exists(),
        "blocking",
        "word-budget platform review exists",
        "平台 Agent 必须写 reviews/word_budget/word_budget_review.md，确认字数-剧情库存映射后才能进入批量场景开发。",
    )
    budget_completion = agent_task_completion_status(budget_task, root=root)
    _add_gate(
        gates,
        f"{prefix}:word-budget-task-complete",
        budget_completion.get("complete") is True,
        "blocking",
        "word-budget platform-agent task completed",
        f"word_budget.agent_tasks.md 未完成：{budget_completion.get('message')}",
    )
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
    _add_gate(
        gates,
        f"{prefix}:chapter-obligation-review",
        obligation_review.exists(),
        "blocking",
        "chapter obligation review exists",
        "平台 Agent 必须写 reviews/word_budget/chapter_obligation_review.md，确认每章承诺、兑现/延迟和读者问题后才能批量生成。",
    )
    if status == "needs_expansion":
        _add_gate(gates, f"{prefix}:budgeted-outline-candidate", candidate.exists(), "blocking", "budgeted outline candidate exists", "预算显示剧情库存不足；平台 Agent 需处理 word_budget.agent_tasks.md。")
        _add_gate(gates, f"{prefix}:scene-inventory-expansion", scene_plan.exists(), "blocking", "scene inventory expansion candidate exists", "预算显示场景库存不足；平台 Agent 需处理 scene_inventory_expansion.agent_tasks.md。")
        _add_gate(gates, f"{prefix}:scene-inventory-review", scene_review.exists(), "blocking", "scene inventory review exists", "扩展场景库存后，平台 Agent 需写 reviews/word_budget/scene_inventory_review.md。")
        scene_completion = agent_task_completion_status(scene_task, root=root)
        _add_gate(
            gates,
            f"{prefix}:scene-inventory-task-complete",
            scene_completion.get("complete") is True,
            "blocking",
            "scene inventory platform-agent task completed",
            f"scene_inventory_expansion.agent_tasks.md 未完成：{scene_completion.get('message')}",
        )
