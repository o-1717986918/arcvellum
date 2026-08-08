"""State, canon, and mounted-style projections for scene audits."""
from __future__ import annotations

from pathlib import Path

from ...agent_tasks import agent_task_completion_status
from ...canon_evolver import canon_writeback_status
from ...route_audit_common import _add_gate
from ...route_audit_evidence import _mounted_style_exists, _style_adherence_status


def add_scene_completion_gates(
    gates: list[dict[str, str]],
    root: Path,
    scene_id: str,
    review_payload: dict,
) -> None:
    """Project post-promotion state, canon, and mounted-style evidence."""

    state_patch_json = root / "characters" / "state_patches" / f"{scene_id}_state_patch.json"
    state_patch_report = root / "characters" / "state_patches" / f"{scene_id}_state_patch.md"
    state_task = state_patch_json.with_suffix(".agent_tasks.md")
    _add_gate(
        gates,
        f"{scene_id}:state-patch-json",
        state_patch_json.exists(),
        "blocking",
        f"{scene_id} state evolution JSON exists",
        f"{scene_id} 缺少 characters/state_patches/{scene_id}_state_patch.json；promote 后运行 state-evolve --agent-tasks。",
    )
    _add_gate(
        gates,
        f"{scene_id}:state-patch-report",
        state_patch_report.exists(),
        "blocking",
        f"{scene_id} state evolution report exists",
        f"{scene_id} 缺少 characters/state_patches/{scene_id}_state_patch.md；平台 Agent 需审查人物状态演化候选。",
    )
    completion = agent_task_completion_status(state_task, root=root)
    _add_gate(
        gates,
        f"{scene_id}:state-agent-task-complete",
        completion.get("complete") is True,
        "blocking",
        f"{scene_id} state-evolve platform-agent task completed",
        f"{scene_id} 的 state-evolve sidecar 未完成：{completion.get('message')}",
    )
    canon_status = canon_writeback_status(root, scene_id)
    _add_gate(
        gates,
        f"{scene_id}:canon-writeback",
        str(canon_status.get("status") or "") in {"pass", "not_required"},
        "blocking",
        f"{scene_id} canon writeback candidate/no-change gate passed",
        f"{scene_id} 的 canon 写回候选门禁未完成：{canon_status.get('message')}",
    )
    if _mounted_style_exists(root):
        style_status = _style_adherence_status(review_payload)
        _add_gate(
            gates,
            f"{scene_id}:style-adherence-review",
            style_status == "pass",
            "blocking",
            f"{scene_id} mounted style adherence reviewed",
            f"{scene_id} 已挂载文风，但 scene_review.v1 缺少 clean pass 的 style_adherence；当前状态：{style_status or 'missing'}。",
        )
