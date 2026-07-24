"""Draft and completed-prose projections for the project library."""

from __future__ import annotations

from pathlib import Path

from ...display_cleaner import display_counts, prose_body_for_display, summarize_text
from .common import (
    _apply_overrides,
    _display_scene_name,
    _first_heading,
    _metric_int,
    _read_text,
    _rel,
    _safe_item_id,
)
from ...display_cleaner import scalar_from_yaml_text

def _draft_items(root: Path, overrides: dict[str, object]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for folder, status, label in [
        (root / "drafts" / "scenes", "promoted", "已晋升正文"),
        (root / "drafts" / "candidates", "candidate", "候选正文"),
        (root / "drafts" / "revisions", "revision", "修订候选"),
        (root / "drafts" / "chapters", "chapter", "章节合稿"),
    ]:
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.md"))[:200]:
            if _is_placeholder_artifact(path):
                continue
            items.append(_draft_item_from_path(root, overrides, path, status=status, label=label))
    for folder, status, label in [
        (root / "exports", "exported", "正式导出正文"),
        (root / "releases", "published", "正式发布正文"),
    ]:
        if not folder.exists():
            continue
        paths = sorted(folder.glob("**/*_novel.md"), key=lambda path: path.stat().st_mtime, reverse=True)
        for path in paths[:80]:
            if _is_placeholder_artifact(path):
                continue
            item_id = f"{status}__{_safe_item_id(path, root)}"
            items.append(_draft_item_from_path(root, overrides, path, status=status, label=label, item_id=item_id))
    return items

def _is_placeholder_artifact(path: Path) -> bool:
    """Exclude directory instructions from reader-facing draft views."""

    name = path.name.lower()
    if name in {"readme.md", "readme.txt", "placeholder.md", "placeholder.txt"}:
        return True
    stem = path.stem.lower()
    return stem in {"readme", "placeholder", "_placeholder"}

def _draft_item_from_path(
    root: Path,
    overrides: dict[str, object],
    path: Path,
    *,
    status: str,
    label: str,
    item_id: str = "",
) -> dict[str, object]:
    text = _read_text(path)
    # Library SSE is a browsing projection. Full formal prose is loaded on
    # demand through Reader Manifest, so keep draft previews bounded here.
    body = prose_body_for_display(text, limit=2400)
    scene_id = _scene_id_from_draft(path)
    target = _scene_target(root, scene_id)
    title = _first_heading(text) or _display_scene_name(scene_id)
    counts = display_counts(body, target=target)
    item = {
        "kind": "drafts",
        "id": item_id or f"{status}__{path.stem}",
        "title": title,
        "subtitle": label,
        "path": _rel(path, root),
        "status": status,
        "badges": [label, f"{counts['chinese_content_chars']} 字"],
        "excerpt": summarize_text(body, limit=220) or "正文为空或只有工程说明。",
        "body": body,
        "reader_facing": not _is_placeholder_artifact(path),
        "metrics": counts,
        "facts": [
            {"label": "正文口径", "value": "已过滤工程痕迹"},
            {"label": "完成类型", "value": label},
            {"label": "目标字数", "value": target or "未设置"},
            {"label": "机器字符", "value": counts["machine_nonspace_chars"]},
        ],
    }
    return _apply_overrides(item, overrides)

def _completed_prose_summary(draft_items: list[dict[str, object]]) -> dict[str, object]:
    completed_statuses = {"promoted", "chapter", "exported", "published"}
    priority = {"published": 0, "exported": 1, "chapter": 2, "promoted": 3}
    items = [
        item
        for item in draft_items
        if str(item.get("status") or "") in completed_statuses
        and item.get("reader_facing", True)
        and (item.get("body") or item.get("excerpt"))
    ]
    items.sort(key=lambda item: (priority.get(str(item.get("status") or ""), 9), str(item.get("path") or "")))
    promoted_items = [item for item in items if item.get("status") == "promoted"]
    total_source = promoted_items or items
    total_chinese = sum(_metric_int(item, "chinese_content_chars") for item in total_source)
    total_machine = sum(_metric_int(item, "machine_nonspace_chars") for item in total_source)
    return {
        "status": "available" if items else "empty",
        "title": "已完成正文",
        "count": len(items),
        "total_chinese_content_chars": total_chinese,
        "total_machine_nonspace_chars": total_machine,
        "items": items[:12],
        "source_note": "优先展示已发布/已导出正文；没有发布包时展示已晋升场景正文。",
    }

def _scene_id_from_draft(path: Path) -> str:
    stem = path.stem
    if "-platform-agent" in stem:
        return stem.split("-platform-agent", 1)[0]
    if "_revision" in stem:
        return stem.split("_revision", 1)[0]
    return stem

def _scene_target(root: Path, scene_id: str) -> int:
    scene_path = root / "scenes" / f"{scene_id}.yaml"
    text = _read_text(scene_path)
    value = scalar_from_yaml_text(text, "word_count_target")
    try:
        return int(value or 0)
    except ValueError:
        return 0
