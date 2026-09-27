"""Bounded top-level access to the existing lean planning service."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .action_receipts import action_receipt
from .formal_output_state import has_unmigrated_formal_work


def planning_prepare_action(
    prepare: Callable[[Path], dict[str, Any]],
    autopilot: Any,
    invalidate_project: Callable[[Path, str], Any] | None,
) -> Callable[[Path, Mapping[str, Any]], Mapping[str, Any]]:
    def execute(root: Path, _arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        if has_unmigrated_formal_work(root):
            raise ValueError("历史正式正文尚未转换为轻事务回执；请先完成作品迁移，不能直接按轻内核规划。")
        status = autopilot.status(root)
        run = status.get("run") if isinstance(status.get("run"), dict) else {}
        if run.get("status") == "running":
            raise ValueError("作品正在自动创作；请先暂停，再单独准备规划。")
        policy = autopilot.policy(root).get("policy", {})
        if policy.get("literary_kernel") != "lean-v2":
            if run:
                raise ValueError("已有旧内核运行；请先处理该运行，再切换为 lean-v2 规划。")
            autopilot.migrate_kernel(root, target_kernel="lean-v2")
        plan = prepare(root)
        if invalidate_project is not None:
            invalidate_project(root, "project-agent-planning-prepare")
        value = {
            "ok": True,
            "operation": "planning_prepare",
            "status": "prepared",
            "chapter_count": len(plan["chapters"]),
            "scene_ids": [scene["scene_id"] for scene in plan["scenes"]],
            "autopilot_started": False,
        }
        return {**value, "receipt": action_receipt("planning_prepare", value)}

    return execute


__all__ = ["planning_prepare_action"]
