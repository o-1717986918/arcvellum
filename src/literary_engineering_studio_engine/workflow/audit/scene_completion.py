"""State, canon, and mounted-style projections for scene audits."""
from __future__ import annotations

from pathlib import Path

from ...agent_tasks import agent_task_completion_status
from ...canon_evolver import canon_writeback_status
from ...character_state_apply import state_patch_writeback_status
from ...continuity_ledger import continuity_ledger_status, continuity_ledger_task_status
from ...route_audit_common import _add_gate
from ...route_audit_evidence import _mounted_style_exists, _style_adherence_status
from ...scene_handoff import scene_handoff_source_status


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
    state_status = state_patch_writeback_status(root, scene_id)
    state_status_value = str(state_status.get("status") or "")
    completion = agent_task_completion_status(state_task, root=root)
    review_not_required = state_status_value == "not_required"
    _add_gate(
        gates,
        f"{scene_id}:state-agent-task-complete",
        review_not_required or completion.get("complete") is True,
        "blocking",
        (
            f"{scene_id} state semantic review is not required for an empty durable patch"
            if review_not_required
            else f"{scene_id} state-evolve platform-agent task completed"
        ),
        (
            f"{scene_id} 的 state-evolve sidecar 未完成：{completion.get('message')}；"
            f"聚合写回状态：{state_status_value or 'missing'}"
        ),
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
    _add_continuity_and_handoff_gates(gates, root, scene_id)
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


def _add_continuity_and_handoff_gates(
    gates: list[dict[str, str]],
    root: Path,
    scene_id: str,
) -> None:
    delta_task_ok, delta_task_message = continuity_ledger_task_status(root, scene_id, review=False)
    review_task_ok, review_task_message = continuity_ledger_task_status(root, scene_id, review=True)
    ledger_ok, ledger_message, _payload = continuity_ledger_status(root, scene_id, require_review=True)
    apply_path = root / "plot" / "ledger_deltas" / f"{scene_id}_apply.json"
    handoff_ok, handoff_message, _handoff = scene_handoff_source_status(root, scene_id)
    checks = (
        ("continuity-ledger-agent-task", delta_task_ok, delta_task_message),
        ("continuity-ledger-review", review_task_ok and ledger_ok, review_task_message if not review_task_ok else ledger_message),
        ("continuity-ledger-apply", apply_path.is_file(), "continuity ledger apply receipt exists" if apply_path.is_file() else "continuity ledger apply receipt is missing"),
        ("scene-handoff", handoff_ok, handoff_message),
    )
    for key, passed, message in checks:
        _add_gate(
            gates,
            f"{scene_id}:{key}",
            passed,
            "blocking",
            f"{scene_id} {message}",
            f"{scene_id} {message}",
        )
