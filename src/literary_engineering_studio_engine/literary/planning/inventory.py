"""Scene and outline inventory inspection for word-budget planning."""

from __future__ import annotations

from pathlib import Path
import re

from ...draft_text import (
    count_delivery_chars,
    count_delivery_chinese_content_chars,
    final_body_from_draft_path,
)
from .common import _read, _rel, _scalar, _to_int

def _scene_inventory_binding(root: Path, chapter_budgets: list[dict[str, object]]) -> dict[str, object]:
    scenes = _scan_scene_files(root)
    by_chapter: dict[str, list[dict[str, object]]] = {}
    for scene in scenes:
        by_chapter.setdefault(str(scene["chapter_id"]), []).append(scene)
    rows = []
    for chapter in chapter_budgets:
        chapter_id = str(chapter["chapter_id"])
        expected_scenes = int(chapter["scene_count"])
        target_words = int(chapter["target_words"])
        actual = by_chapter.get(chapter_id, [])
        actual_scene_count = len(actual)
        actual_chars = sum(int(scene["draft_chinese_chars"]) for scene in actual)
        actual_machine_chars = sum(int(scene["draft_machine_chars"]) for scene in actual)
        missing_scene_count = max(expected_scenes - actual_scene_count, 0)
        word_shortfall = max(target_words - actual_chars, 0)
        if missing_scene_count:
            status = "missing_scenes"
        elif word_shortfall > max(target_words * 0.2, int(chapter.get("avg_scene_words", 0))):
            status = "word_shortfall"
        else:
            status = "ok"
        rows.append(
            {
                "chapter_id": chapter_id,
                "volume_id": chapter["volume_id"],
                "target_words": target_words,
                "target_scene_count": expected_scenes,
                "avg_scene_words": chapter["avg_scene_words"],
                "actual_scene_count": actual_scene_count,
                "actual_draft_chars": actual_chars,
                "actual_draft_chinese_chars": actual_chars,
                "actual_draft_machine_chars": actual_machine_chars,
                "missing_scene_count": missing_scene_count,
                "word_shortfall": word_shortfall,
                "status": status,
                "scene_ids": [scene["scene_id"] for scene in actual],
            }
        )
    return {
        "chapter_rows": rows,
        "underbuilt_chapter_count": sum(1 for row in rows if row["status"] != "ok"),
        "missing_scene_count": sum(int(row["missing_scene_count"]) for row in rows),
        "word_shortfall": sum(int(row["word_shortfall"]) for row in rows),
        "actual_scene_count": len(scenes),
        "actual_draft_chars": sum(int(scene["draft_chars"]) for scene in scenes),
        "actual_draft_chinese_chars": sum(int(scene["draft_chinese_chars"]) for scene in scenes),
        "actual_draft_machine_chars": sum(int(scene["draft_machine_chars"]) for scene in scenes),
    }

def _scan_scene_files(root: Path) -> list[dict[str, object]]:
    scene_dir = root / "scenes"
    if not scene_dir.exists():
        return []
    rows = []
    for path in sorted(scene_dir.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        text = _read(path)
        scene_id = _scalar(text, "scene_id") or path.stem
        chapter_id = _scalar(text, "chapter_id") or "unassigned"
        draft_path = root / "drafts" / "scenes" / f"{scene_id}.md"
        body = final_body_from_draft_path(draft_path) if draft_path.exists() else ""
        rows.append(
            {
                "scene_id": scene_id,
                "chapter_id": chapter_id,
                "scene_path": _rel(path, root),
                "draft_path": _rel(draft_path, root) if draft_path.exists() else "",
                "draft_chars": count_delivery_chinese_content_chars(body),
                "draft_chinese_chars": count_delivery_chinese_content_chars(body),
                "draft_machine_chars": count_delivery_chars(body),
            }
        )
    return rows

def _chapter_budget_row(payload: dict[str, object], chapter_id: str) -> dict[str, object]:
    binding = payload.get("scene_inventory_binding") if isinstance(payload.get("scene_inventory_binding"), dict) else {}
    rows = binding.get("chapter_rows") if isinstance(binding, dict) else []
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and str(row.get("chapter_id") or "") == chapter_id:
                return row
    rows = payload.get("chapter_budgets")
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and str(row.get("chapter_id") or "") == chapter_id:
                return row
    return {}

def _scene_ids_for_chapter(root: Path, chapter_id: str) -> list[str]:
    scene_dir = root / "scenes"
    if not scene_dir.exists():
        return []
    ids = []
    for path in sorted(scene_dir.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        text = _read(path)
        if (_scalar(text, "chapter_id") or "unassigned") != chapter_id:
            continue
        ids.append(_scalar(text, "scene_id") or path.stem)
    return ids

def _scene_word_count_target(scene_text: str) -> int:
    """Read explicit per-scene word target aliases from scene YAML."""

    for key in ("word_count_target", "target_words", "word_target"):
        value = _to_int(_scalar(scene_text, key))
        if value > 0:
            return value
    return 0

def _budget_issues(totals: dict[str, int], inventory: dict[str, int | str], scene_inventory_binding: dict[str, object]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    planned_chapters = int(inventory.get("planned_chapter_count", 0))
    planned_scenes = int(inventory.get("planned_scene_count", 0))
    required_chapters = totals["chapter_count"]
    required_scenes = totals["scene_count"]
    if planned_chapters and planned_chapters < required_chapters * 0.75:
        issues.append(
            {
                "severity": "medium",
                "category": "chapter_inventory",
                "message": f"现有章节库存约 {planned_chapters}，低于预算章节 {required_chapters} 的 75%。",
                "recommendation": "扩展卷章结构，增加可承载场景的章节，不要用章节摘要替代场景。",
            }
        )
    elif not planned_chapters:
        issues.append(
            {
                "severity": "medium",
                "category": "chapter_inventory",
                "message": f"未检测到明确章节库存，预算需要约 {required_chapters} 章。",
                "recommendation": "先生成预算化章节候选，再进入场景开发。",
            }
        )
    if planned_scenes and planned_scenes < required_scenes * 0.75:
        issues.append(
            {
                "severity": "high",
                "category": "scene_inventory",
                "message": f"现有场景库存约 {planned_scenes}，低于预算场景 {required_scenes} 的 75%。",
                "recommendation": "按主线、关系线、信息释放、行动后果和节奏调节补足场景库存。",
            }
        )
    elif not planned_scenes:
        issues.append(
            {
                "severity": "high",
                "category": "scene_inventory",
                "message": f"未检测到明确场景库存，预算需要约 {required_scenes} 个场景。",
                "recommendation": "先拆出卷-章-场景级候选，不要直接生成正文。",
            }
        )
    missing_scene_count = int(scene_inventory_binding.get("missing_scene_count", 0) or 0)
    word_shortfall = int(scene_inventory_binding.get("word_shortfall", 0) or 0)
    underbuilt_chapters = int(scene_inventory_binding.get("underbuilt_chapter_count", 0) or 0)
    if underbuilt_chapters:
        issues.append(
            {
                "severity": "high" if missing_scene_count else "medium",
                "category": "chapter_scene_binding",
                "message": f"预算绑定显示 {underbuilt_chapters} 个章节存在场景或正文缺口，缺失场景 {missing_scene_count} 个，正文缺口约 {word_shortfall} 字。",
                "recommendation": "处理 scene_inventory_expansion.agent_tasks.md，为欠账章节补足有因果功能的候选场景。",
            }
        )
    return issues

def _outline_inventory(root: Path, outline_path: Path) -> dict[str, int | str]:
    text = _read(outline_path)
    scene_files = [path for path in (root / "scenes").glob("*.yaml") if not path.name.startswith("_")] if (root / "scenes").exists() else []
    scene_chapters = {
        _scalar(_read(path), "chapter_id")
        for path in scene_files
        if _scalar(_read(path), "chapter_id")
    }
    volume_count = len(re.findall(r"(?im)^(?:#{1,6}\s*)?(?:第[一二三四五六七八九十百\d]+卷|volume\s+\d+|卷\s*[一二三四五六七八九十百\d]+)", text))
    chapter_count = len(re.findall(r"(?im)^(?:#{1,6}\s*)?(?:第[一二三四五六七八九十百\d]+章|chapter\s+\d+|chapter_\d+)", text))
    scene_markers = len(re.findall(r"(?im)^(?:#{1,6}\s*)?(?:场景\s*[一二三四五六七八九十百\d]+|scene[_\s-]?\d+)", text))
    return {
        "outline_path": _rel(outline_path, root) if outline_path.exists() else "",
        "planned_volume_count": volume_count,
        "planned_chapter_count": max(chapter_count, len(scene_chapters)),
        "scene_file_chapter_count": len(scene_chapters),
        "outline_scene_markers": scene_markers,
        "scene_file_count": len(scene_files),
        "planned_scene_count": max(scene_markers, len(scene_files)),
    }
