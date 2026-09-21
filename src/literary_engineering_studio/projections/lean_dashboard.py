"""Read-only workbench status for projects using the lean literary kernel."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_lean_dashboard(project_root: Path) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    plan = _read_json(root / "plot" / "lean_project_plan.json")
    budget = _read_json(root / "plot" / "word_budget" / "word_budget.json")
    totals = budget.get("totals") if isinstance(budget.get("totals"), dict) else {}
    target_scenes = int(totals.get("scene_count") or 0)
    planned = bool(plan.get("chapters") and plan.get("scenes"))
    scenes = sorted((root / "scenes").glob("scene_*.yaml"))
    committed = sum(
        (root / "workflow" / "scene_commits" / f"{path.stem}.json").is_file()
        for path in scenes
    )
    release = _read_json(root / "releases" / "whole-book" / "release_manifest.json")
    delivered = release.get("status") == "released"
    stages = (
        ("longform-planning", planned, "等待作品规划与首章场景"),
        ("scene-development", bool(target_scenes) and committed == target_scenes, f"已提交 {committed}/{target_scenes or len(scenes)} 场"),
        ("review-and-audit", delivered, "全书完整性在交付时统一核验"),
        ("export-and-release", delivered, "等待正式交付文件"),
    )
    audits = [
        {
            "route": route,
            "status": "ready" if ready else "pending",
            "blocking_count": 0 if ready else 1,
            "pending_task_count": 0,
            "top_blocking_gates": [] if ready else [{"message": message}],
        }
        for route, ready, message in stages
    ]
    next_action = _next_action(planned, delivered, committed, len(scenes))
    summary = {
        "route_count": len(audits),
        "blocking_count": sum(row["blocking_count"] for row in audits),
        "pending_task_count": 0,
        "formal_scene_count": len(scenes),
        "target_scene_count": target_scenes,
        "committed_scene_count": committed,
        "literary_kernel": "lean-v2",
    }
    dashboard = {
        "schema": "arcvellum/lean-workflow-dashboard/v1",
        "summary": summary,
        "route_audits": audits,
        "next_actions": [{"title": next_action, "message": next_action}],
        "recent_events": [],
        "rules": [],
    }
    return {
        "ok": True,
        "project_root": str(root),
        "dashboard": dashboard,
        **dashboard,
        "paths": {},
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _next_action(planned: bool, delivered: bool, committed: int, scenes: int) -> str:
    if not planned:
        return "先确定作品方向并生成章级规划"
    if delivered:
        return "作品已交付"
    if committed < scenes:
        return "继续创作并提交下一场正文"
    return "检查并生成全书交付"


__all__ = ["build_lean_dashboard"]
