"""Shared workflow gates for formal creative handoffs."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agent_tasks import agent_task_completion_status


FORMAL_BRANCH_DECISIONS = {
    "select",
    "selected",
    "approve",
    "approved",
    "accept",
    "accepted",
    "merge",
    "merged",
    "hybrid",
}
PENDING_BRANCH_VALUES = {"", "none", "n/a", "pending", "todo", "待定"}


class FlowGateError(RuntimeError):
    """Raised when a workflow tries to cross a formal approval boundary."""


def branch_selection_status(path: Path) -> dict[str, str]:
    """Return a normalized status for a branch_selection.md file."""

    if not path.exists():
        return {
            "status": "missing",
            "decision": "",
            "selected_branch": "",
            "reviewer": "",
            "message": "branch_selection.md does not exist",
        }
    text = path.read_text(encoding="utf-8", errors="ignore")
    decision = _field(text, "decision").lower()
    selected = _field(text, "selected_branch")
    reviewer = _field(text, "reviewer")
    if selected.lower() in PENDING_BRANCH_VALUES:
        selected = ""
    if decision in PENDING_BRANCH_VALUES:
        decision = ""
    if selected and decision in FORMAL_BRANCH_DECISIONS:
        status = "selected"
        message = "formal branch selection is present"
    elif selected:
        status = "incomplete"
        message = "selected_branch is filled but decision is still pending or not formal"
    else:
        status = "pending"
        message = "selected_branch is empty"
    return {
        "status": status,
        "decision": decision,
        "selected_branch": selected,
        "reviewer": reviewer,
        "message": message,
    }


def selected_branch_from(path: Path) -> str:
    status = branch_selection_status(path)
    return status["selected_branch"] if status["status"] == "selected" else ""


def ensure_agent_task_completed(root: Path, task_path: Path, *, label: str) -> dict[str, object]:
    """Reject forward progress when a formal platform-agent sidecar is still pending."""

    state = agent_task_completion_status(task_path, root=root)
    if state.get("complete") is True:
        return state
    raise FlowGateError(
        f"formal platform-agent task must be completed before {label}: {state.get('message')}. "
        "Read the .agent_tasks.md file, perform the platform-agent work, write expected artifacts, "
        "then create the matching .agent_completion.json marker. Do not skip it by reading only the JSON/report artifact."
    )


def ensure_scene_pre_generation_tasks_completed(root: Path, scene_id: str) -> None:
    """Require completed RP/branch/composition sidecars before formal scene generation."""

    tasks = [
        (root / "branches" / scene_id / "roleplay_simulation.agent_tasks.md", "generate-scene"),
        (root / "branches" / scene_id / "branch_manifest.agent_tasks.md", "generate-scene"),
        (root / "drafts" / "compositions" / f"{scene_id}_composition.agent_tasks.md", "generate-scene"),
    ]
    for path, label in tasks:
        ensure_agent_task_completed(root, path, label=label)


def ensure_composition_ready_for_generation(
    root: Path,
    composition_path: Path | None,
    *,
    allow_unselected_composition: bool = False,
    allow_missing_composition: bool = False,
) -> dict[str, Any]:
    """Reject composition packets that have not crossed the branch-selection gate."""

    if composition_path is None:
        if allow_missing_composition:
            return {}
        raise FlowGateError(
            "formal scene composition required before generate-scene: "
            "run simulate-scene --agent, branch-simulate --agent, record branch_selection.md, "
            "then rebuild compose-scene. For internal experiments only, pass allow_missing_composition=True or the CLI flag."
        )
    if not composition_path.exists():
        if allow_missing_composition:
            return {}
        raise FlowGateError(
            f"formal scene composition required before generate-scene: {composition_path} does not exist. "
            "Run compose-scene after roleplay simulation, branch simulation, and formal branch selection."
        )
    json_path = composition_path if composition_path.suffix.lower() == ".json" else composition_path.with_suffix(".json")
    if not json_path.exists():
        raise FlowGateError(
            f"composition gate requires companion JSON before generation: {json_path}"
        )
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    source = str(payload.get("selection_source") or "")
    selected = str(payload.get("selected_branch") or "")
    flow_gate = payload.get("flow_gate", {}) if isinstance(payload.get("flow_gate"), dict) else {}
    ready = flow_gate.get("ready_for_generation")
    if allow_unselected_composition:
        return payload
    if source != "selection" or ready is False:
        rel = _rel(composition_path, root)
        raise FlowGateError(
            "formal branch selection required before generate-scene: "
            f"{rel} has selection_source={source or 'missing'} selected_branch={selected or 'none'}. "
            "Fill branch_selection.md with decision: selected and selected_branch, then rebuild compose-scene. "
            "For internal experiments only, pass allow_unselected_composition=True or the CLI flag."
        )
    provenance = payload.get("formal_cli_provenance")
    created_by = str(provenance.get("created_by") or "") if isinstance(provenance, dict) else ""
    if created_by != "compose-scene":
        rel = _rel(composition_path, root)
        raise FlowGateError(
            "CLI-generated composition required before formal generate-scene: "
            f"{rel} is missing formal_cli_provenance.created_by=compose-scene. "
            "Manual composition files are exploratory/debug-only and cannot satisfy the formal generation gate. "
            "Run compose-scene after context, simulate-scene --agent, branch-simulate --agent, and formal branch_selection.md."
        )
    return payload


def _field(text: str, name: str) -> str:
    match = re.search(rf"(?mi)^\s*-?\s*{re.escape(name)}:\s*`?([^`\n#]*)`?\s*$", text)
    if not match:
        return ""
    return match.group(1).strip().strip("`").strip()


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
