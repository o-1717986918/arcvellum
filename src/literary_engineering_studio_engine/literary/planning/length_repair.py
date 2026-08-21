"""Deterministic repair allocation for a formal whole-work length shortfall."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from ...foundation.display_cleaner import scalar_from_yaml_text
from ...foundation.draft_text import (
    count_delivery_chinese_content_chars,
    final_body_from_draft_path,
)
from .contracts import scene_word_budget_contract
from .delivery_length import delivery_length_status


TARGET_LENGTH_REPAIR_SCHEMA = "arcvellum/target-length-repair/v1"


@dataclass(frozen=True)
class TargetLengthRepairResult:
    json_path: Path
    markdown_path: Path
    shortfall_chinese_chars: int
    allocated_chinese_chars: int
    scene_count: int
    status: str


def build_target_length_repair_plan(
    project_root: Path,
    *,
    output: Path | None = None,
    markdown_output: Path | None = None,
) -> TargetLengthRepairResult:
    root = project_root.resolve()
    progress = delivery_length_status(root)
    if progress.target_chinese_chars <= 0:
        raise RuntimeError("target-length repair requires a formal word-budget target")
    if not progress.inventory_complete:
        raise RuntimeError("target-length repair requires a complete planned scene inventory")
    json_path = _resolve(root, output, "reviews/longform/target_length_repair.json")
    markdown_path = _resolve(root, markdown_output, "reviews/longform/target_length_repair.md")
    allocations = _allocate(root, progress.shortfall_chinese_chars)
    allocated = sum(int(item["required_growth_chars"]) for item in allocations)
    status = "resolved" if progress.met else (
        "ready" if allocated == progress.shortfall_chinese_chars else "insufficient_capacity"
    )
    payload = {
        "schema": TARGET_LENGTH_REPAIR_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "source_snapshot": _source_snapshot(root),
        "delivery_length": progress.as_dict(),
        "allocated_chinese_chars": allocated,
        "unallocated_chinese_chars": max(progress.shortfall_chinese_chars - allocated, 0),
        "allocations": allocations,
        "creative_contract": {
            "goal": "Meet the explicit whole-work Chinese-content target through meaningful scene development.",
            "required": [
                "Add causal action, relationship pressure, information release, consequence, or earned aftermath.",
                "Preserve current canon, viewpoint, scene turn, outgoing hook, style mount, and punctuation contract.",
                "Re-run exact-candidate AgentReview, promotion, static review, state, canon, and continuity gates.",
            ],
            "forbidden": [
                "Do not pad with repeated emotion, redundant scenery, paraphrased recap, or cosmetic dialogue.",
                "Do not change formal canon or character assets from a prose repair task.",
                "Do not satisfy the project target by counting Markdown or workflow traces.",
            ],
        },
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(_render_markdown(payload), encoding="utf-8")
    return TargetLengthRepairResult(
        json_path=json_path,
        markdown_path=markdown_path,
        shortfall_chinese_chars=progress.shortfall_chinese_chars,
        allocated_chinese_chars=allocated,
        scene_count=len(allocations),
        status=status,
    )


def target_length_repair_status(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    progress = delivery_length_status(root)
    path = root / "reviews" / "longform" / "target_length_repair.json"
    payload = _read_json(path)
    allocations = payload.get("allocations")
    allocations = allocations if isinstance(allocations, list) else []
    source = payload.get("source_snapshot") if isinstance(payload.get("source_snapshot"), dict) else {}
    plan_current = bool(payload) and str(source.get("budget_sha256") or "") == _file_sha(
        root / "plot" / "word_budget" / "word_budget.json"
    )
    pending = _pending_allocations(root, allocations)
    recorded_status = str(payload.get("status") or "")
    status = _current_repair_status(
        met=progress.met,
        plan_current=plan_current,
        recorded_status=recorded_status,
        pending=bool(pending),
    )
    return {
        "path": path.relative_to(root).as_posix(),
        "exists": path.is_file(),
        "plan_current": plan_current,
        "delivery_length": progress.as_dict(),
        "pending_allocations": pending,
        "pending_scene_ids": [str(item.get("scene_id") or "") for item in pending],
        "status": status,
    }


def scene_length_repair_allocation(project_root: Path, scene_id: str) -> dict[str, Any]:
    status = target_length_repair_status(project_root)
    if status.get("status") != "pending":
        return {}
    for item in status["pending_allocations"]:
        if item.get("scene_id") == scene_id:
            return dict(item)
    return {}


def target_length_repair_pending(project_root: Path) -> bool:
    """Return whether a current plan requires formal scene rework."""

    status = target_length_repair_status(project_root)
    return bool(
        status.get("status") == "pending"
        and status.get("pending_scene_ids")
    )


def _allocate(root: Path, shortfall: int) -> list[dict[str, Any]]:
    if shortfall <= 0:
        return []
    candidates = _allocation_candidates(root)
    allocations, remaining = _preferred_allocations(candidates, shortfall)
    _allocate_remaining_capacity(candidates, allocations, remaining)
    return allocations


def _allocation_candidates(root: Path) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for path in sorted((root / "scenes").glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8")
        scene_id = scalar_from_yaml_text(text, "scene_id") or path.stem
        contract = scene_word_budget_contract(root, path, materialization_scope="scene")
        actual = _formal_scene_chars(root, scene_id)
        target = int(contract.get("target_chinese_chars") or 0)
        maximum = int(contract.get("max_chinese_chars") or target or actual)
        capacity = max(maximum - actual, 0)
        if capacity <= 0:
            continue
        candidates.append(
            {
                "scene_id": scene_id,
                "scene_path": path.relative_to(root).as_posix(),
                "chapter_id": scalar_from_yaml_text(text, "chapter_id") or "unassigned",
                "scene_function": scalar_from_yaml_text(text, "scene_function"),
                "current_scene_chars": actual,
                "target_scene_chars": target,
                "max_scene_chars": maximum,
                "target_deficit": max(target - actual, 0),
                "capacity": capacity,
            }
        )
    candidates.sort(
        key=lambda item: (
            int(item["target_deficit"]),
            int(item["capacity"]),
            str(item["scene_id"]),
        ),
        reverse=True,
    )
    return candidates


def _preferred_allocations(
    candidates: list[dict[str, Any]],
    shortfall: int,
) -> tuple[list[dict[str, Any]], int]:
    remaining = shortfall
    allocations: list[dict[str, Any]] = []
    for candidate in candidates:
        if remaining <= 0:
            break
        preferred = int(candidate["target_deficit"]) or int(candidate["capacity"])
        growth = min(remaining, preferred, int(candidate["capacity"]))
        if growth <= 0:
            continue
        allocations.append(_allocation_row(candidate, growth))
        remaining -= growth
    return allocations, remaining


def _allocate_remaining_capacity(
    candidates: list[dict[str, Any]],
    allocations: list[dict[str, Any]],
    remaining: int,
) -> None:
    by_scene = {str(item["scene_id"]): item for item in allocations}
    for candidate in candidates:
        if remaining <= 0:
            return
        existing = by_scene.get(str(candidate["scene_id"]))
        already = int(existing["required_growth_chars"]) if existing else 0
        growth = min(remaining, int(candidate["capacity"]) - already)
        if growth <= 0:
            continue
        if existing is None:
            existing = _allocation_row(candidate, 0)
            allocations.append(existing)
            by_scene[str(candidate["scene_id"])] = existing
        existing["required_growth_chars"] = already + growth
        existing["minimum_scene_chars"] = int(existing["current_scene_chars"]) + already + growth
        remaining -= growth


def _allocation_row(candidate: dict[str, Any], growth: int) -> dict[str, Any]:
    return {
        **candidate,
        "required_growth_chars": growth,
        "minimum_scene_chars": int(candidate["current_scene_chars"]) + growth,
        "repair_focus": "Add an earned beat that strengthens the existing scene function; do not append generic filler.",
    }


def _pending_allocations(
    root: Path,
    allocations: list[object],
) -> list[dict[str, Any]]:
    pending: list[dict[str, Any]] = []
    for item in allocations:
        if not isinstance(item, dict):
            continue
        scene_id = str(item.get("scene_id") or "")
        actual = _formal_scene_chars(root, scene_id)
        if actual < int(item.get("minimum_scene_chars") or 0):
            pending.append({**item, "actual_scene_chars": actual})
    return pending


def _current_repair_status(
    *,
    met: bool,
    plan_current: bool,
    recorded_status: str,
    pending: bool,
) -> str:
    if met:
        return "resolved"
    if plan_current and recorded_status == "insufficient_capacity":
        return "insufficient_capacity"
    if plan_current and pending:
        return "pending"
    return "missing_or_stale"


def _formal_scene_chars(root: Path, scene_id: str) -> int:
    path = root / "drafts" / "scenes" / f"{scene_id}.md"
    if not path.is_file():
        return 0
    return count_delivery_chinese_content_chars(final_body_from_draft_path(path))


def _source_snapshot(root: Path) -> dict[str, Any]:
    return {
        "budget_sha256": _file_sha(root / "plot" / "word_budget" / "word_budget.json"),
        "scene_drafts": {
            path.stem: _file_sha(path)
            for path in sorted((root / "drafts" / "scenes").glob("*.md"))
        },
    }


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _resolve(root: Path, value: Path | None, default: str) -> Path:
    if value is None:
        return root / default
    return value if value.is_absolute() else root / value


def _render_markdown(payload: dict[str, Any]) -> str:
    length = payload["delivery_length"]
    lines = [
        "# 全书目标长度修订计划",
        "",
        f"- 状态：`{payload['status']}`",
        f"- 正文中文内容字符：{length['actual_chinese_chars']} / {length['target_chinese_chars']}",
        f"- 缺口：{length['shortfall_chinese_chars']}",
        f"- 已分配：{payload['allocated_chinese_chars']}",
        "",
        "## 场景分配",
        "",
        "| 场景 | 当前 | 最低修订后 | 增量 | 上限 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for item in payload["allocations"]:
        lines.append(
            f"| {item['scene_id']} | {item['current_scene_chars']} | {item['minimum_scene_chars']} | "
            f"{item['required_growth_chars']} | {item['max_scene_chars']} |"
        )
    lines.extend(
        [
            "",
            "## 修订原则",
            "",
            "- 只增加有因果、关系、信息释放、行动后果或余波功能的内容。",
            "- 禁止复述、重复心理、空泛景物和对白注水。",
            "- 每个修订候选必须重新经过 AgentReview、晋升、静态审查与状态/连续性写回。",
        ]
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "TARGET_LENGTH_REPAIR_SCHEMA",
    "TargetLengthRepairResult",
    "build_target_length_repair_plan",
    "scene_length_repair_allocation",
    "target_length_repair_pending",
    "target_length_repair_status",
]
