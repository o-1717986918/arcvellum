"""Formal branch-selection interpretation for scene composition."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ....flow_gates import (
    FlowGateError,
    branch_selection_status,
    fallback_selection_reason_error,
    selected_branch_from,
)
from ....semantic_task_contracts import validated_branch_proposals
from ..facts import SceneFacts


def load_branch_choice(
    root: Path,
    scene_id: str,
    manifest: Path | None,
    selection: Path | None,
    allow_recommended_branch: bool,
    allow_missing_branch: bool,
) -> dict[str, Any]:
    manifest_path = _resolve(
        root, manifest, root / "branches" / scene_id / "branch_manifest.json"
    )
    selection_path = _resolve(
        root, selection, root / "branches" / scene_id / "branch_selection.md"
    )
    selection_gate = branch_selection_status(selection_path)
    selected = selected_branch_from(selection_path)
    if not manifest_path.exists():
        return _missing_manifest(
            root,
            scene_id,
            manifest_path,
            selection_path,
            selection_gate,
            allow_missing_branch,
        )
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    fallback_branches = data.get("branches", [])
    proposal_branches, proposal_path = _proposal_inputs(root, scene_id, data)
    recommended = str(data.get("recommended_branch") or "")
    target_id = _selected_id(
        root,
        selection_path,
        selected,
        recommended,
        allow_recommended_branch,
    )
    chosen = _find_branch([*proposal_branches, *fallback_branches], target_id)
    if target_id and chosen is None:
        raise FlowGateError(
            f"selected branch {target_id} is not present in {_relative(manifest_path, root)}; "
            "rerun branch-simulate or correct branch_selection.md."
        )
    if not chosen:
        return _empty_manifest(
            scene_id, target_id, manifest_path, selection_path, selection_gate, data
        )
    _ensure_fallback_allowed(
        selection_gate, target_id, proposal_branches, fallback_branches
    )
    return _selected_result(
        chosen,
        selected,
        manifest_path,
        selection_path,
        selection_gate,
        recommended,
        proposal_path,
    )


def fallback_writeback(facts: SceneFacts) -> dict[str, list[str]]:
    return {
        "new_facts": [f"{facts.scene_id} 的新增事实必须在正文生成后人工确认。"],
        "character_changes": ["人物状态变化先保持候选。"],
        "relationship_changes": ["关系变化先保持候选。"],
        "foreshadowing_changes": ["伏笔新增、加固或回收需进入审查清单。"],
        "next_scene_inputs": facts.next_hooks or ["补充下一场景输入。"],
    }


def _missing_manifest(
    root: Path,
    scene_id: str,
    manifest_path: Path,
    selection_path: Path,
    selection_gate: dict[str, str],
    allow_missing: bool,
) -> dict[str, Any]:
    if not allow_missing:
        raise FlowGateError(
            "branch simulation required before compose-scene: "
            f"missing {_relative(manifest_path, root)}. Run simulate-scene --agent, "
            "branch-simulate --agent, then record branch_selection.md before composing. "
            "For internal experiments only, pass allow_missing_branch=True or the CLI flag."
        )
    return {
        "branch_id": "",
        "title": "未加载分支",
        "strategy": "no_branch_manifest",
        "premise": "当前场景尚未生成 branch-simulate 产物，compose-scene 将使用场景目标和人物档案生成保守编排。",
        "action_chain": [],
        "scores": {},
        "status": "no_manifest",
        "source": "fallback",
        "manifest_path": manifest_path,
        "selection_path": selection_path if selection_path.exists() else None,
        "selection_gate": selection_gate,
        "risks": ["缺少 branch_manifest.json，剧情方向未经过多分支评分。"],
        "writeback_candidates": _fallback_writeback_by_id(scene_id),
    }


def _empty_manifest(
    scene_id: str,
    target_id: str,
    manifest_path: Path,
    selection_path: Path,
    selection_gate: dict[str, str],
    data: dict[str, Any],
) -> dict[str, Any]:
    return {
        "branch_id": target_id,
        "title": "空分支清单",
        "strategy": "empty_manifest",
        "premise": "branch_manifest.json 存在，但没有可用分支。",
        "action_chain": [],
        "scores": {},
        "status": "needs_detail",
        "source": "manifest_empty",
        "manifest_path": manifest_path,
        "selection_path": selection_path if selection_path.exists() else None,
        "selection_gate": selection_gate,
        "risks": ["branch_manifest.json 无分支。"],
        "writeback_candidates": data.get(
            "writeback_candidates", _fallback_writeback_by_id(scene_id)
        ),
    }


def _selected_id(
    root: Path,
    selection_path: Path,
    selected: str,
    recommended: str,
    allow_recommended: bool,
) -> str:
    if not selected and not allow_recommended:
        raise FlowGateError(
            "formal branch selection required before compose-scene: "
            f"fill {_relative(selection_path, root)} with decision: selected and "
            f"selected_branch. recommended_branch={recommended or 'n/a'} is only a scoring hint."
        )
    return selected or recommended


def _proposal_inputs(
    root: Path,
    scene_id: str,
    manifest: dict[str, Any],
) -> tuple[list[dict[str, Any]], Path | None]:
    try:
        return validated_branch_proposals(root, scene_id, manifest)
    except ValueError as exc:
        raise FlowGateError(str(exc)) from exc


def _ensure_fallback_allowed(
    selection: dict[str, str],
    selected: str,
    proposals: list[dict[str, Any]],
    fallbacks: list[Any],
) -> None:
    proposal_ids = {str(item.get("branch_id") or "") for item in proposals}
    fallback_ids = {
        str(item.get("branch_id") or "")
        for item in fallbacks
        if isinstance(item, dict)
    }
    error = fallback_selection_reason_error(
        selection, selected, proposal_ids, fallback_ids
    )
    if error:
        raise FlowGateError(error)


def _selected_result(
    chosen: dict[str, Any],
    selected: str,
    manifest_path: Path,
    selection_path: Path,
    selection_gate: dict[str, str],
    recommended: str,
    proposal_path: Path | None,
) -> dict[str, Any]:
    result = dict(chosen)
    origin = str(chosen.get("branch_origin") or "deterministic-fallback")
    reason = str(selection_gate.get("fallback_reason") or "").strip()
    if origin == "deterministic-fallback" and proposal_path is None:
        reason = "no-validated-agent-proposal"
    result.update(
        {
            "branch_origin": origin,
            "fallback_reason": reason if origin == "deterministic-fallback" else "",
            "validated_agent_proposals_available": proposal_path is not None,
            "source": "selection" if selected else "recommended",
            "manifest_path": manifest_path,
            "selection_path": selection_path if selection_path.exists() else None,
            "selection_gate": selection_gate,
            "recommended_branch": recommended,
            "proposal_path": proposal_path,
        }
    )
    return result


def _find_branch(branches: list[Any], branch_id: str) -> dict[str, Any] | None:
    return next(
        (
            branch
            for branch in branches
            if isinstance(branch, dict) and branch.get("branch_id") == branch_id
        ),
        None,
    )


def _fallback_writeback_by_id(scene_id: str) -> dict[str, list[str]]:
    return {
        "new_facts": [f"{scene_id} 的新增事实必须在正文生成后人工确认。"],
        "character_changes": ["人物状态变化先保持候选。"],
        "relationship_changes": ["关系变化先保持候选。"],
        "foreshadowing_changes": ["伏笔新增、加固或回收需进入审查清单。"],
        "next_scene_inputs": ["补充下一场景输入。"],
    }


def _resolve(root: Path, value: Path | None, default: Path) -> Path:
    if value is None:
        return default
    return value if value.is_absolute() else root / value


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


__all__ = ["fallback_writeback", "load_branch_choice"]
