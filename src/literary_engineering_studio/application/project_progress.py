"""Formal, read-only project progress projection for the Studio surface."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


PROGRESS_SCHEMA = "arcvellum/project-progress/v1"


def build_project_progress(
    dashboard: dict[str, Any],
    library: dict[str, Any],
    reader: dict[str, Any],
) -> dict[str, Any]:
    """Summarize real preparation, formal prose and route evidence.

    This is deliberately a projection: it never advances a route and does not infer
    progress from candidate prose. A missing word target produces an honest
    ``waiting_calibration`` result instead of an invented percentage.
    """

    sections = library.get("sections") if isinstance(library.get("sections"), dict) else {}
    project = library.get("project") if isinstance(library.get("project"), dict) else {}
    counts = library.get("counts") if isinstance(library.get("counts"), dict) else {}
    target = _target_words(project)
    formal_chars = _integer(reader.get("total_chinese_content_chars"))
    preparation_checks = _preparation_checks(project, sections, counts, target)
    preparation = _ratio(preparation_checks)
    manuscript = min(1.0, formal_chars / target) if target > 0 else None
    integrity_checks = _integrity_checks(dashboard, reader)
    integrity = _ratio(integrity_checks)
    overall = None if manuscript is None else round((preparation * 30 + manuscript * 60 + integrity * 10), 1)
    sources = {
        "dashboard": _digest(dashboard),
        "library": _digest(library),
        "reader": _digest(reader),
    }
    return {
        "ok": True,
        "schema": PROGRESS_SCHEMA,
        "status": "calibrated" if manuscript is not None else "waiting_calibration",
        "overall_percent": overall,
        "target_chinese_content_chars": target,
        "formal_chinese_content_chars": formal_chars,
        "parts": [
            {
                "id": "preparation",
                "label": "创作准备",
                "weight": 30,
                "percent": round(preparation * 100, 1),
                "checks": preparation_checks,
            },
            {
                "id": "manuscript",
                "label": "已晋升正文",
                "weight": 60,
                "percent": round(manuscript * 100, 1) if manuscript is not None else None,
                "actual": formal_chars,
                "target": target or None,
                "message": "只统计通过正式晋升的正文汉字与标点字符。",
            },
            {
                "id": "integrity",
                "label": "交付完整度",
                "weight": 10,
                "percent": round(integrity * 100, 1),
                "checks": integrity_checks,
            },
        ],
        "source_revisions": sources,
        "revision": _digest({"sources": sources, "overall": overall, "target": target, "formal": formal_chars}),
    }


def _preparation_checks(
    project: dict[str, Any],
    sections: dict[str, Any],
    counts: dict[str, Any],
    target: int,
) -> list[dict[str, Any]]:
    excerpt = str(project.get("excerpt") or "").strip()
    return [
        _check("direction", "创作方向", bool(excerpt and "还没有" not in excerpt)),
        _check("canon", "世界与 Canon", _count(counts, "world") > 0),
        _check("characters", "人物资产", _count(counts, "characters") > 0),
        _check("style", "文风挂载", _count(counts, "style") > 0),
        _check("scene_inventory", "场景库存", _count(counts, "scenes") > 0),
        _check("word_budget", "字数预算", _count(counts, "word_budget") > 0 and target > 0),
        _check("rhythm", "节奏计划", _count(counts, "rhythm") > 0),
    ]


def _integrity_checks(dashboard: dict[str, Any], reader: dict[str, Any]) -> list[dict[str, Any]]:
    audits = dashboard.get("route_audits") if isinstance(dashboard.get("route_audits"), list) else []
    audit_rows = [item for item in audits if isinstance(item, dict)]
    all_clear = bool(audit_rows) and all(_integer(item.get("blocking_count")) == 0 for item in audit_rows)
    review = next((item for item in audit_rows if str(item.get("route")) == "review-and-audit"), {})
    scene = next((item for item in audit_rows if str(item.get("route")) == "scene-development"), {})
    pending = _integer((dashboard.get("summary") or {}).get("pending_task_count")) if isinstance(dashboard.get("summary"), dict) else 0
    warnings = reader.get("warnings") if isinstance(reader.get("warnings"), list) else []
    return [
        _check("route_gates", "路线门禁", all_clear),
        _check("review", "审查闭环", isinstance(review, dict) and _integer(review.get("blocking_count")) == 0),
        _check("state", "场景状态写回", isinstance(scene, dict) and _integer(scene.get("blocking_count")) == 0),
        _check("reader", "正式正文可读", not warnings),
        _check("sidecars", "待处理任务收束", pending == 0),
    ]


def _target_words(project: dict[str, Any]) -> int:
    facts = project.get("facts") if isinstance(project.get("facts"), list) else []
    for item in facts:
        if not isinstance(item, dict) or str(item.get("label") or "") not in {"目标长度", "目标字数"}:
            continue
        raw = str(item.get("value") or "")
        match = re.search(r"\d[\d,]*", raw)
        if match:
            value = int(match.group(0).replace(",", ""))
            return value * 10_000 if "万" in raw else value
    return 0


def _check(identifier: str, label: str, complete: bool) -> dict[str, Any]:
    return {"id": identifier, "label": label, "complete": complete}


def _ratio(checks: list[dict[str, Any]]) -> float:
    return sum(1 for item in checks if item.get("complete") is True) / max(1, len(checks))


def _count(values: dict[str, Any], key: str) -> int:
    return _integer(values.get(key))


def _integer(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _digest(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]
