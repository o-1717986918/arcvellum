"""Packaged project library views for the local frontend."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re

from .display_cleaner import (
    display_counts,
    file_label,
    list_from_yaml_text,
    markdown_to_display_text,
    nested_scalar_from_yaml_text,
    prose_body_for_display,
    read_json_file,
    read_jsonl_tail,
    scalar_from_yaml_text,
    summarize_text,
    truncate_text,
)
from .style_lab import active_project_style


PROJECT_LIBRARY_SCHEMA = "literary-engineering-workbench/project-library/v0.1"


def build_project_library(project_root: Path) -> dict[str, object]:
    """Build a human-facing, read-only project library snapshot."""

    root = project_root.resolve()
    if not root.exists():
        raise FileNotFoundError(f"project root not found: {root}")
    overrides = _load_overrides(root)
    drafts = _draft_items(root, overrides)
    sections = {
        "drafts": drafts,
        "characters": _character_items(root, overrides),
        "world": _world_items(root, overrides),
        "scenes": _scene_items(root, overrides),
        "branches": _branch_items(root, overrides),
        "style": _style_items(root, overrides),
        "reviews": _review_items(root, overrides),
        "word_budget": _word_budget_items(root, overrides),
        "rhythm": _rhythm_items(root, overrides),
        "canon_patches": _canon_patch_items(root, overrides),
    }
    sections = {key: [_with_key_points(item) for item in value] for key, value in sections.items()}
    counts = {key: len(value) for key, value in sections.items()}
    project = _project_card(root, overrides)
    return {
        "schema": PROJECT_LIBRARY_SCHEMA,
        "generated_at": _now(),
        "project_root": str(root),
        "project": project,
        "counts": counts,
        "sections": sections,
        "completed_prose": _completed_prose_summary(drafts),
        "recent_human_choices": read_jsonl_tail(root / "workflow" / "human_choices" / "index.jsonl", 8),
        "recent_user_notes": read_jsonl_tail(root / "workflow" / "user_notes" / "index.jsonl", 8),
        "rules": [
            "This library is display-only. It packages artifacts for users but does not promote candidates or advance routes.",
            "Draft bodies are cleaned with final-delivery rules before display and counting.",
            "Canon, character, prose, and release changes must still use candidate/review/approval or formal CLI routes.",
        ],
    }


def find_project_library_item(project_root: Path, kind: str, item_id: str) -> dict[str, object]:
    library = build_project_library(project_root)
    sections = library.get("sections") if isinstance(library.get("sections"), dict) else {}
    items = sections.get(kind, []) if isinstance(sections, dict) else []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and str(item.get("id") or "") == item_id:
                return {"ok": True, "kind": kind, "item": item, "library_generated_at": library.get("generated_at", "")}
    raise FileNotFoundError(f"library item not found: {kind}/{item_id}")


def _project_card(root: Path, overrides: dict[str, object]) -> dict[str, object]:
    text = _read_text(root / "project.yaml")
    title = nested_scalar_from_yaml_text(text, "project", "title") or scalar_from_yaml_text(text, "title") or root.name
    project_type = nested_scalar_from_yaml_text(text, "project", "type") or "novel"
    target = nested_scalar_from_yaml_text(text, "project", "target_length") or nested_scalar_from_yaml_text(text, "longform_budget", "target_words")
    premise = nested_scalar_from_yaml_text(text, "creative_brief", "premise")
    genre = nested_scalar_from_yaml_text(text, "creative_brief", "genre")
    item = {
        "kind": "project",
        "id": "project",
        "title": title,
        "subtitle": "项目总览",
        "path": "project.yaml" if (root / "project.yaml").exists() else "",
        "status": nested_scalar_from_yaml_text(text, "project", "status") or "unknown",
        "badges": [badge for badge in [project_type, genre, f"目标 {target} 字" if target else ""] if badge],
        "excerpt": premise or "还没有项目简介。",
        "facts": [
            {"label": "作品类型", "value": project_type},
            {"label": "目标长度", "value": target or "未设置"},
            {"label": "语言", "value": nested_scalar_from_yaml_text(text, "project", "language") or "zh-CN"},
        ],
    }
    return _apply_overrides(item, overrides)


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


def _character_items(root: Path, overrides: dict[str, object]) -> list[dict[str, object]]:
    folder = root / "characters"
    if not folder.exists():
        return []
    items = []
    for path in sorted(folder.glob("*.yaml"))[:200]:
        if path.name.startswith("_"):
            continue
        text = _read_text(path)
        character_id = scalar_from_yaml_text(text, "character_id") or path.stem
        name = scalar_from_yaml_text(text, "name") or file_label(path)
        importance = scalar_from_yaml_text(text, "importance") or "secondary"
        role = scalar_from_yaml_text(text, "role") or importance
        background = nested_scalar_from_yaml_text(text, "background_story", "summary")
        fear = _first_nested_list_item(text, "psychology", "fear")
        desire = _first_nested_list_item(text, "bdi", "desire")
        item = {
            "kind": "characters",
            "id": character_id,
            "title": name,
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


def _scene_items(root: Path, overrides: dict[str, object]) -> list[dict[str, object]]:
    folder = root / "scenes"
    if not folder.exists():
        return []
    items = []
    for path in sorted(folder.glob("*.yaml"))[:250]:
        text = _read_text(path)
        scene_id = scalar_from_yaml_text(text, "scene_id") or path.stem
        chapter_id = scalar_from_yaml_text(text, "chapter_id") or "未分章"
        goal = scalar_from_yaml_text(text, "scene_goal") or nested_scalar_from_yaml_text(text, "reader_experience", "reader_question")
        participants = list_from_yaml_text(text, "participants")
        target = scalar_from_yaml_text(text, "word_count_target") or "0"
        item = {
            "kind": "scenes",
            "id": scene_id,
            "title": _display_scene_name(scene_id),
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


def _branch_items(root: Path, overrides: dict[str, object]) -> list[dict[str, object]]:
    folder = root / "branches"
    if not folder.exists():
        return []
    items = []
    for manifest in sorted(folder.glob("*/branch_manifest.json"))[:250]:
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


def _review_items(root: Path, overrides: dict[str, object]) -> list[dict[str, object]]:
    folder = root / "reviews"
    if not folder.exists():
        return []
    paths = [path for path in folder.rglob("*") if path.is_file() and path.suffix.lower() in {".md", ".json"}]
    paths = sorted(paths, key=lambda path: path.stat().st_mtime, reverse=True)[:80]
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


def _word_budget_items(root: Path, overrides: dict[str, object]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    budget = root / "plot" / "word_budget" / "word_budget.json"
    if budget.exists():
        payload = read_json_file(budget)
        totals = payload.get("totals") if isinstance(payload.get("totals"), dict) else {}
        body = _display_text_for_path(root / "plot" / "word_budget" / "word_budget.md")
        item = {
            "kind": "word_budget",
            "id": "word_budget",
            "title": "长篇字数预算",
            "subtitle": "目标长度与剧情库存",
            "path": _rel(budget, root),
            "status": str(payload.get("status") or "unknown"),
            "badges": [str(payload.get("status") or "unknown"), f"{totals.get('chapter_count', 0)} 章", f"{totals.get('scene_count', 0)} 场"],
            "excerpt": summarize_text(body, limit=240) or "预算文件存在，但还没有可读报告。",
            "body": truncate_text(body, 3000),
            "facts": [
                {"label": "目标字数", "value": totals.get("target_words") or "未设置"},
                {"label": "章节数", "value": totals.get("chapter_count") or 0},
                {"label": "场景数", "value": totals.get("scene_count") or 0},
            ],
        }
        items.append(_apply_overrides(item, overrides))
    obligations = root / "plot" / "chapter_obligations"
    if obligations.exists():
        for path in sorted(obligations.glob("*.json"))[:80]:
            payload = read_json_file(path)
            if not payload:
                continue
            chapter_id = str(payload.get("chapter_id") or path.stem)
            item = {
                "kind": "word_budget",
                "id": f"chapter__{chapter_id}",
                "title": f"{chapter_id} 章节义务",
                "subtitle": "读者体验契约",
                "path": _rel(path, root),
                "status": str(payload.get("status") or "draft"),
                "badges": [str(payload.get("status") or "draft")],
                "excerpt": truncate_text(str(payload.get("chapter_function") or payload.get("ending_hook") or "章节义务等待平台 Agent 填写。"), 240),
                "facts": [
                    {"label": "章节功能", "value": payload.get("chapter_function") or "未填写"},
                    {"label": "章末钩子", "value": payload.get("ending_hook") or "未填写"},
                    {"label": "库存充分性", "value": payload.get("inventory_sufficiency") or "未填写"},
                ],
            }
            items.append(_apply_overrides(item, overrides))
    return items


def _rhythm_items(root: Path, overrides: dict[str, object]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for path in sorted((root / "drafts" / "compositions").glob("*_composition.json"))[:250]:
        payload = read_json_file(path)
        if not payload:
            continue
        scene_id = str(payload.get("scene_id") or path.stem.replace("_composition", ""))
        rhythm = payload.get("narrative_rhythm") if isinstance(payload.get("narrative_rhythm"), dict) else {}
        bridge = payload.get("scene_bridge") if isinstance(payload.get("scene_bridge"), dict) else {}
        contract = payload.get("narrative_rhythm_contract") if isinstance(payload.get("narrative_rhythm_contract"), dict) else {}
        item = {
            "kind": "rhythm",
            "id": scene_id,
            "title": f"{_display_scene_name(scene_id)} 的叙事节奏",
            "subtitle": "节奏与场景衔接",
            "path": _rel(path, root),
            "status": str(contract.get("status") or "composition"),
            "badges": [str(rhythm.get("rhythm_role") or "mixed"), str(rhythm.get("pace") or "balanced"), str(contract.get("source") or "composition")],
            "excerpt": str(rhythm.get("reader_effect") or rhythm.get("scene_turn") or bridge.get("outgoing_hook") or "这个场景还没有显式节奏转折说明。"),
            "facts": [
                {"label": "场景功能", "value": _display_list_value(rhythm.get("scene_function")) or rhythm.get("rhythm_role") or "未填写"},
                {"label": "节奏定位", "value": rhythm.get("pace") or "balanced"},
                {"label": "叙事密度", "value": rhythm.get("density") or "medium"},
                {"label": "本场转折", "value": rhythm.get("scene_turn") or "未填写"},
                {"label": "读者效果", "value": rhythm.get("reader_effect") or "未填写"},
                {"label": "叙述距离", "value": rhythm.get("narrative_distance") or "medium"},
                {"label": "入场压力", "value": bridge.get("incoming_pressure") or "未填写"},
                {"label": "承接上场", "value": _display_list_value(bridge.get("incoming_from_previous")) or _display_list_value(bridge.get("carryover_from_previous")) or "未填写"},
                {"label": "出场钩子", "value": _display_hooks(bridge.get("outgoing_hooks")) or bridge.get("outgoing_hook") or "未填写"},
            ],
        }
        items.append(_apply_overrides(item, overrides))
    if items:
        return items
    for path in sorted((root / "scenes").glob("*.yaml"))[:250]:
        text = _read_text(path)
        scene_id = scalar_from_yaml_text(text, "scene_id") or path.stem
        turn = nested_scalar_from_yaml_text(text, "narrative_rhythm", "scene_turn")
        hook = nested_scalar_from_yaml_text(text, "scene_bridge", "outgoing_hook")
        if not turn and not hook:
            continue
        item = {
            "kind": "rhythm",
            "id": scene_id,
            "title": f"{_display_scene_name(scene_id)} 的叙事节奏",
            "subtitle": "scene.yaml 节奏字段",
            "path": _rel(path, root),
            "status": "scene",
            "badges": ["scene.yaml"],
            "excerpt": turn or hook,
            "facts": [
                {"label": "本场转折", "value": turn or "未填写"},
                {"label": "出场钩子", "value": hook or "未填写"},
            ],
        }
        items.append(_apply_overrides(item, overrides))
    return items


def _canon_patch_items(root: Path, overrides: dict[str, object]) -> list[dict[str, object]]:
    folder = root / "canon" / "patches"
    if not folder.exists():
        return []
    items: list[dict[str, object]] = []
    for path in sorted(folder.glob("*_canon_patch.json"))[:250]:
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
    elif kind == "rhythm":
        for label in ["场景功能", "本场转折", "出场钩子", "入场压力"]:
            if fact_map.get(label) and fact_map[label] != "未填写":
                points.append(f"{label}：{fact_map[label]}")
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
