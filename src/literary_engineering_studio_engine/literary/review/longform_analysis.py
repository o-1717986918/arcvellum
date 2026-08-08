"""Macro literary analysis projections consumed by the long-form audit."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import re
from typing import Any, Iterable

from ..planning.rhythm_plan import load_rhythm_plan
from .longform_contract import audit_continuity_ledgers, longform_issue_is_blocking


def collect_expanded_evidence(
    root: Path,
    scenes: list[Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, str]]]:
    rhythm_plan = load_rhythm_plan(root)
    curves = rhythm_plan.get("chapters") if isinstance(rhythm_plan.get("chapters"), dict) else {}
    continuity = audit_continuity_ledgers(
        root,
        (scene.scene_id for scene in scenes if scene.status == "ready"),
    )
    findings = [
        *macro_rhythm_issues(rhythm_plan, scenes),
        *viewpoint_issues(scenes),
        *(item for item in continuity.get("issues", []) if isinstance(item, dict)),
    ]
    return rhythm_plan, curves, continuity, findings


def macro_rhythm_issues(rhythm_plan: dict[str, Any], scenes: list[Any]) -> list[dict[str, str]]:
    scene_chapters = {scene.scene_id: scene.chapter_id for scene in scenes}
    issues: list[dict[str, str]] = []
    volumes = rhythm_plan.get("volumes") if isinstance(rhythm_plan.get("volumes"), dict) else {}
    for volume_id, curve in volumes.items():
        if not isinstance(curve, dict):
            continue
        issues.extend(_cross_chapter_curve_issues(str(volume_id), curve, scene_chapters))
    book = rhythm_plan.get("book") if isinstance(rhythm_plan.get("book"), dict) else {}
    macro = book.get("macro") if isinstance(book.get("macro"), dict) else {}
    issues.extend(_rhythm_issue("book", item) for item in macro.get("issues", []) if isinstance(item, dict))
    return issues


def viewpoint_issues(scenes: list[Any]) -> list[dict[str, str]]:
    configured = [scene for scene in scenes if scene.viewpoint]
    if not configured:
        return []
    issues: list[dict[str, str]] = []
    missing = [scene.scene_id for scene in scenes if not scene.viewpoint]
    if missing:
        issues.append(_issue("scenes/", f"作品已启用显式视角合同，但 {len(missing)} 个场景未声明 viewpoint。", "为缺失场景补齐 viewpoint；全知或客观镜头也应显式命名，避免无计划跳转。"))
    issues.extend(item for scene in configured if (item := _invalid_viewpoint_issue(scene)) is not None)
    return issues


def extended_summary(
    scenes: list[Any],
    issues: Iterable[Any],
    rhythm_plan: dict[str, Any],
    continuity: dict[str, Any],
) -> dict[str, Any]:
    curves = rhythm_plan.get("chapters") if isinstance(rhythm_plan.get("chapters"), dict) else {}
    volumes = rhythm_plan.get("volumes") if isinstance(rhythm_plan.get("volumes"), dict) else {}
    book = rhythm_plan.get("book") if isinstance(rhythm_plan.get("book"), dict) else {}
    rows = list(issues)
    blocking = sum(1 for item in rows if longform_issue_is_blocking(asdict(item)))
    distribution = _viewpoint_distribution(scenes)
    collections = continuity.get("collections") if isinstance(continuity.get("collections"), dict) else {}
    return {
        "blocking_issue_count": blocking,
        "attention_issue_count": len(rows) - blocking,
        "rhythm_curve_pass_count": _status_count(curves, "pass"),
        "rhythm_curve_attention_count": len(curves) - _status_count(curves, "pass"),
        "volume_rhythm_attention_count": len(volumes) - _status_count(volumes, "pass"),
        "book_rhythm_status": str(book.get("status") or "missing"),
        "viewpoint_configured_count": sum(distribution.values()),
        "viewpoint_distribution": distribution,
        "open_reader_question_count": _ledger_count(collections, "reader_questions", "open_count"),
        "open_promise_count": _ledger_count(collections, "promises", "open_count"),
        "overdue_continuity_count": _ledger_count(collections, "reader_questions", "overdue_count")
        + _ledger_count(collections, "promises", "overdue_count"),
    }


def summary_markdown_lines(summary: dict[str, Any]) -> list[str]:
    return [
        f"- 全书节奏状态：{summary.get('book_rhythm_status', 'missing')}",
        f"- 开放读者问题 / 承诺：{summary.get('open_reader_question_count', 0)} / {summary.get('open_promise_count', 0)}",
        f"- 逾期连续性债务：{summary.get('overdue_continuity_count', 0)}",
        f"- 问题数：{summary['issue_count']}（确定性阻塞 {summary.get('blocking_issue_count', 0)}）",
    ]


def _cross_chapter_curve_issues(
    volume_id: str,
    curve: dict[str, Any],
    scene_chapters: dict[str, str],
) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for item in curve.get("issues", []):
        if not isinstance(item, dict):
            continue
        chapters = {scene_chapters.get(str(scene_id), "") for scene_id in item.get("scene_ids", [])}
        if len({chapter for chapter in chapters if chapter}) >= 2:
            results.append(_rhythm_issue(f"volume:{volume_id}", item))
    return results


def _rhythm_issue(subject: str, item: dict[str, Any]) -> dict[str, str]:
    blocking = item.get("severity") == "blocking"
    return {
        "severity": "high" if blocking else "medium",
        "category": "macro_rhythm" if blocking else "macro_rhythm_attention",
        "subject": subject,
        "message": str(item.get("message") or "宏观叙事节奏需要复核。"),
        "recommendation": "回到 rhythm-plan 和场景库存调整全书/分卷起伏、重点场与呼吸间隔；不要用局部修辞掩盖宏观平坦。",
    }


def _invalid_viewpoint_issue(scene: Any) -> dict[str, str] | None:
    neutral = {"authorial", "external", "objective", "omniscient", "全知", "客观", "旁观"}
    if not scene.participants or scene.viewpoint in scene.participants or scene.viewpoint.lower() in neutral:
        return None
    return _issue(
        scene.scene_id,
        f"视角 `{scene.viewpoint}` 不在本场 participants 中，也不是已声明的非人物视角。",
        "统一人物 ID/姓名，或把该场明确标记为 omniscient/objective 等非人物视角。",
    )


def _issue(subject: str, message: str, recommendation: str) -> dict[str, str]:
    return {
        "severity": "medium",
        "category": "viewpoint_continuity",
        "subject": subject,
        "message": message,
        "recommendation": recommendation,
    }


def _viewpoint_distribution(scenes: Iterable[Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for scene in scenes:
        if scene.viewpoint:
            result[scene.viewpoint] = result.get(scene.viewpoint, 0) + 1
    return result


def _status_count(curves: dict[str, Any], expected: str) -> int:
    return sum(1 for curve in curves.values() if isinstance(curve, dict) and curve.get("status") == expected)


def _ledger_count(collections: dict[str, Any], collection: str, key: str) -> int:
    payload = collections.get(collection) if isinstance(collections.get(collection), dict) else {}
    try:
        return int(payload.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def scene_identity(text: str, path: Path) -> tuple[str, str, str, str]:
    return (
        _scalar(text, "scene_id") or path.stem,
        _scalar(text, "volume_id") or _scalar(text, "volume") or "unassigned",
        _scalar(text, "chapter_id") or "unassigned",
        _scalar(text, "viewpoint") or _scalar(text, "pov"),
    )


def viewpoint_label(scene: dict[str, object]) -> str:
    return str(scene.get("viewpoint") or "未声明")


def _scalar(text: str, key: str) -> str:
    match = re.search(rf"(?m)^[ \t]*{re.escape(key)}:[ \t]*(.*?)[ \t]*$", text)
    return match.group(1).strip().strip("\"'") if match else ""


__all__ = [
    "collect_expanded_evidence",
    "extended_summary",
    "scene_identity",
    "summary_markdown_lines",
    "viewpoint_label",
]
