"""Formal character, world, scene, branch, style, and review projections."""

from __future__ import annotations

from pathlib import Path

from ...display_cleaner import (
    file_label,
    list_from_yaml_text,
    markdown_to_display_text,
    nested_scalar_from_yaml_text,
    read_json_file,
    scalar_from_yaml_text,
    summarize_text,
    truncate_text,
)
from .common import (
    _apply_overrides,
    _bounded_paths,
    _display_scene_name,
    _display_text_for_path,
    _first_heading,
    _first_nested_list_item,
    _read_text,
    _rel,
    _review_status,
    _safe_item_id,
    _selected_branch,
)
from ...style_lab import active_project_style

def _character_items(
    root: Path,
    overrides: dict[str, object],
    *,
    limit: int | None = 200,
) -> list[dict[str, object]]:
    folder = root / "characters"
    if not folder.exists():
        return []
    items = []
    for path in _bounded_paths(folder.glob("*.yaml"), limit):
        if path.name.startswith("_"):
            continue
        text = _read_text(path)
        character_id = scalar_from_yaml_text(text, "character_id") or path.stem
        name = scalar_from_yaml_text(text, "name") or file_label(path)
        aliases = list_from_yaml_text(text, "aliases", limit=32)
        importance = scalar_from_yaml_text(text, "importance") or "secondary"
        role = scalar_from_yaml_text(text, "role") or importance
        background = nested_scalar_from_yaml_text(text, "background_story", "summary")
        fear = _first_nested_list_item(text, "psychology", "fear")
        desire = _first_nested_list_item(text, "bdi", "desire")
        item = {
            "kind": "characters",
            "id": character_id,
            "title": name,
            "aliases": aliases,
            "importance": importance,
            "subtitle": role,
            "path": _rel(path, root),
            "status": "major" if importance == "major" else "supporting",
            "badges": [importance, role],
            "excerpt": background or desire or "还没有可展示的角色背景摘要。",
            "facts": [
                {"label": "重要性", "value": importance},
                {"label": "当前欲望", "value": desire or "未填写"},
                {"label": "主要恐惧", "value": fear or "未填写"},
                {"label": "背景故事", "value": background or "未填写"},
            ],
        }
        items.append(_apply_overrides(item, overrides))
    return items

def _world_items(root: Path, overrides: dict[str, object]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for folder_name, label in [("canon", "世界规则"), ("plot", "情节资料")]:
        folder = root / folder_name
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".md", ".yaml", ".yml", ".json"}:
                continue
            if "candidates" in path.parts or path.name.endswith(".agent_tasks.md"):
                continue
            text = _display_text_for_path(path)
            if not text:
                continue
            item = {
                "kind": "world",
                "id": _safe_item_id(path, root),
                "title": _first_heading(_read_text(path)) or file_label(path),
                "subtitle": label,
                "path": _rel(path, root),
                "status": "formal",
                "badges": [label, path.suffix.lower().lstrip(".")],
                "excerpt": summarize_text(text, limit=220),
                "body": truncate_text(text, 3000),
                "facts": [{"label": "来源", "value": _rel(path, root)}],
            }
            items.append(_apply_overrides(item, overrides))
            if len(items) >= 80:
                return items
    return items

def _scene_items(
    root: Path,
    overrides: dict[str, object],
    *,
    limit: int | None = 250,
) -> list[dict[str, object]]:
    folder = root / "scenes"
    if not folder.exists():
        return []
    items = []
    for path in _bounded_paths(folder.glob("*.yaml"), limit):
        text = _read_text(path)
        scene_id = scalar_from_yaml_text(text, "scene_id") or path.stem
        chapter_id = scalar_from_yaml_text(text, "chapter_id") or "未分章"
        goal = scalar_from_yaml_text(text, "scene_goal") or nested_scalar_from_yaml_text(text, "reader_experience", "reader_question")
        participants = list_from_yaml_text(text, "participants", limit=32)
        participant_refs = list_from_yaml_text(text, "participant_refs", limit=32)
        target = scalar_from_yaml_text(text, "word_count_target") or "0"
        item = {
            "kind": "scenes",
            "id": scene_id,
            "title": _display_scene_name(scene_id),
            "participants": participants,
            "participant_refs": participant_refs,
            "subtitle": chapter_id,
            "path": _rel(path, root),
            "status": scalar_from_yaml_text(text, "status") or "planned",
            "badges": [chapter_id, f"目标 {target} 字" if target and target != "0" else "未绑定字数"],
            "excerpt": goal or "还没有场景目标。",
            "facts": [
                {"label": "章节", "value": chapter_id},
                {"label": "目标字数", "value": target if target != "0" else "未设置"},
                {"label": "参与者", "value": "、".join(participants) if participants else "未填写"},
                {"label": "读者问题", "value": nested_scalar_from_yaml_text(text, "reader_experience", "reader_question") or "未填写"},
                {"label": "承诺回报", "value": nested_scalar_from_yaml_text(text, "reader_experience", "promised_reward") or "未填写"},
            ],
        }
        items.append(_apply_overrides(item, overrides))
    return items

def _branch_items(root: Path, overrides: dict[str, object], *, limit: int | None = 250) -> list[dict[str, object]]:
    folder = root / "branches"
    if not folder.exists():
        return []
    items = []
    for manifest in _bounded_paths(folder.glob("*/branch_manifest.json"), limit):
        payload = read_json_file(manifest)
        scene_id = str(payload.get("scene_id") or manifest.parent.name)
        selection_path = manifest.parent / "branch_selection.md"
        selection_text = _read_text(selection_path)
        selected = _selected_branch(selection_text)
        options = []
        for branch in payload.get("branches", []) if isinstance(payload.get("branches"), list) else []:
            if not isinstance(branch, dict):
                continue
            branch_id = str(branch.get("branch_id") or branch.get("id") or "")
            title = str(branch.get("title") or branch_id or "未命名分支")
            premise = str(branch.get("premise") or branch.get("summary") or "")
            risks = branch.get("risks") if isinstance(branch.get("risks"), list) else []
            options.append(
                {
                    "id": branch_id,
                    "label": title,
                    "summary": truncate_text(premise, 180),
                    "risk": "；".join(str(item) for item in risks[:3]),
                    "selected": bool(branch_id and branch_id == selected),
                }
            )
        item = {
            "kind": "branches",
            "id": scene_id,
            "title": f"{_display_scene_name(scene_id)}的剧情分支",
            "subtitle": "推演分支",
            "path": _rel(manifest, root),
            "status": "selected" if selected else "waiting_user_choice",
            "badges": [f"{len(options)} 个候选", f"已选 {selected}" if selected else "等待选择"],
            "excerpt": f"推荐分支：{payload.get('recommended_branch') or '未给出'}。正式进入编剧态前必须完成分支选择。",
            "options": options,
            "facts": [
                {"label": "场景", "value": scene_id},
                {"label": "推荐分支", "value": payload.get("recommended_branch") or "未给出"},
                {"label": "当前选择", "value": selected or "未选择"},
            ],
        }
        items.append(_apply_overrides(item, overrides))
    return items

def _style_items(root: Path, overrides: dict[str, object]) -> list[dict[str, object]]:
    active = active_project_style(root)
    items = []
    if active.get("style_id"):
        readiness = active.get("readiness") if isinstance(active.get("readiness"), dict) else {}
        item = {
            "kind": "style",
            "id": str(active.get("style_id")),
            "title": str(active.get("style_id")),
            "subtitle": "当前挂载文风",
            "path": str(active.get("project_style") or "style/active_style_skill.json"),
            "status": "ready" if readiness.get("ready") else "needs_review",
            "badges": ["最高优先级", "可正式生成" if readiness.get("ready") else "需补齐评测"],
            "excerpt": "文风会在表达层先于普通生成约束生效。",
            "facts": [
                {"label": "优先级", "value": active.get("priority") or "highest"},
                {"label": "是否就绪", "value": "是" if readiness.get("ready") else "否"},
                {"label": "挂载文件", "value": active.get("project_style") or "style/active_style_skill.json"},
            ],
        }
        items.append(_apply_overrides(item, overrides))
    for prompt in sorted((root / "style").glob("**/style_prompt.md"))[:80]:
        text = _read_text(prompt)
        item = {
            "kind": "style",
            "id": _safe_item_id(prompt, root),
            "title": _first_heading(text) or file_label(prompt.parent),
            "subtitle": "文风提示词",
            "path": _rel(prompt, root),
            "status": "candidate",
            "badges": ["LLM-facing prompt", f"{len(markdown_to_display_text(text, limit=5000))} 字"],
            "excerpt": summarize_text(text, limit=240),
            "body": markdown_to_display_text(text, limit=2500),
            "facts": [{"label": "提示词文件", "value": _rel(prompt, root)}],
        }
        items.append(_apply_overrides(item, overrides))
    return items

def _review_items(
    root: Path,
    overrides: dict[str, object],
    *,
    limit: int | None = 80,
) -> list[dict[str, object]]:
    folder = root / "reviews"
    if not folder.exists():
        return []
    paths = [path for path in folder.rglob("*") if path.is_file() and path.suffix.lower() in {".md", ".json"}]
    paths = sorted(paths, key=lambda path: path.stat().st_mtime, reverse=True)
    if limit is not None:
        paths = paths[:max(0, int(limit))]
    items = []
    for path in paths:
        text = _display_text_for_path(path)
        status = _review_status(path, text)
        item = {
            "kind": "reviews",
            "id": _safe_item_id(path, root),
            "title": _first_heading(_read_text(path)) or file_label(path),
            "subtitle": "审查证据",
            "path": _rel(path, root),
            "status": status,
            "badges": [status, path.suffix.lower().lstrip(".")],
            "excerpt": summarize_text(text, limit=220),
            "body": truncate_text(text, 3000),
            "facts": [{"label": "审查文件", "value": _rel(path, root)}],
        }
        items.append(_apply_overrides(item, overrides))
    return items
