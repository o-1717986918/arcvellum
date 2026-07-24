"""Shared display and override primitives for read-only project-library projections."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re

from ...display_cleaner import (
    list_from_yaml_text,
    markdown_to_display_text,
    read_json_file,
    scalar_from_yaml_text,
    truncate_text,
)

PROJECT_LIBRARY_SCHEMA = "literary-engineering-workbench/project-library/v0.1"

def _load_overrides(root: Path) -> dict[str, object]:
    payload = read_json_file(root / "workflow" / "ui_overrides.json")
    items = payload.get("items") if isinstance(payload.get("items"), dict) else {}
    return items

def _apply_overrides(item: dict[str, object], overrides: dict[str, object]) -> dict[str, object]:
    key = f"{item.get('kind')}:{item.get('id')}"
    record = overrides.get(key) if isinstance(overrides, dict) else None
    if not isinstance(record, dict):
        return item
    fields = record.get("fields") if isinstance(record.get("fields"), dict) else {}
    if "display_title" in fields:
        item["title"] = str(fields["display_title"])
    if "display_summary" in fields:
        item["excerpt"] = str(fields["display_summary"])
    if "note" in fields:
        item["user_note"] = str(fields["note"])
    if "tags" in fields:
        tags = fields["tags"] if isinstance(fields["tags"], list) else [fields["tags"]]
        item["badges"] = list(item.get("badges", [])) + [str(tag) for tag in tags if str(tag).strip()]
    item["ui_overridden"] = True
    return item

def _with_key_points(item: dict[str, object]) -> dict[str, object]:
    """Attach concise creative-control points for the frontend reader."""

    points: list[str] = []
    kind = str(item.get("kind") or "")
    status = str(item.get("status") or "")
    facts = item.get("facts") if isinstance(item.get("facts"), list) else []
    fact_map = {
        str(fact.get("label") or ""): str(fact.get("value") or "")
        for fact in facts
        if isinstance(fact, dict) and str(fact.get("value") or "").strip()
    }
    if kind == "drafts":
        points.append(f"正文状态：{item.get('subtitle') or status}，后续引用时应以该版本口径为准。")
        if fact_map.get("目标字数") and fact_map["目标字数"] != "未设置":
            points.append(f"字数目标：{fact_map['目标字数']}，生成或修订时不能只写成摘要。")
    elif kind == "characters":
        for label in ["背景故事", "当前欲望", "主要恐惧"]:
            if fact_map.get(label) and fact_map[label] != "未填写":
                points.append(f"{label}：{fact_map[label]}")
    elif kind == "world":
        points.append("这是正式世界观/情节资料，新增设定不能与它冲突。")
    elif kind == "scenes":
        for label in ["读者问题", "承诺回报", "目标字数", "参与者"]:
            if fact_map.get(label) and fact_map[label] != "未填写":
                points.append(f"{label}：{fact_map[label]}")
    elif kind == "branches":
        for label in ["推荐分支", "当前选择"]:
            if fact_map.get(label) and fact_map[label] not in {"未给出", "未选择"}:
                points.append(f"{label}：{fact_map[label]}")
        if status == "waiting_user_choice":
            points.append("正式进入编剧态前必须选定分支，不能让平台 Agent 自行默认。")
    elif kind == "style":
        points.append("文风是表达层最高优先级，会影响正文生成、修订和审查。")
        if fact_map.get("是否就绪"):
            points.append(f"可用性：{fact_map['是否就绪']}")
    elif kind == "reviews":
        points.append(f"审查状态：{status}。未通过或 pass_with_notes 都应回到修订闭环。")
    elif kind == "word_budget":
        for label in ["目标字数", "章节数", "场景数", "库存充分性"]:
            value = fact_map.get(label)
            if value and value not in {"0", "未填写"}:
                points.append(f"{label}：{value}")
    elif kind == "story_architecture":
        for label in ["中心戏剧问题", "人物改变", "中点不可逆", "终局选择", "独立审查"]:
            if fact_map.get(label) and fact_map[label] != "未填写":
                points.append(f"{label}：{fact_map[label]}")
    elif kind == "rhythm":
        for label in ["场景功能", "本场转折", "出场钩子", "入场压力"]:
            if fact_map.get(label) and fact_map[label] != "未填写":
                points.append(f"{label}：{fact_map[label]}")
    elif kind == "continuity":
        for label in ["状态", "最近推进", "预期兑现", "正文证据"]:
            if fact_map.get(label) and fact_map[label] not in {"未记录", "未填写"}:
                points.append(f"{label}：{fact_map[label]}")
    elif kind == "decisions":
        for label in ["路线", "目标", "是否已物化"]:
            if fact_map.get(label) and fact_map[label] not in {"未指定", "未填写"}:
                points.append(f"{label}：{fact_map[label]}")
    elif kind == "context_health":
        points.append(f"来源校验：{status}。状态不是 pass 时必须先重建上下文，不能继续进入正式创作。")
        if fact_map.get("缺少必要上下文") and fact_map["缺少必要上下文"] != "无":
            points.append(f"缺少必要上下文：{fact_map['缺少必要上下文']}")
    elif kind == "canon_patches":
        points.append(f"Canon 变化：{fact_map.get('Canon 变化', status)}。未审批前只能作为候选。")
        if fact_map.get("候选条目"):
            points.append(f"待写回条目：{fact_map['候选条目']}")
    excerpt = str(item.get("excerpt") or "").strip()
    if excerpt and len(points) < 3:
        points.append(truncate_text(excerpt, 160))
    item["key_points"] = _unique_points(points)[:5]
    return item

def _unique_points(points: list[str]) -> list[str]:
    seen = set()
    result = []
    for point in points:
        text = truncate_text(str(point or "").strip(), 220)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result

def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")

def _display_text_for_path(path: Path) -> str:
    if not path.exists():
        return ""
    if path.suffix.lower() == ".json":
        payload = read_json_file(path)
        return _json_to_display_text(payload)
    return markdown_to_display_text(_read_text(path), limit=5000)

def _json_to_display_text(payload: dict[str, object]) -> str:
    if not payload:
        return ""
    lines = []
    for key, value in payload.items():
        if isinstance(value, (str, int, float, bool)):
            lines.append(f"{_label(key)}：{value}")
        elif isinstance(value, list):
            shown = "；".join(str(item) for item in value[:5] if not isinstance(item, (dict, list)))
            if shown:
                lines.append(f"{_label(key)}：{shown}")
        elif isinstance(value, dict):
            brief = "；".join(f"{_label(k)}={v}" for k, v in list(value.items())[:4] if isinstance(v, (str, int, float, bool)))
            if brief:
                lines.append(f"{_label(key)}：{brief}")
    return truncate_text("\n".join(lines), 5000)

def _label(value: str) -> str:
    return str(value).replace("_", " ").replace("-", " ")

def _first_heading(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return ""

def _display_scene_name(scene_id: str) -> str:
    return scene_id.replace("_", " ").replace("-", " ").strip() or "未命名场景"

def _first_nested_list_item(text: str, parent: str, key: str) -> str:
    parent_match = None
    for match in re.finditer(rf"(?m)^(\s*){parent}\s*:\s*$", text):
        parent_match = match
        break
    if not parent_match:
        return ""
    start = parent_match.end()
    block_lines = []
    for line in text[start:].splitlines():
        if line and not line.startswith(" ") and not line.startswith("\t"):
            break
        block_lines.append(line)
    return (list_from_yaml_text("\n".join(block_lines), key, limit=1) or [""])[0]

def _selected_branch(text: str) -> str:
    return scalar_from_yaml_text(text, "selected_branch")

def _review_status(path: Path, text: str) -> str:
    if path.suffix.lower() == ".json":
        payload = read_json_file(path)
        return str(payload.get("conclusion") or payload.get("status") or payload.get("final_recommendation") or "review")
    lowered = text.lower()
    if "conclusion: pass" in lowered or "结论：pass" in lowered or "结论: pass" in lowered:
        return "pass"
    if "pass_with_notes" in lowered:
        return "pass_with_notes"
    if "revise" in lowered or "修订" in text:
        return "revise"
    return "review"

def _metric_int(item: dict[str, object], key: str) -> int:
    metrics = item.get("metrics") if isinstance(item.get("metrics"), dict) else {}
    value = metrics.get(key) if isinstance(metrics, dict) else 0
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0

def _display_list_value(value: object) -> str:
    if isinstance(value, list):
        return "；".join(str(item) for item in value if str(item).strip())
    return str(value or "")

def _display_hooks(value: object) -> str:
    if not isinstance(value, list):
        return str(value or "")
    parts: list[str] = []
    for item in value:
        if isinstance(item, dict):
            hook_type = str(item.get("type") or "").strip()
            content = str(item.get("content") or item.get("summary") or "").strip()
            if hook_type and content:
                parts.append(f"{hook_type}: {content}")
            elif content:
                parts.append(content)
        else:
            text = str(item).strip()
            if text:
                parts.append(text)
    return "；".join(parts)

def _safe_item_id(path: Path, root: Path) -> str:
    return _rel(path, root).replace("/", "__").replace("\\", "__").replace(".", "_")

def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
