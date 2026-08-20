"""Summary and report projections for the long-form audit."""

from __future__ import annotations

from pathlib import Path

from .longform_analysis import summary_markdown_lines, viewpoint_label
from .longform_inventory import rel_str
from .longform_issue_analysis import foreshadow_status, to_int
from .longform_models import LongformIssue, LongformSceneRecord


def build_summary(
    scenes: list[LongformSceneRecord],
    characters: list[dict[str, str]],
    foreshadowing: list[dict[str, str]],
    chapter_files: list[Path],
    issues: list[LongformIssue],
    target_length: int,
    word_budget: dict[str, object],
) -> dict[str, object]:
    scene_counts = _scene_counts(scenes)
    totals = word_budget.get("totals", {}) if word_budget else {}
    totals = totals if isinstance(totals, dict) else {}
    return {
        "chapter_count": max(scene_counts["chapter_count"], len(chapter_files)),
        "scene_count": len(scenes),
        "character_count": len(characters),
        "location_count": scene_counts["location_count"],
        "foreshadowing_count": len(foreshadowing),
        "draft_chars": scene_counts["draft_chars"],
        "draft_chinese_chars": scene_counts["draft_chars"],
        "draft_machine_chars": scene_counts["draft_machine_chars"],
        "target_length": target_length,
        "ready_scene_count": scene_counts["ready_scene_count"],
        "blocked_scene_count": scene_counts["blocked_scene_count"],
        "rhythm_pass_count": scene_counts["rhythm_pass_count"],
        "rhythm_gap_count": scene_counts["rhythm_gap_count"],
        "issue_count": len(issues),
        "word_budget_status": str(word_budget.get("status") or "missing") if word_budget else "missing",
        "word_budget_scene_count": to_int(totals.get("scene_count")),
        "word_budget_chapter_count": to_int(totals.get("chapter_count")),
    }


def _scene_counts(scenes: list[LongformSceneRecord]) -> dict[str, int]:
    chapters: set[str] = set()
    locations: set[str] = set()
    counts = {
        "draft_chars": 0, "draft_machine_chars": 0,
        "ready_scene_count": 0, "rhythm_pass_count": 0, "rhythm_gap_count": 0,
    }
    for scene in scenes:
        if scene.chapter_id != "unassigned":
            chapters.add(scene.chapter_id)
        if scene.location:
            locations.add(scene.location)
        counts["draft_chars"] += scene.draft_chars
        counts["draft_machine_chars"] += scene.draft_machine_chars
        counts["ready_scene_count"] += int(scene.status == "ready")
        counts["rhythm_pass_count"] += int(scene.narrative_rhythm_status == "pass")
        counts["rhythm_gap_count"] += int(scene.narrative_rhythm_status in {"", "defaulted", "incomplete"})
    counts["chapter_count"] = len(chapters)
    counts["location_count"] = len(locations)
    counts["blocked_scene_count"] = len(scenes) - counts["ready_scene_count"]
    return counts


def render_markdown(root: Path, payload: dict[str, object], graph_path: Path) -> str:
    summary = payload["summary"]
    assert isinstance(summary, dict)
    lines = [
        "# 长篇项目审计报告", "",
        f"生成时间：{payload['generated_at']}",
        f"图谱文件：`{rel_str(graph_path, root)}`", "",
        *_overview_lines(summary),
        *_scene_matrix_lines(_dict_rows(payload.get("scenes"))),
        *_rhythm_matrix_lines(_dict_rows(payload.get("scenes"))),
        *_issue_lines(_dict_rows(payload.get("issues"))),
        *_foreshadowing_lines(_dict_rows(payload.get("foreshadowing"))),
        *_closing_lines(rel_str(graph_path, root)),
    ]
    return "\n".join(lines) + "\n"


def _overview_lines(summary: dict[str, object]) -> list[str]:
    return [
        "## 总览", "",
        f"- 章节数：{summary['chapter_count']}",
        f"- 场景数：{summary['scene_count']}",
        f"- 人物档案数：{summary['character_count']}",
        f"- 地点数：{summary['location_count']}",
        f"- 正文中文内容字符：{summary['draft_chars']} / 目标 {summary['target_length']}",
        f"- 机器非空白字符诊断：{summary.get('draft_machine_chars', 0)}",
        f"- 字数预算状态：{summary.get('word_budget_status', 'missing')} / 预算场景 {summary.get('word_budget_scene_count', 0)}",
        f"- 可装配场景：{summary['ready_scene_count']}",
        f"- 阻塞场景：{summary['blocked_scene_count']}",
        f"- 节奏契约通过场景：{summary.get('rhythm_pass_count', 0)}",
        f"- 节奏契约缺口场景：{summary.get('rhythm_gap_count', 0)}",
        *summary_markdown_lines(summary), "",
    ]


def _scene_matrix_lines(scenes: list[dict[str, object]]) -> list[str]:
    lines = [
        "## 场景状态矩阵", "",
        "| 章节 | 场景 | 地点 | 视角 | 参与者 | 正文中文内容字符 | 静态审查 | Agent审查 | 状态 |",
        "| --- | --- | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for scene in scenes:
        lines.append(
            "| {chapter} | {scene} | {location} | {viewpoint} | {participants} | {chars} | {review} | {agent_review} | {status} |".format(
                chapter=scene["chapter_id"], scene=scene["scene_id"],
                location=scene["location"] or "未填写", viewpoint=viewpoint_label(scene),
                participants="、".join(str(item) for item in scene["participants"]) or "未填写",
                chars=scene["draft_chars"], review=scene["review_conclusion"] or "missing",
                agent_review=f"{scene.get('agent_review_conclusion') or 'missing'}/{scene.get('agent_review_schema_status') or 'missing'}",
                status=scene["status"],
            )
        )
    return [*lines, ""]


def _rhythm_matrix_lines(scenes: list[dict[str, object]]) -> list[str]:
    lines = ["## 叙事节奏与场景桥接矩阵", ""]
    if not scenes:
        return [*lines, "- 未发现场景。", ""]
    lines.extend(["| 章节 | 场景 | 节奏契约 | 场景功能 | 本场转折 | 入场压力 | 出场钩子 |", "| --- | --- | --- | --- | --- | --- | --- |"])
    for scene in scenes:
        lines.append(
            "| {chapter} | {scene} | {status} | {function} | {turn} | {incoming} | {outgoing} |".format(
                chapter=scene["chapter_id"], scene=scene["scene_id"],
                status=scene.get("narrative_rhythm_status") or "missing",
                function="、".join(str(item) for item in scene.get("scene_function") or []) or "未填写",
                turn=scene.get("scene_turn") or "未填写",
                incoming=scene.get("incoming_pressure") or "未填写",
                outgoing=scene.get("outgoing_hook") or "未填写",
            )
        )
    return [*lines, ""]


def _issue_lines(issues: list[dict[str, object]]) -> list[str]:
    lines = ["## 风险清单", ""]
    if not issues:
        return [*lines, "- 未发现阻塞性风险。", ""]
    lines.extend(["| 级别 | 类别 | 对象 | 问题 | 建议 |", "| --- | --- | --- | --- | --- |"])
    lines.extend(
        f"| {item['severity']} | {item['category']} | `{item['subject']}` | {item['message']} | {item['recommendation']} |"
        for item in issues
    )
    return [*lines, ""]


def _foreshadowing_lines(rows: list[dict[str, object]]) -> list[str]:
    lines = ["## 伏笔债务", ""]
    if not rows:
        return [*lines, "- 未登记伏笔。", ""]
    lines.extend(["| 伏笔 | 设置场景 | 预期回收 | 实际回收 | 状态 |", "| --- | --- | --- | --- | --- |"])
    for row in rows:
        string_row = {str(key): str(value or "") for key, value in row.items()}
        lines.append(
            "| {fid} | {setup} | {expected} | {actual} | {status} |".format(
                fid=string_row.get("foreshadow_id") or string_row.get("id") or "unknown",
                setup=string_row.get("setup_scene") or "",
                expected=string_row.get("expected_payoff") or string_row.get("expected_payoff_range") or "",
                actual=string_row.get("actual_payoff_scene") or string_row.get("payoff_scene") or "",
                status=foreshadow_status(string_row),
            )
        )
    return [*lines, ""]


def _closing_lines(graph_relative: str) -> list[str]:
    return [
        "## 图谱导出", "", f"- 图谱 JSON：`{graph_relative}`",
        "- 当前是轻量 JSON 图谱，可后续导入 Neo4j 或由 LlamaIndex 图检索层消费。", "",
        "## 下一步", "",
        "- 先处理 `high` 风险，再扩大章节生成规模。",
        "- 每章运行 `chapter-workspace`，再运行本审计。",
        "- 对开放伏笔补齐预期回收范围。",
        "- 人物档案缺失时，先补人物 BDI，再继续正文扩写。",
    ]


def _dict_rows(value: object) -> list[dict[str, object]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


__all__ = ["build_summary", "render_markdown"]
