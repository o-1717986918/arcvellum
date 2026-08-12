"""Human-choice construction, durable decision records, and formal materialization."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ...approval import record_workflow_approval
from ...character_state_apply import state_patch_writeback_status
from ...display_cleaner import read_json_file, read_jsonl_tail, truncate_text
from ...project_interaction_common import (
    DECISION_TYPES, HUMAN_CHOICE_SCHEMA, _append_jsonl, _make_id, _now, _rel, _resolved_choice_ids,
    _safe_approval_target, _safe_choice_id, _safe_mapping, _safe_options,
    _safe_target_id, _safe_token, _stable_choice_id, _write_json_atomic,
)
from ...release_fingerprint import release_candidate_fingerprint
from ...workflow_dashboard import build_workflow_dashboard
from ...workflow_state import build_workflow_state, next_scene_workflow_state
from .style_choices import build_style_mount_choice as _style_mount_choice

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
    resolved = _resolved_choice_ids(root)

    def add_choice(choice: dict[str, object] | None, step: str = "", next_action: str = "") -> None:
        if not choice:
            return
        if step:
            choice["task_step"] = step
        if next_action:
            choice["next_action"] = next_action
        choice["choice_id"] = _stable_choice_id(choice)
        key = str(choice["choice_id"])
        if key in seen or key in resolved:
            return
        seen.add(key)
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
        elif route == "scene-development" and step in {"candidate-revision", "static-revision", "revision-direction"}:
            add_choice(
                _revision_direction_choice(root, route, target or "scene", step),
                step,
                str(action.get("next_action") or ""),
            )
        elif route == "scene-development" and step in {"state-writeback", "state-patch-approval"}:
            add_choice(_state_patch_choice(root, target), step, str(action.get("next_action") or ""))
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
    if not normalized_route or normalized_route == "scene-development":
        for choice in _state_patch_choices(root):
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
        "status": "recorded",
        "recorded_at": _now(),
        "formal_effect": "human choice evidence only; downstream route gates still validate produced artifacts",
    }
    choices_dir = root / "workflow" / "human_choices"
    choices_dir.mkdir(parents=True, exist_ok=True)
    choice_path = choices_dir / f"{choice_id}.json"
    if choice_path.exists():
        existing = read_json_file(choice_path)
        same_choice = (
            str(existing.get("decision_type") or "") == decision_type
            and str(existing.get("selected") or "") == selected
            and _safe_mapping(existing.get("target") if isinstance(existing.get("target"), dict) else {}) == record["target"]
        )
        if not same_choice:
            raise ValueError("这个创作决定已经用另一项选择提交，不能静默覆盖。")
        return {
            "ok": True,
            "choice": existing,
            "choice_path": _rel(choice_path, root),
            "index_path": "workflow/human_choices/index.jsonl",
            "materialized": str(existing.get("materialized") or ""),
            "duplicate": True,
        }
    materialized = ""
    if bool(payload.get("materialize", True)) and decision_type == "branch_selection":
        _write_json_atomic(choice_path, record)
        materialized = _materialize_branch_selection(root, record, choice_path)
    elif bool(payload.get("materialize", True)) and decision_type in {
        "asset_approval", "release_approval", "canon_patch_approval", "state_patch_confirmation"
    }:
        materialized = _materialize_approval(root, record)
    record["materialized"] = materialized
    record["consumed"] = bool(materialized)
    record["status"] = "submitted" if record["consumed"] else "recorded"
    _write_json_atomic(choice_path, record)
    _append_jsonl(choices_dir / "index.jsonl", record)
    return {
        "ok": True,
        "choice": record,
        "choice_path": _rel(choice_path, root),
        "index_path": "workflow/human_choices/index.jsonl",
        "materialized": materialized,
        "duplicate": False,
    }

def finalize_human_choice(
    project_root: Path,
    choice_id: str,
    *,
    materialized: str,
    effect: dict[str, object] | None = None,
    consumed: bool = True,
) -> dict[str, object]:
    """Finalize a Studio-layer choice after its non-core effect succeeds."""

    root = project_root.resolve()
    safe_id = _safe_choice_id(choice_id)
    path = root / "workflow" / "human_choices" / f"{safe_id}.json"
    record = read_json_file(path)
    if not record:
        raise FileNotFoundError(f"human choice not found: {safe_id}")
    record["materialized"] = truncate_text(str(materialized or ""), 1000)
    record["effect"] = _safe_mapping(effect or {})
    record["consumed"] = bool(consumed)
    record["status"] = "submitted" if consumed else "recorded"
    record["finalized_at"] = _now()
    _write_json_atomic(path, record)
    return record

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
    source_paths = (
        _asset_approval_source_paths(root, approval_target)
        if decision_type == "asset_approval"
        else ["workflow/approvals/index.jsonl"]
    )
    return {
        "choice_id": _make_id("choice", decision_type, choice_target),
        "route": route,
        "decision_type": decision_type,
        "title": f"{approval_target} 等待用户审批",
        "summary": summary,
        "target": {"target_id": approval_target, **({"candidate_sha256": subject_sha256} if subject_sha256 else {})},
        "source_paths": source_paths,
        "options": [
            {"id": "approve", "label": "批准", "summary": "允许进入下一步正式流程。"},
            {"id": "revise", "label": "要求修改", "summary": "保留方向，但需要平台 Agent 修订后再审。"},
            {"id": "reject", "label": "拒绝", "summary": "当前候选不能进入后续流程。"},
        ],
        "actions": ["记录选择"],
    }

def _direction_choice(route: str, target: str, decision_type: str) -> dict[str, object]:
    safe_target = _safe_target_id(target or "longform")
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


def _revision_direction_choice(root: Path, route: str, target: str, step: str) -> dict[str, object]:
    safe_target = _safe_target_id(target or "scene")
    review_json = root / "reviews" / "agent" / f"{safe_target}_scene_review.json"
    review_markdown = review_json.with_suffix(".md")
    review = read_json_file(review_json)
    candidate_relative = str(review.get("candidate_path") or review.get("candidate") or "").replace("\\", "/").strip().lstrip("/")
    candidate = (root / candidate_relative).resolve() if candidate_relative else None
    try:
        candidate_relative = candidate.relative_to(root).as_posix() if candidate is not None else ""
    except ValueError:
        candidate = None
        candidate_relative = ""
    if step == "static-revision":
        candidate_relative = f"drafts/scenes/{safe_target}.md"
        candidate = (root / candidate_relative).resolve()

    source_paths = []
    for path in (
        review_json,
        review_markdown,
        root / f"reviews/{safe_target}-review.md" if step == "static-revision" else None,
        candidate,
        root / f"scenes/{safe_target}.yaml",
        root / f"drafts/compositions/{safe_target}_composition_review.json",
    ):
        if path is None or not path.is_file():
            continue
        relative = path.resolve().relative_to(root).as_posix()
        if relative not in source_paths:
            source_paths.append(relative)

    candidate_sha256 = ""
    if candidate is not None and candidate.is_file():
        candidate_sha256 = hashlib.sha256(candidate.read_bytes()).hexdigest()
    target_payload = {
        "target_id": safe_target,
        "candidate_path": candidate_relative,
        "candidate_sha256": candidate_sha256,
        "review_conclusion": str(review.get("conclusion") or ""),
    }
    return {
        "choice_id": _make_id("choice", "revision_direction", safe_target),
        "route": route,
        "decision_type": "revision_direction",
        "title": f"{safe_target} 需要确认修订方向",
        "summary": "根据当前候选及其精确审查证据选择修订重点；正式正文仍需 revise/review/promote。",
        "target": target_payload,
        "source_paths": source_paths,
        "options": [
            {"id": "fix_logic_first", "label": "先修因果逻辑", "summary": "优先处理人物动机、剧情因果和 canon 冲突。"},
            {"id": "fix_style_first", "label": "先修文风和 AI 味", "summary": "优先处理句式、标点、节奏和文风偏移。"},
            {"id": "expand_scene", "label": "扩写场景", "summary": "在不灌水的前提下补足动作、冲突和读者回报。"},
            {"id": "ask_agent_compare", "label": "要求给出修订方案对比", "summary": "先让平台 Agent 提供多种修订策略再决定。"},
        ],
        "actions": ["记录修订方向"],
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

def _state_patch_choices(root: Path) -> list[dict[str, object]]:
    folder = root / "characters" / "state_patches"
    if not folder.exists():
        return []
    choices: list[dict[str, object]] = []
    for path in sorted(folder.glob("*_state_patch.json"))[:80]:
        scene_id = _safe_target_id(path.stem.replace("_state_patch", "") or "state")
        status = state_patch_writeback_status(root, scene_id)
        if status.get("status") != "needs_approval":
            continue
        digest = str(status.get("candidate_sha256") or _file_sha256(path))
        choices.append(
            {
                "choice_id": _make_id("choice", "state_patch_confirmation", scene_id),
                "route": "scene-development",
                "decision_type": "state_patch_confirmation",
                "title": f"{scene_id} 有人物状态写回候选",
                "summary": "确认后，系统只会将已审查的人物状态、关系和弧光写回对应角色档案；不会写入 Canon。",
                "target": {
                    "scene_id": scene_id,
                    "patch": _rel(path, root),
                    "approval_run_id": path.stem,
                    "candidate_sha256": digest,
                },
                "source_paths": [_rel(path, root), _rel(path.with_suffix(".md"), root), _rel(path.with_name(f"{scene_id}_state_patch_review.json"), root)],
                "recommended": "approve",
                "options": [
                    {"id": "approve", "label": "同意写回", "summary": "允许按已审查补丁写回人物状态。"},
                    {"id": "revise", "label": "要求修改", "summary": "退回候选补丁，补充证据或收缩变化范围。"},
                    {"id": "reject", "label": "拒绝", "summary": "不允许这批人物状态变化进入正式档案。"},
                ],
                "actions": ["记录状态写回审批"],
            }
        )
    return choices

def _state_patch_choice(root: Path, scene_id: str) -> dict[str, object] | None:
    return next((item for item in _state_patch_choices(root) if str((item.get("target") or {}).get("scene_id") or "") == _safe_target_id(scene_id or "")), None)

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
    if decision_type == "state_patch_confirmation":
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


def _asset_approval_source_paths(root: Path, candidate_id: str) -> list[str]:
    """Supply the exact candidate and independent review evidence to a delegated approval."""

    candidates = (
        f"characters/candidates/{candidate_id}.json",
        f"canon/candidates/world_rules/{candidate_id}.json",
        f"canon/candidates/locations/{candidate_id}.json",
        f"canon/candidates/organizations/{candidate_id}.json",
        f"plot/candidates/outlines/{candidate_id}.json",
        f"plot/candidates/chapters/{candidate_id}.json",
        f"plot/candidates/scenes/{candidate_id}.json",
    )
    candidate_rel = next((relative for relative in candidates if (root / relative).is_file()), "")
    paths = [
        f"reviews/assets/{candidate_id}_review.json",
        f"reviews/assets/{candidate_id}_review.md",
    ]
    if candidate_rel:
        paths.extend([candidate_rel, candidate_rel.removesuffix(".json") + ".md"])
    paths.append("workflow/approvals/index.jsonl")
    # Keep the declared evidence contract stable before and after an approval
    # record is written. Missing files are surfaced as missing evidence rather
    # than silently changing the choice fingerprint.
    return list(dict.fromkeys(paths))

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
