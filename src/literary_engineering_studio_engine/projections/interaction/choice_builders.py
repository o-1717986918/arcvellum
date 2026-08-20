"""Pure and read-only builders for frontend human-choice cards."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ...character_state_apply import state_patch_writeback_status
from ...display_cleaner import read_json_file, truncate_text
from ...project_interaction_common import _make_id, _rel, _safe_approval_target, _safe_target_id
from ...release_fingerprint import release_candidate_fingerprint


def branch_choice(root: Path, scene_id: str) -> dict[str, object] | None:
    scene_id = _safe_target_id(scene_id or "")
    if not scene_id:
        return None
    manifest = root / "branches" / scene_id / "branch_manifest.json"
    if not manifest.exists():
        return None
    payload = read_json_file(manifest)
    options = [_branch_option(item) for item in _dict_rows(payload.get("branches"))]
    options = [item for item in options if item]
    if not options:
        return None
    return {
        "choice_id": _make_id("choice", "branch_selection", scene_id),
        "route": "scene-development", "decision_type": "branch_selection",
        "title": f"{scene_id} 需要选择剧情分支",
        "summary": "选择后会写入正式 branch_selection.md，但后续仍要通过 CLI 门禁。",
        "target": {"scene_id": scene_id}, "source_paths": [_rel(manifest, root)],
        "recommended": str(payload.get("recommended_branch") or ""), "options": options,
        "actions": ["选择分支", "要求重新推演"],
    }


def approval_choice(
    root: Path,
    route: str,
    target: str,
    decision_type: str,
    summary: str,
) -> dict[str, object]:
    approval_target = _safe_approval_target(target or "target")
    choice_target = _safe_target_id(approval_target)
    subject_sha256 = _approval_subject_sha256(root, approval_target, decision_type)
    source_paths = asset_approval_source_paths(root, approval_target) if decision_type == "asset_approval" else ["workflow/approvals/index.jsonl"]
    target_payload = {"target_id": approval_target}
    if subject_sha256:
        target_payload["candidate_sha256"] = subject_sha256
    return {
        "choice_id": _make_id("choice", decision_type, choice_target), "route": route,
        "decision_type": decision_type, "title": f"{approval_target} 等待用户审批", "summary": summary,
        "target": target_payload, "source_paths": source_paths,
        "options": _approval_options(), "actions": ["记录选择"],
    }


def direction_choice(route: str, target: str, decision_type: str) -> dict[str, object]:
    safe_target = _safe_target_id(target or "longform")
    return {
        "choice_id": _make_id("choice", decision_type, safe_target), "route": route,
        "decision_type": decision_type, "title": "长篇规划需要方向取舍",
        "summary": "用于记录你对扩纲、场景库存或章节义务的取舍，正式改动仍走候选和 review。",
        "target": {"target_id": safe_target}, "source_paths": ["plot/word_budget/word_budget.json"],
        "options": [
            {"id": "expand_inventory", "label": "扩充剧情库存", "summary": "增加事件、子线、地点或关系压力。"},
            {"id": "reduce_scope", "label": "收缩作品规模", "summary": "降低目标长度或卷章数量。"},
            {"id": "ask_agent_replan", "label": "重新规划", "summary": "让平台 Agent 提出新的字数与结构方案。"},
        ],
        "actions": ["记录方向"],
    }


def revision_direction_choice(root: Path, route: str, target: str, step: str) -> dict[str, object]:
    safe_target = _safe_target_id(target or "scene")
    review_json = root / "reviews" / "agent" / f"{safe_target}_scene_review.json"
    review = read_json_file(review_json)
    candidate_relative, candidate = _revision_candidate(root, safe_target, step, review)
    source_paths = _revision_sources(root, safe_target, step, review_json, candidate)
    candidate_sha256 = hashlib.sha256(candidate.read_bytes()).hexdigest() if candidate is not None and candidate.is_file() else ""
    return {
        "choice_id": _make_id("choice", "revision_direction", safe_target), "route": route,
        "decision_type": "revision_direction", "title": f"{safe_target} 需要确认修订方向",
        "summary": "根据当前候选及其精确审查证据选择修订重点；正式正文仍需 revise/review/promote。",
        "target": {
            "target_id": safe_target, "candidate_path": candidate_relative,
            "candidate_sha256": candidate_sha256, "review_conclusion": str(review.get("conclusion") or ""),
        },
        "source_paths": source_paths, "options": _revision_options(), "actions": ["记录修订方向"],
    }


def candidate_asset_alignment_choice(root: Path, scene_id: str) -> dict[str, object] | None:
    safe_scene_id = _safe_target_id(scene_id or "")
    if not safe_scene_id:
        return None
    review_path = root / "reviews" / "agent" / f"{safe_scene_id}_scene_review.json"
    review = read_json_file(review_path)
    candidate_sha256 = str(review.get("candidate_sha256") or "").strip().lower()
    if not candidate_sha256:
        return None
    summary = "；".join(_human_review_notes(review)) or "审查指出正文与正式设定存在冲突，必须先决定哪个事实成立。"
    return {
        "choice_id": _make_id("choice", "candidate_asset_alignment", safe_scene_id),
        "route": "scene-development", "decision_type": "cross_asset_alignment",
        "title": f"{safe_scene_id} 需要确认正式设定", "summary": summary,
        "target": {
            "scene_id": safe_scene_id, "target_id": safe_scene_id,
            "candidate_sha256": candidate_sha256, "review": _rel(review_path, root),
        },
        "source_paths": [_rel(review_path, root)], "recommended": "align_prose_to_formal_asset",
        "options": [
            {"id": "align_prose_to_formal_asset", "label": "以现有正式设定为准修改正文", "summary": "不改 canon 或角色文件，只让正文与已批准的正式资产一致，然后重新审查。"},
            {"id": "hold_for_asset_revision", "label": "保留正文，转入设定修订", "summary": "正文不自动改写；先通过角色或 canon 的正式候选、审查与审批流程修改设定。"},
        ],
        "actions": ["确认设定优先级"],
    }


def canon_patch_choices(root: Path) -> list[dict[str, object]]:
    folder = root / "canon" / "patches"
    if not folder.exists():
        return []
    choices: list[dict[str, object]] = []
    for path in sorted(folder.glob("*_canon_patch.json"))[:80]:
        choice = _canon_patch_choice(root, path)
        if choice:
            choices.append(choice)
    return choices


def state_patch_choices(root: Path) -> list[dict[str, object]]:
    folder = root / "characters" / "state_patches"
    if not folder.exists():
        return []
    choices: list[dict[str, object]] = []
    for path in sorted(folder.glob("*_state_patch.json"))[:80]:
        choice = _state_patch_choice_from_path(root, path)
        if choice:
            choices.append(choice)
    return choices


def state_patch_choice(root: Path, scene_id: str) -> dict[str, object] | None:
    expected = _safe_target_id(scene_id or "")
    return next((item for item in state_patch_choices(root) if str((item.get("target") or {}).get("scene_id") or "") == expected), None)


def asset_candidate_sha256(root: Path, candidate_id: str) -> str:
    for relative in _asset_candidates(candidate_id):
        path = root / relative
        if path.is_file():
            return hashlib.sha256(path.read_bytes()).hexdigest()
    return ""


def asset_approval_source_paths(root: Path, candidate_id: str) -> list[str]:
    candidate_rel = next((relative for relative in _asset_candidates(candidate_id) if (root / relative).is_file()), "")
    paths = [f"reviews/assets/{candidate_id}_review.json", f"reviews/assets/{candidate_id}_review.md"]
    if candidate_rel:
        paths.extend([candidate_rel, candidate_rel.removesuffix(".json") + ".md"])
    paths.append("workflow/approvals/index.jsonl")
    return list(dict.fromkeys(paths))


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


def latest_approval_record(root: Path, run_id: str) -> dict[str, object]:
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


def _branch_option(branch: dict[str, object]) -> dict[str, str] | None:
    option_id = str(branch.get("branch_id") or branch.get("id") or "").strip()
    if not option_id:
        return None
    return {
        "id": option_id, "label": truncate_text(str(branch.get("title") or option_id), 80),
        "summary": truncate_text(str(branch.get("premise") or branch.get("summary") or "这个分支需要平台 Agent 继续解释代价。"), 220),
    }


def _approval_subject_sha256(root: Path, target: str, decision_type: str) -> str:
    if decision_type == "asset_approval":
        return asset_candidate_sha256(root, target)
    return release_candidate_fingerprint(root, target) if decision_type == "release_approval" else ""


def _approval_options() -> list[dict[str, str]]:
    return [
        {"id": "approve", "label": "批准", "summary": "允许进入下一步正式流程。"},
        {"id": "revise", "label": "要求修改", "summary": "保留方向，但需要平台 Agent 修订后再审。"},
        {"id": "reject", "label": "拒绝", "summary": "当前候选不能进入后续流程。"},
    ]


def _revision_candidate(
    root: Path,
    scene_id: str,
    step: str,
    review: dict[str, object],
) -> tuple[str, Path | None]:
    relative = str(review.get("candidate_path") or review.get("candidate") or "").replace("\\", "/").strip().lstrip("/")
    if step == "static-revision":
        relative = f"drafts/scenes/{scene_id}.md"
    candidate = (root / relative).resolve() if relative else None
    try:
        relative = candidate.relative_to(root).as_posix() if candidate is not None else ""
    except ValueError:
        return "", None
    return relative, candidate


def _revision_sources(
    root: Path,
    scene_id: str,
    step: str,
    review_json: Path,
    candidate: Path | None,
) -> list[str]:
    paths = [review_json, review_json.with_suffix(".md")]
    if step == "static-revision":
        paths.append(root / f"reviews/{scene_id}-review.md")
    paths.extend([candidate, root / f"scenes/{scene_id}.yaml", root / f"drafts/compositions/{scene_id}_composition_review.json"])
    result: list[str] = []
    for path in paths:
        if path is not None and path.is_file():
            relative = path.resolve().relative_to(root).as_posix()
            if relative not in result:
                result.append(relative)
    return result


def _revision_options() -> list[dict[str, str]]:
    return [
        {"id": "fix_logic_first", "label": "先修因果逻辑", "summary": "优先处理人物动机、剧情因果和 canon 冲突。"},
        {"id": "fix_style_first", "label": "先修文风和 AI 味", "summary": "优先处理句式、标点、节奏和文风偏移。"},
        {"id": "expand_scene", "label": "扩写场景", "summary": "在不灌水的前提下补足动作、冲突和读者回报。"},
        {"id": "ask_agent_compare", "label": "要求给出修订方案对比", "summary": "先让平台 Agent 提供多种修订策略再决定。"},
    ]


def _human_review_notes(review: dict[str, object]) -> list[str]:
    notes: list[str] = []
    human_resolutions = {"needs_human_review", "human_decision_required", "pending_user_decision"}
    for key in ("blocking_issues", "warnings", "revision_actions"):
        for item in _dict_rows(review.get(key)):
            if str(item.get("resolution") or "").strip().lower() in human_resolutions:
                note = str(item.get("description") or item.get("note") or "")
                if note:
                    notes.append(note)
    return notes


def _canon_patch_choice(root: Path, path: Path) -> dict[str, object] | None:
    payload = read_json_file(path)
    if not payload or payload.get("applied") or str(payload.get("canon_change", "unknown")).lower() == "false":
        return None
    scene_id = _safe_target_id(str(payload.get("scene_id") or path.stem.replace("_canon_patch", "")) or "canon")
    candidate_digest = file_sha256(path)
    approval = latest_approval_record(root, path.stem)
    if approval and str(approval.get("subject_sha256") or "").lower() == candidate_digest:
        return None
    patch_items = payload.get("items") if isinstance(payload.get("items"), list) else []
    return {
        "choice_id": _make_id("choice", "canon_patch_approval", scene_id), "route": "review-and-audit",
        "decision_type": "canon_patch_approval", "title": f"{scene_id} 有世界观写回候选",
        "summary": "这会影响后续场景的世界规则和事实边界。选择只记录审批意图，正式写入仍要走 canon-apply。",
        "target": {"scene_id": scene_id, "patch": _rel(path, root), "approval_run_id": path.stem, "candidate_sha256": candidate_digest},
        "source_paths": [_rel(path, root), _rel(path.with_suffix(".md"), root)],
        "recommended": "review_then_apply" if patch_items else "revise", "options": _canon_options(),
        "actions": ["记录 canon 审批"],
    }


def _state_patch_choice_from_path(root: Path, path: Path) -> dict[str, object] | None:
    scene_id = _safe_target_id(path.stem.replace("_state_patch", "") or "state")
    status = state_patch_writeback_status(root, scene_id)
    if status.get("status") != "needs_approval":
        return None
    candidate_digest = str(status.get("candidate_sha256") or file_sha256(path))
    return {
        "choice_id": _make_id("choice", "state_patch_confirmation", scene_id), "route": "scene-development",
        "decision_type": "state_patch_confirmation", "title": f"{scene_id} 有人物状态写回候选",
        "summary": "确认后，系统只会将已审查的人物状态、关系和弧光写回对应角色档案；不会写入 Canon。",
        "target": {"scene_id": scene_id, "patch": _rel(path, root), "approval_run_id": path.stem, "candidate_sha256": candidate_digest},
        "source_paths": [_rel(path, root), _rel(path.with_suffix(".md"), root), _rel(path.with_name(f"{scene_id}_state_patch_review.json"), root)],
        "recommended": "approve", "options": _state_options(), "actions": ["记录状态写回审批"],
    }


def _canon_options() -> list[dict[str, str]]:
    return [
        {"id": "approve", "label": "同意写回", "summary": "认可这批候选事实，后续仍需正式 apply。"},
        {"id": "revise", "label": "要求修改", "summary": "方向可以保留，但候选事实需要平台 Agent 重写。"},
        {"id": "reject", "label": "拒绝", "summary": "这批候选事实不应进入世界观。"},
    ]


def _state_options() -> list[dict[str, str]]:
    return [
        {"id": "approve", "label": "同意写回", "summary": "允许按已审查补丁写回人物状态。"},
        {"id": "revise", "label": "要求修改", "summary": "退回候选补丁，补充证据或收缩变化范围。"},
        {"id": "reject", "label": "拒绝", "summary": "不允许这批人物状态变化进入正式档案。"},
    ]


def _asset_candidates(candidate_id: str) -> tuple[str, ...]:
    return (
        f"characters/candidates/{candidate_id}.json",
        f"canon/candidates/world_rules/{candidate_id}.json",
        f"canon/candidates/locations/{candidate_id}.json",
        f"canon/candidates/organizations/{candidate_id}.json",
        f"plot/candidates/outlines/{candidate_id}.json",
        f"plot/candidates/chapters/{candidate_id}.json",
        f"plot/candidates/scenes/{candidate_id}.json",
    )


def _dict_rows(value: object) -> list[dict[str, object]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


__all__ = [
    "approval_choice", "asset_approval_source_paths", "asset_candidate_sha256", "branch_choice",
    "candidate_asset_alignment_choice", "canon_patch_choices", "direction_choice", "file_sha256",
    "latest_approval_record", "revision_direction_choice", "state_patch_choice", "state_patch_choices",
]
