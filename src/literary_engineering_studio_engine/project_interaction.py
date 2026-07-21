"""Frontend-safe project notes, display edits, and human choices."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path

from .display_cleaner import read_json_file, read_jsonl_tail, truncate_text
from .approval import record_workflow_approval
from .release_fingerprint import release_candidate_fingerprint
from .workflow_dashboard import build_workflow_dashboard
from .workflow_state import build_workflow_state, next_scene_workflow_state


UI_OVERRIDES_SCHEMA = "literary-engineering-workbench/ui-overrides/v0.1"
USER_NOTE_SCHEMA = "literary-engineering-workbench/user-note/v0.1"
HUMAN_CHOICE_SCHEMA = "literary-engineering-workbench/human-choice/v0.1"

TARGET_TYPES = {"project", "drafts", "characters", "world", "scenes", "branches", "style", "reviews", "word_budget", "canon_patches"}
DIRECT_EDIT_FIELDS = {
    "display_title",
    "display_summary",
    "tags",
    "note",
    "display_name",
    "importance_label",
    "word_count_target",
    "word_count_min",
    "word_count_max",
    "preferred_style_id",
}
DECISION_TYPES = {
    "branch_selection",
    "style_mount",
    "asset_approval",
    "release_approval",
    "canon_patch_approval",
    "word_budget_direction",
    "revision_direction",
    "cross_asset_alignment",
    "state_patch_confirmation",
    "general_project_choice",
}


def build_editable_schema(project_root: Path) -> dict[str, object]:
    root = project_root.resolve()
    return {
        "schema": "literary-engineering-workbench/editable-schema/v0.1",
        "project_root": str(root),
        "mode": "safe-display-and-choice-layer",
        "direct_fields": [
            {
                "field": "display_title",
                "label": "展示标题",
                "risk": "low",
                "writes_to": "workflow/ui_overrides.json",
            },
            {
                "field": "display_summary",
                "label": "展示摘要",
                "risk": "low",
                "writes_to": "workflow/ui_overrides.json",
            },
            {
                "field": "tags",
                "label": "标签",
                "risk": "low",
                "writes_to": "workflow/ui_overrides.json",
            },
            {
                "field": "note",
                "label": "用户备注",
                "risk": "low",
                "writes_to": "workflow/ui_overrides.json",
            },
            {
                "field": "word_count_target",
                "label": "目标字数提示",
                "risk": "medium",
                "writes_to": "workflow/ui_overrides.json",
                "requires": "rerun route-audit or word-budget before relying on it as a formal constraint",
            },
        ],
        "candidate_only_changes": [
            "角色背景故事、动机、秘密、关系变化",
            "世界规则、地点、组织、时间线",
            "正文、修订正文和章节合稿",
            "正式 canon、角色状态写回、发布 latest 指针",
        ],
        "rules": [
            "Direct edits never overwrite canon, characters, plot, drafts, reviews, approvals, task files, or releases.",
            "Fields that affect planning are saved as user intent and must be routed through CLI review before formal use.",
            "Promotion, release, state writeback, and approval still require their formal gates.",
        ],
    }


def save_display_field(
    project_root: Path,
    *,
    target_type: str,
    target_id: str,
    field: str,
    value: object,
    actor: str = "user-ui",
) -> dict[str, object]:
    root = project_root.resolve()
    target_type = _safe_token(target_type, "target_type")
    target_id = _safe_target_id(target_id)
    field = _safe_token(field, "field")
    if target_type not in TARGET_TYPES:
        raise ValueError(f"target_type must be one of: {', '.join(sorted(TARGET_TYPES))}")
    if field not in DIRECT_EDIT_FIELDS:
        raise ValueError(f"field is not frontend-editable: {field}")
    safe_value = _safe_value(value)
    path = root / "workflow" / "ui_overrides.json"
    payload = read_json_file(path)
    if not payload:
        payload = {"schema": UI_OVERRIDES_SCHEMA, "items": {}}
    items = payload.get("items") if isinstance(payload.get("items"), dict) else {}
    key = f"{target_type}:{target_id}"
    record = items.get(key) if isinstance(items.get(key), dict) else {}
    fields = record.get("fields") if isinstance(record.get("fields"), dict) else {}
    fields[field] = safe_value
    now = _now()
    record.update(
        {
            "target_type": target_type,
            "target_id": target_id,
            "fields": fields,
            "updated_at": now,
            "updated_by": actor or "user-ui",
        }
    )
    if field.startswith("word_count_"):
        record["formal_effect"] = "display-only until word-budget/route-audit validates the change"
    items[key] = record
    payload["items"] = items
    payload["updated_at"] = now
    _write_json_atomic(path, payload)
    _append_jsonl(
        root / "workflow" / "user_notes" / "edit_log.jsonl",
        {
            "schema": "literary-engineering-workbench/ui-edit-log/v0.1",
            "target_type": target_type,
            "target_id": target_id,
            "field": field,
            "actor": actor or "user-ui",
            "recorded_at": now,
            "formal_effect": record.get("formal_effect", "display-only"),
        },
    )
    return {"ok": True, "path": _rel(path, root), "key": key, "record": record}


def record_ui_note(
    project_root: Path,
    *,
    target_type: str,
    target_id: str,
    note: str,
    actor: str = "user-ui",
) -> dict[str, object]:
    root = project_root.resolve()
    target_type = _safe_token(target_type, "target_type")
    target_id = _safe_target_id(target_id)
    if target_type not in TARGET_TYPES:
        raise ValueError(f"target_type must be one of: {', '.join(sorted(TARGET_TYPES))}")
    text = truncate_text(str(note or "").strip(), 4000)
    if not text:
        raise ValueError("note must not be empty")
    now = _now()
    record = {
        "schema": USER_NOTE_SCHEMA,
        "note_id": _make_id("note", target_type, target_id),
        "target_type": target_type,
        "target_id": target_id,
        "note": text,
        "actor": actor or "user-ui",
        "recorded_at": now,
        "formal_effect": "user note only; platform agent must route material changes through candidates and review",
    }
    notes_dir = root / "workflow" / "user_notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    note_path = notes_dir / f"{record['note_id']}.json"
    _write_json_atomic(note_path, record)
    _append_jsonl(notes_dir / "index.jsonl", record)
    return {"ok": True, "note": record, "note_path": _rel(note_path, root), "index_path": "workflow/user_notes/index.jsonl"}


def build_current_human_choices(
    project_root: Path,
    route: str = "",
    dashboard_payload: dict[str, object] | None = None,
) -> dict[str, object]:
    root = project_root.resolve()
    normalized_route = str(route or "").strip().lower()
    if normalized_route:
        actions, dashboard_path = _route_choice_actions(root, normalized_route)
    elif isinstance(dashboard_payload, dict):
        actions = dashboard_payload.get("next_actions") if isinstance(dashboard_payload.get("next_actions"), list) else []
        dashboard_path = "workflow/dashboard/workflow_dashboard.json"
    else:
        result = build_workflow_dashboard(root)
        dashboard = read_json_file(result.json_path)
        actions = dashboard.get("next_actions") if isinstance(dashboard.get("next_actions"), list) else []
        dashboard_path = _rel(result.json_path, root)
    choices: list[dict[str, object]] = []
    seen = set()

    def add_choice(choice: dict[str, object] | None, step: str = "", next_action: str = "") -> None:
        if not choice:
            return
        key = str(choice.get("choice_id") or "")
        if not key or key in seen:
            return
        seen.add(key)
        if step:
            choice["task_step"] = step
        if next_action:
            choice["next_action"] = next_action
        choices.append(choice)

    for action in actions:
        if not isinstance(action, dict):
            continue
        route = str(action.get("route") or "")
        step = str(action.get("current_step") or "")
        target = str(action.get("target") or "")
        if route == "scene-development" and step == "branch-selection":
            add_choice(_branch_choice(root, target), step, str(action.get("next_action") or ""))
        elif step == "asset-approval":
            add_choice(_approval_choice(root, route, target, "asset_approval", "候选设定需要你确认是否晋升。"), step, str(action.get("next_action") or ""))
        elif step == "release-approval" or route == "export-and-release" and "approval" in step:
            add_choice(_approval_choice(root, route, target, "release_approval", "发布前需要你确认是否放行。"), step, str(action.get("next_action") or ""))
        elif route == "longform-planning" and step in {"budget-review", "scene-inventory-review", "chapter-obligation-review"}:
            add_choice(_direction_choice(route, target or "longform", "word_budget_direction"), step, str(action.get("next_action") or ""))
        elif route == "scene-development" and step == "candidate-human-decision":
            add_choice(_candidate_asset_alignment_choice(root, target), step, str(action.get("next_action") or ""))
        elif route == "scene-development" and step in {"candidate-review", "agent-review-task", "static-review", "revision-direction"}:
            add_choice(_direction_choice(route, target or "scene", "revision_direction"), step, str(action.get("next_action") or ""))
        elif route == "style-engineering":
            add_choice(_style_mount_choice(root), step, str(action.get("next_action") or ""))
    if not normalized_route or normalized_route == "scene-development":
        for manifest in sorted((root / "branches").glob("*/branch_manifest.json")):
            scene_id = manifest.parent.name
            if (manifest.parent / "branch_selection.md").exists():
                continue
            add_choice(_branch_choice(root, scene_id))
    if not normalized_route or normalized_route == "review-and-audit":
        for choice in _canon_patch_choices(root):
            add_choice(choice)
    if not normalized_route or normalized_route == "style-engineering":
        add_choice(_style_mount_choice(root))
    return {
        "schema": "literary-engineering-workbench/current-human-choices/v0.1",
        "generated_at": _now(),
        "project_root": str(root),
        "choices": choices[:20],
        "recent_choices": read_jsonl_tail(root / "workflow" / "human_choices" / "index.jsonl", 12),
        "dashboard": dashboard_path,
    }


def _route_choice_actions(root: Path, route: str) -> tuple[list[dict[str, object]], str]:
    if route == "scene-development":
        state = next_scene_workflow_state(root)
        if not state or state.get("status") == "ready":
            return [], ""
        return [
            {
                "route": route,
                "target": state.get("scene_id", ""),
                "current_step": state.get("current_step", ""),
                "next_action": state.get("next_action", ""),
            }
        ], ""

    state_dir = root / "workflow" / "runtime_choices"
    result = build_workflow_state(
        root,
        route=route,
        output=state_dir / f"{route}.md",
        json_output=state_dir / f"{route}.json",
    )
    payload = read_json_file(result.json_path)
    keys = {
        "longform-planning": ("longform",),
        "source-ingest": ("source_ingests",),
        "style-engineering": ("styles",),
        "character-and-world-assets": ("assets",),
        "review-and-audit": ("audits",),
        "export-and-release": ("exports",),
    }.get(route, ())
    items: list[dict[str, object]] = []
    for key in keys:
        value = payload.get(key)
        candidates = [value] if isinstance(value, dict) else value if isinstance(value, list) else []
        for item in candidates:
            if not isinstance(item, dict) or item.get("status") == "ready":
                continue
            candidate_id = str(item.get("candidate_id") or "")
            items.append(
                {
                    "route": route,
                    # Asset approvals are bound to the candidate file digest, not the
                    # source scene that happened to introduce the asset.
                    "target": candidate_id or item.get("scene_id") or item.get("target_id") or "",
                    "current_step": item.get("current_step", ""),
                    "next_action": item.get("next_action", ""),
                }
            )
    return items, _rel(result.json_path, root)


def record_human_choice(project_root: Path, payload: dict[str, object]) -> dict[str, object]:
    root = project_root.resolve()
    decision_type = _safe_token(str(payload.get("decision_type") or "general_project_choice"), "decision_type")
    if decision_type not in DECISION_TYPES:
        raise ValueError(f"decision_type must be one of: {', '.join(sorted(DECISION_TYPES))}")
    target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    selected = truncate_text(str(payload.get("selected") or "").strip(), 200)
    if not selected:
        raise ValueError("selected must not be empty")
    choice_id = str(payload.get("choice_id") or "").strip()
    if choice_id:
        choice_id = _safe_choice_id(choice_id)
    else:
        choice_id = _make_id("choice", decision_type, selected)
    options = payload.get("options") if isinstance(payload.get("options"), list) else []
    record = {
        "schema": HUMAN_CHOICE_SCHEMA,
        "choice_id": choice_id,
        "route": truncate_text(str(payload.get("route") or ""), 80),
        "task_id": truncate_text(str(payload.get("task_id") or ""), 140),
        "decision_type": decision_type,
        "target": _safe_mapping(target),
        "options": _safe_options(options),
        "selected": selected,
        "rationale": truncate_text(str(payload.get("rationale") or "").strip(), 2000),
        "actor": truncate_text(str(payload.get("actor") or "user-ui"), 80),
        "status": "submitted",
        "recorded_at": _now(),
        "formal_effect": "human choice evidence only; downstream route gates still validate produced artifacts",
    }
    choices_dir = root / "workflow" / "human_choices"
    choices_dir.mkdir(parents=True, exist_ok=True)
    choice_path = choices_dir / f"{choice_id}.json"
    if choice_path.exists():
        choice_path = choices_dir / f"{choice_id}-{_stamp()}.json"
        record["choice_id"] = choice_path.stem
    _write_json_atomic(choice_path, record)
    _append_jsonl(choices_dir / "index.jsonl", record)
    materialized = ""
    if bool(payload.get("materialize", True)) and decision_type == "branch_selection":
        materialized = _materialize_branch_selection(root, record, choice_path)
    elif bool(payload.get("materialize", True)) and decision_type in {
        "asset_approval", "release_approval", "canon_patch_approval", "state_patch_confirmation"
    }:
        materialized = _materialize_approval(root, record)
    return {
        "ok": True,
        "choice": record,
        "choice_path": _rel(choice_path, root),
        "index_path": "workflow/human_choices/index.jsonl",
        "materialized": materialized,
    }


def _branch_choice(root: Path, scene_id: str) -> dict[str, object] | None:
    scene_id = _safe_target_id(scene_id or "")
    if not scene_id:
        return None
    manifest = root / "branches" / scene_id / "branch_manifest.json"
    if not manifest.exists():
        return None
    payload = read_json_file(manifest)
    options = []
    for branch in payload.get("branches", []) if isinstance(payload.get("branches"), list) else []:
        if not isinstance(branch, dict):
            continue
        option_id = str(branch.get("branch_id") or branch.get("id") or "").strip()
        if not option_id:
            continue
        options.append(
            {
                "id": option_id,
                "label": truncate_text(str(branch.get("title") or option_id), 80),
                "summary": truncate_text(str(branch.get("premise") or branch.get("summary") or "这个分支需要平台 Agent 继续解释代价。"), 220),
            }
        )
    if not options:
        return None
    recommended = str(payload.get("recommended_branch") or "")
    return {
        "choice_id": _make_id("choice", "branch_selection", scene_id),
        "route": "scene-development",
        "decision_type": "branch_selection",
        "title": f"{scene_id} 需要选择剧情分支",
        "summary": "选择后会写入正式 branch_selection.md，但后续仍要通过 CLI 门禁。",
        "target": {"scene_id": scene_id},
        "source_paths": [_rel(manifest, root)],
        "recommended": recommended,
        "options": options,
        "actions": ["选择分支", "要求重新推演"],
    }


def _approval_choice(root: Path, route: str, target: str, decision_type: str, summary: str) -> dict[str, object]:
    approval_target = _safe_approval_target(target or "target")
    choice_target = _safe_target_id(approval_target)
    subject_sha256 = _asset_candidate_sha256(root, approval_target) if decision_type == "asset_approval" else (
        release_candidate_fingerprint(root, approval_target) if decision_type == "release_approval" else ""
    )
    return {
        "choice_id": _make_id("choice", decision_type, choice_target),
        "route": route,
        "decision_type": decision_type,
        "title": f"{approval_target} 等待用户审批",
        "summary": summary,
        "target": {"target_id": approval_target, **({"candidate_sha256": subject_sha256} if subject_sha256 else {})},
        "source_paths": ["workflow/approvals/index.jsonl"],
        "options": [
            {"id": "approve", "label": "批准", "summary": "允许进入下一步正式流程。"},
            {"id": "revise", "label": "要求修改", "summary": "保留方向，但需要平台 Agent 修订后再审。"},
            {"id": "reject", "label": "拒绝", "summary": "当前候选不能进入后续流程。"},
        ],
        "actions": ["记录选择"],
    }


def _direction_choice(route: str, target: str, decision_type: str) -> dict[str, object]:
    safe_target = _safe_target_id(target or "longform")
    if decision_type == "revision_direction":
        return {
            "choice_id": _make_id("choice", decision_type, safe_target),
            "route": route,
            "decision_type": decision_type,
            "title": f"{safe_target} 需要确认修订方向",
            "summary": "用于记录你希望平台 Agent 在修订中优先处理的问题，正式正文仍需 revise/review/promote。",
            "target": {"target_id": safe_target},
            "source_paths": ["reviews/", "drafts/candidates/", "drafts/revisions/"],
            "options": [
                {"id": "fix_logic_first", "label": "先修因果逻辑", "summary": "优先处理人物动机、剧情因果和 canon 冲突。"},
                {"id": "fix_style_first", "label": "先修文风和 AI 味", "summary": "优先处理句式、标点、节奏和文风偏移。"},
                {"id": "expand_scene", "label": "扩写场景", "summary": "在不灌水的前提下补足动作、冲突和读者回报。"},
                {"id": "ask_agent_compare", "label": "要求给出修订方案对比", "summary": "先让平台 Agent 提供多种修订策略再决定。"},
            ],
            "actions": ["记录修订方向"],
        }
    return {
        "choice_id": _make_id("choice", decision_type, safe_target),
        "route": route,
        "decision_type": decision_type,
        "title": "长篇规划需要方向取舍",
        "summary": "用于记录你对扩纲、场景库存或章节义务的取舍，正式改动仍走候选和 review。",
        "target": {"target_id": safe_target},
        "source_paths": ["plot/word_budget/word_budget.json"],
        "options": [
            {"id": "expand_inventory", "label": "扩充剧情库存", "summary": "增加事件、子线、地点或关系压力。"},
            {"id": "reduce_scope", "label": "收缩作品规模", "summary": "降低目标长度或卷章数量。"},
            {"id": "ask_agent_replan", "label": "重新规划", "summary": "让平台 Agent 提出新的字数与结构方案。"},
        ],
        "actions": ["记录方向"],
    }


def _candidate_asset_alignment_choice(root: Path, scene_id: str) -> dict[str, object] | None:
    safe_scene_id = _safe_target_id(scene_id or "")
    if not safe_scene_id:
        return None
    review_path = root / "reviews" / "agent" / f"{safe_scene_id}_scene_review.json"
    review = read_json_file(review_path)
    candidate_sha256 = str(review.get("candidate_sha256") or "").strip().lower()
    if not candidate_sha256:
        return None
    human_notes = []
    for key in ("blocking_issues", "warnings", "revision_actions"):
        values = review.get(key) if isinstance(review.get(key), list) else []
        human_notes.extend(
            str(item.get("description") or item.get("note") or "")
            for item in values
            if isinstance(item, dict)
            and str(item.get("resolution") or "").strip().lower() in {
                "needs_human_review",
                "human_decision_required",
                "pending_user_decision",
            }
        )
    summary = "；".join(note for note in human_notes if note) or "审查指出正文与正式设定存在冲突，必须先决定哪个事实成立。"
    return {
        "choice_id": _make_id("choice", "candidate_asset_alignment", safe_scene_id),
        "route": "scene-development",
        "decision_type": "cross_asset_alignment",
        "title": f"{safe_scene_id} 需要确认正式设定",
        "summary": summary,
        "target": {
            "scene_id": safe_scene_id,
            "target_id": safe_scene_id,
            "candidate_sha256": candidate_sha256,
            "review": _rel(review_path, root),
        },
        "source_paths": [_rel(review_path, root)],
        "recommended": "align_prose_to_formal_asset",
        "options": [
            {
                "id": "align_prose_to_formal_asset",
                "label": "以现有正式设定为准修改正文",
                "summary": "不改 canon 或角色文件，只让正文与已批准的正式资产一致，然后重新审查。",
            },
            {
                "id": "hold_for_asset_revision",
                "label": "保留正文，转入设定修订",
                "summary": "正文不自动改写；先通过角色或 canon 的正式候选、审查与审批流程修改设定。",
            },
        ],
        "actions": ["确认设定优先级"],
    }


def _canon_patch_choices(root: Path) -> list[dict[str, object]]:
    folder = root / "canon" / "patches"
    if not folder.exists():
        return []
    choices: list[dict[str, object]] = []
    for path in sorted(folder.glob("*_canon_patch.json"))[:80]:
        payload = read_json_file(path)
        if not payload or payload.get("applied"):
            continue
        change = payload.get("canon_change", "unknown")
        if change is False or str(change).lower() == "false":
            continue
        scene_id = _safe_target_id(str(payload.get("scene_id") or path.stem.replace("_canon_patch", "")) or "canon")
        digest = _file_sha256(path)
        approval = _latest_approval_record(root, path.stem)
        if approval and str(approval.get("subject_sha256") or "").lower() == digest:
            continue
        patch_items = payload.get("items") if isinstance(payload.get("items"), list) else []
        choices.append(
            {
                "choice_id": _make_id("choice", "canon_patch_approval", scene_id),
                "route": "review-and-audit",
                "decision_type": "canon_patch_approval",
                "title": f"{scene_id} 有世界观写回候选",
                "summary": "这会影响后续场景的世界规则和事实边界。选择只记录审批意图，正式写入仍要走 canon-apply。",
                "target": {
                    "scene_id": scene_id,
                    "patch": _rel(path, root),
                    "approval_run_id": path.stem,
                    "candidate_sha256": digest,
                },
                "source_paths": [_rel(path, root), _rel(path.with_suffix(".md"), root)],
                "recommended": "review_then_apply" if patch_items else "revise",
                "options": [
                    {"id": "approve", "label": "同意写回", "summary": "认可这批候选事实，后续仍需正式 apply。"},
                    {"id": "revise", "label": "要求修改", "summary": "方向可以保留，但候选事实需要平台 Agent 重写。"},
                    {"id": "reject", "label": "拒绝", "summary": "这批候选事实不应进入世界观。"},
                ],
                "actions": ["记录 canon 审批"],
            }
        )
    return choices


def _style_mount_choice(root: Path) -> dict[str, object] | None:
    if (root / "style" / "active_style_skill.json").exists():
        return None
    options = []
    for path in sorted((root / "style").glob("**/style_skill.json"))[:20]:
        payload = read_json_file(path)
        style_id = str(payload.get("style_id") or path.parent.name).strip()
        if not style_id:
            continue
        options.append(
            {
                "id": style_id,
                "label": truncate_text(str(payload.get("author") or style_id), 80),
                "summary": truncate_text(str(payload.get("mode") or "项目内发现的文风候选。"), 180),
            }
        )
    for path in sorted((root / "style").glob("**/style_prompt.md"))[:20]:
        style_id = path.parent.name
        if any(option["id"] == style_id for option in options):
            continue
        options.append(
            {
                "id": style_id,
                "label": truncate_text(style_id, 80),
                "summary": "项目内发现的文风提示词，可作为挂载候选继续评审。",
            }
        )
    if not options:
        return None
    return {
        "choice_id": _make_id("choice", "style_mount", "project-style"),
        "route": "style-engineering",
        "decision_type": "style_mount",
        "title": "需要选择创作使用的文风",
        "summary": "文风会作为表达层最高优先级约束。选择只记录意图，正式挂载仍需文风页或 style-lab mount。 ",
        "target": {"target_id": "project-style"},
        "source_paths": ["style/"],
        "options": options[:8],
        "actions": ["记录文风选择"],
    }


def _materialize_branch_selection(root: Path, record: dict[str, object], choice_path: Path) -> str:
    target = record.get("target") if isinstance(record.get("target"), dict) else {}
    scene_id = _safe_target_id(str(target.get("scene_id") or target.get("target_id") or ""))
    if not scene_id:
        raise ValueError("branch selection target.scene_id is required")
    branch_dir = root / "branches" / scene_id
    manifest = branch_dir / "branch_manifest.json"
    if not manifest.exists():
        raise FileNotFoundError(f"branch manifest not found: {manifest}")
    branch_dir.mkdir(parents=True, exist_ok=True)
    selected = str(record.get("selected") or "").strip()
    path = branch_dir / "branch_selection.md"
    lines = [
        f"# Branch Selection：{scene_id}",
        "",
        "## 用户结构化选择",
        "",
        "- decision: selected",
        f"- selected_branch: {selected}",
        f"- actor: {record.get('actor', 'user-ui')}",
        f"- selected_at: {record.get('recorded_at', '')}",
        f"- source_choice: {_rel(choice_path, root)}",
        "",
        "## 选择理由",
        "",
        str(record.get("rationale") or "用户通过前端结构化选择确认。"),
        "",
        "## 正式边界",
        "",
        "- 本文件只确认分支选择，不代表正文、canon、状态写回或发布已完成。",
        "- 下一步仍必须由 CLI route gate 验证 composition、generation、review 和 promotion。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return _rel(path, root)


def _materialize_approval(root: Path, record: dict[str, object]) -> str:
    selected = str(record.get("selected") or "").strip()
    if selected not in {"approve", "revise", "reject", "defer"}:
        raise ValueError("approval choice must select approve, revise, reject, or defer")
    decision_type = str(record.get("decision_type") or "")
    target = record.get("target") if isinstance(record.get("target"), dict) else {}
    run_id = str(target.get("target_id") or target.get("scene_id") or "").strip()
    if decision_type == "release_approval" and run_id and not run_id.startswith("release-"):
        run_id = f"release-{run_id}"
    if decision_type == "canon_patch_approval":
        patch_rel = str(target.get("patch") or "").strip()
        patch = root / patch_rel if patch_rel else None
        if patch is not None and patch.is_file():
            run_id = str(target.get("approval_run_id") or patch.stem)
    if not run_id:
        raise ValueError(f"{decision_type} choice does not identify its approval target")
    result = record_workflow_approval(
        root,
        run_id,
        selected,
        actor=str(record.get("actor") or "user-ui"),
        notes=str(record.get("rationale") or ""),
        subject_sha256=str(target.get("candidate_sha256") or ""),
    )
    return _rel(result.approval_path, root)


def _asset_candidate_sha256(root: Path, candidate_id: str) -> str:
    for relative in (
        f"characters/candidates/{candidate_id}.json",
        f"canon/candidates/world_rules/{candidate_id}.json",
        f"canon/candidates/locations/{candidate_id}.json",
        f"canon/candidates/organizations/{candidate_id}.json",
        f"plot/candidates/outlines/{candidate_id}.json",
        f"plot/candidates/chapters/{candidate_id}.json",
        f"plot/candidates/scenes/{candidate_id}.json",
    ):
        path = root / relative
        if path.is_file():
            return hashlib.sha256(path.read_bytes()).hexdigest()
    return ""


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


def _latest_approval_record(root: Path, run_id: str) -> dict[str, object]:
    index = root / "workflow" / "approvals" / "index.jsonl"
    latest: dict[str, object] = {}
    if not index.is_file():
        return latest
    for line in index.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and item.get("run_id") == run_id:
            latest = item
    return latest


def _safe_mapping(value: dict[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, raw in value.items():
        safe_key = _safe_token(str(key), "target key")
        result[safe_key] = truncate_text(str(raw), 240)
    return result


def _safe_options(options: list[object]) -> list[dict[str, str]]:
    cleaned = []
    for item in options[:20]:
        if not isinstance(item, dict):
            continue
        option_id = truncate_text(str(item.get("id") or item.get("label") or ""), 120)
        if not option_id:
            continue
        cleaned.append(
            {
                "id": option_id,
                "label": truncate_text(str(item.get("label") or option_id), 120),
                "summary": truncate_text(str(item.get("summary") or ""), 500),
            }
        )
    return cleaned


def _safe_value(value: object) -> object:
    if isinstance(value, str):
        return truncate_text(value, 4000)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [truncate_text(str(item), 240) for item in value[:40]]
    return truncate_text(str(value), 1000)


def _safe_token(value: str, label: str) -> str:
    token = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", token):
        raise ValueError(f"invalid {label}")
    if ".." in token:
        raise ValueError(f"invalid {label}")
    return token


def _safe_target_id(value: str) -> str:
    target = value.strip().replace("/", "__").replace("\\", "__")
    target = re.sub(r"[^A-Za-z0-9_.-]", "_", target)
    target = re.sub(r"_+", "_", target).strip("._-")
    return target[:120]


def _safe_approval_target(value: str) -> str:
    target = value.strip()
    if not target or len(target) > 128 or ".." in target or any(char in target for char in "/\\"):
        raise ValueError("invalid approval target")
    if any(ord(char) < 32 for char in target):
        raise ValueError("invalid approval target")
    return target


def _safe_choice_id(value: str) -> str:
    choice_id = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,160}", choice_id) or ".." in choice_id:
        raise ValueError("invalid choice_id")
    return choice_id


def _make_id(prefix: str, *parts: str) -> str:
    joined = ".".join(_safe_target_id(str(part)) for part in parts if str(part).strip())
    return _safe_choice_id(f"{prefix}.{joined}.{_stamp()}")


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
