"""Continuity, human-decision, context-health, and Canon patch projections."""

from __future__ import annotations

from pathlib import Path

from literary_engineering_studio_engine.literary.scene.context.broker import context_trace_status
from literary_engineering_studio_engine.foundation.display_cleaner import read_json_file, summarize_text, truncate_text
from .common import (
    _apply_overrides,
    _bounded_paths,
    _display_list_value,
    _display_scene_name,
    _display_text_for_path,
    _json_to_display_text,
    _rel,
)

def _continuity_items(root: Path, overrides: dict[str, object]) -> list[dict[str, object]]:
    """Expose applied reader-question and promise/payoff ledgers as read-only records."""

    projection_path = root / "workflow" / "continuity" / "current.json"
    projection = read_json_file(projection_path)
    return [
        *_ledger_continuity_items(root, overrides),
        *_projected_continuity_items(projection_path, projection, overrides),
        *_identity_conflict_items(projection_path, projection, overrides),
    ]


def _ledger_continuity_items(
    root: Path, overrides: dict[str, object],
) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    sources = [
        (root / "plot" / "reader_questions" / "ledger.json", "reader_questions", "读者问题账本", "reader_questions"),
        (root / "plot" / "promises" / "ledger.json", "promises", "承诺与兑现账本", "promises"),
    ]
    for path, collection, title, kind in sources:
        payload = read_json_file(path)
        values = payload.get(collection) if isinstance(payload.get(collection), list) else []
        for index, value in enumerate(values[:160], start=1):
            if not isinstance(value, dict):
                continue
            item = _ledger_continuity_item(root, path, title, kind, index, value)
            items.append(_apply_overrides(item, overrides))
    return items


def _ledger_continuity_item(root, path, title, kind, index, value) -> dict[str, object]:
    record_id = str(_first_value(value, ("id", "question_id", "promise_id"), f"{kind}_{index}"))
    status = str(value.get("status") or "open")
    content = str(_first_value(value, ("content", "summary", "question", "promise"), "尚未提供可读内容。"))
    return {
        "kind": "continuity",
        "id": f"{kind}__{record_id}",
        "title": content,
        "subtitle": title,
        "path": _rel(path, root),
        "status": status,
        "badges": ["读者问题" if kind == "reader_questions" else "承诺/兑现", status],
        "excerpt": content,
        "facts": [
            {"label": "状态", "value": status},
            {"label": "首次出现", "value": _first_value(value, ("introduced_at", "created_at"), "未记录")},
            {"label": "最近推进", "value": value.get("last_advanced_at") or "未记录"},
            {"label": "预期兑现", "value": _first_value(value, ("due_window", "target_window"), "未记录")},
            {"label": "正文证据", "value": _display_list_value(value.get("evidence")) or "未记录"},
        ],
    }


def _first_value(value, keys, fallback):
    for key in keys:
        if result := value.get(key):
            return result
    return fallback


def _projected_continuity_items(
    projection_path: Path,
    projection: dict[str, object],
    overrides: dict[str, object],
) -> list[dict[str, object]]:
    projected = projection.get("entries") if isinstance(projection.get("entries"), list) else []
    labels = {
        "character_change": "人物状态变化",
        "canon_candidate": "Canon 候选",
        "continuity_change": "连续性变化",
        "promise_update": "承诺推进",
        "reader_question_update": "读者问题推进",
        "new_asset_candidate": "新资产身份候选",
    }
    open_kinds = {"promise_update", "reader_question_update", "new_asset_candidate"}
    items: list[dict[str, object]] = []
    for index, value in enumerate(projected[:240], start=1):
        if not isinstance(value, dict):
            continue
        kind = str(value.get("kind") or "continuity_change")
        summary = str(value.get("summary") or "尚未提供可读内容。")
        status = "open" if kind in open_kinds else "recorded"
        item = {
            "kind": "continuity",
            "continuity_kind": kind,
            "id": str(value.get("entry_id") or f"scene_delta_{index}"),
            "title": summary,
            "subtitle": labels.get(kind, "场景提交变化"),
            "path": _rel(projection_path, root),
            "status": status,
            "badges": [labels.get(kind, kind), status],
            "excerpt": summary,
            "facts": [
                {"label": "目标", "value": value.get("target_ref") or "未记录"},
                {"label": "来源场景", "value": value.get("scene_id") or "未记录"},
                {"label": "证据", "value": value.get("evidence") or "未记录"},
            ],
        }
        items.append(_apply_overrides(item, overrides))
    return items


def _identity_conflict_items(
    projection_path: Path,
    projection: dict[str, object],
    overrides: dict[str, object],
) -> list[dict[str, object]]:
    conflicts = projection.get("identity_conflicts") if isinstance(projection.get("identity_conflicts"), list) else []
    items: list[dict[str, object]] = []
    for index, value in enumerate(conflicts[:80], start=1):
        if not isinstance(value, dict):
            continue
        target = str(value.get("target_ref") or "未命名身份")
        item = {
            "kind": "continuity",
            "continuity_kind": "identity_conflict",
            "id": f"identity_conflict_{index}",
            "title": f"{target} 存在身份描述冲突",
            "subtitle": "身份连续性待消歧",
            "path": _rel(projection_path, root),
            "status": "needs_identity_resolution",
            "badges": ["身份冲突", "需消歧"],
            "excerpt": _display_list_value(value.get("summaries")) or "同一身份引用出现了多个描述。",
            "facts": [
                {"label": "身份引用", "value": target},
                {"label": "涉及场景", "value": _display_list_value(value.get("scene_ids")) or "未记录"},
            ],
        }
        items.append(_apply_overrides(item, overrides))
    return items

def _decision_items(root: Path, overrides: dict[str, object]) -> list[dict[str, object]]:
    """Render recorded human decisions, including state and Canon approvals, for the archive."""

    folder = root / "workflow" / "human_choices"
    if not folder.exists():
        return []
    paths = sorted(
        (path for path in folder.glob("*.json") if path.name != "index.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )[:120]
    items: list[dict[str, object]] = []
    for path in paths:
        payload = read_json_file(path)
        if not payload:
            continue
        decision_type = str(payload.get("decision_type") or "project decision")
        target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
        selected = str(payload.get("selected") or "未记录选择")
        item = {
            "kind": "decisions",
            "id": str(payload.get("choice_id") or path.stem),
            "title": selected,
            "subtitle": decision_type.replace("_", " "),
            "path": _rel(path, root),
            "status": str(payload.get("status") or "recorded"),
            "badges": [decision_type.replace("_", " "), str(payload.get("status") or "recorded")],
            "excerpt": str(payload.get("rationale") or payload.get("formal_effect") or "这项选择等待正式路线消费。"),
            "facts": [
                {"label": "路线", "value": payload.get("route") or "未指定"},
                {"label": "目标", "value": target.get("scene_id") or target.get("candidate_id") or target.get("path") or "未指定"},
                {"label": "是否已物化", "value": "是" if payload.get("consumed") else "否"},
                {"label": "记录时间", "value": payload.get("recorded_at") or "未记录"},
            ],
        }
        items.append(_apply_overrides(item, overrides))
    return items

def _context_health_items(root: Path, overrides: dict[str, object]) -> list[dict[str, object]]:
    """Make stale context visible without exposing internal trace JSON syntax."""

    folder = root / "memory" / "context_packets"
    if not folder.exists():
        return []
    items: list[dict[str, object]] = []
    for path in sorted(folder.glob("*.trace.json"))[:250]:
        scene_id = path.name.removesuffix(".trace.json")
        result = context_trace_status(root, scene_id, folder / f"{scene_id}.md")
        payload = result.payload
        item = {
            "kind": "context_health",
            "id": scene_id,
            "title": f"{_display_scene_name(scene_id)} 的上下文来源",
            "subtitle": "上下文新鲜度",
            "path": _rel(path, root),
            "status": result.status,
            "badges": [result.status, f"{len(payload.get('loaded_sources') or [])} 个来源"],
            "excerpt": result.message,
            "facts": [
                {"label": "场景", "value": scene_id},
                {"label": "来源文件", "value": len(payload.get("loaded_sources") or [])},
                {"label": "缺少必要上下文", "value": _display_list_value(payload.get("missing_required_context")) or "无"},
                {"label": "生成时间", "value": payload.get("created_at") or "未记录"},
            ],
        }
        items.append(_apply_overrides(item, overrides))
    return items

def _canon_patch_items(
    root: Path,
    overrides: dict[str, object],
    *,
    limit: int | None = 250,
) -> list[dict[str, object]]:
    folder = root / "canon" / "patches"
    if not folder.exists():
        return []
    items: list[dict[str, object]] = []
    for path in _bounded_paths(folder.glob("*_canon_patch.json"), limit):
        payload = read_json_file(path)
        if not payload:
            continue
        scene_id = str(payload.get("scene_id") or path.stem.replace("_canon_patch", ""))
        change = payload.get("canon_change", "unknown")
        patch_items = payload.get("items") if isinstance(payload.get("items"), list) else []
        report = path.with_suffix(".md")
        body = _display_text_for_path(report) or _json_to_display_text(payload)
        item = {
            "kind": "canon_patches",
            "id": scene_id,
            "title": f"{_display_scene_name(scene_id)} 的世界观写回候选",
            "subtitle": "Canon 写回候选",
            "path": _rel(path, root),
            "status": str(change),
            "badges": ["有持续事实" if change is True else "无持续事实" if change is False else "待判断", f"{len(patch_items)} 条候选"],
            "excerpt": str(payload.get("no_canon_change_reason") or summarize_text(body, limit=220) or "等待平台 Agent 判断是否需要写回世界观。"),
            "body": truncate_text(body, 3000),
            "facts": [
                {"label": "Canon 变化", "value": change},
                {"label": "候选条目", "value": len(patch_items)},
                {"label": "是否已应用", "value": "是" if payload.get("applied") else "否"},
                {"label": "来源正文", "value": payload.get("source") or "未填写"},
            ],
        }
        items.append(_apply_overrides(item, overrides))
    return items
