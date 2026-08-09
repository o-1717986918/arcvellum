"""Synthetic scene closure used by the runtime prose benchmark."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from ..contracts import TaskPackage
from literary_engineering_studio_engine.tasking.agent_tasks.writer import (
    write_agent_completion_marker,
)
from literary_engineering_studio_engine.tasking.semantic_contracts import (
    semantic_artifact_template,
)


_SCENE_ID = "scene_0001"
_SYNTHETIC_AGENT_STATES = {
    "roleplay-agent-task",
    "branch-agent-task",
    "composition-agent-task",
}


def seed_synthetic_scene(project: Path) -> None:
    """Populate the initialized scaffold before any route artifacts are issued."""

    scene_path = project / "scenes" / f"{_SCENE_ID}.yaml"
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    payload = yaml.load(scene_path.read_text(encoding="utf-8"))
    payload.update(
        {
            "word_count_target": 1000,
            "word_count_min": 800,
            "word_count_max": 1200,
            "location": "clock shop",
            "scene_goal": "verify the early bell",
            "actions": ["inspect the clock", "compare the ledger"],
            "revealed_info": ["the bell was adjusted by hand"],
        }
    )
    payload["conflict"] = {
        "external": "the ledger is being removed",
        "internal": "the keeper fears accusing an ally",
    }
    payload["narrative_rhythm"] = {
        **dict(payload.get("narrative_rhythm") or {}),
        "scene_function": ["reveal"],
        "scene_turn": "evidence points inward",
        "reader_effect": "certainty becomes suspicion",
        "tension_curve": {"entry": 2, "peak": 4, "exit": 3},
    }
    payload["scene_bridge"] = {
        **dict(payload.get("scene_bridge") or {}),
        "incoming_pressure": "the bell rang early",
        "outgoing_hook": "who held the key",
    }
    output_state = dict(payload.get("output_state") or {})
    output_state["new_facts"] = ["the bell was adjusted"]
    output_state["next_hooks"] = ["find who held the key"]
    payload["output_state"] = output_state
    with scene_path.open("w", encoding="utf-8") as stream:
        yaml.dump(payload, stream)


def supports_synthetic_completion(task: TaskPackage) -> bool:
    return task.current_state in _SYNTHETIC_AGENT_STATES


def complete_synthetic_scene_task(project: Path, task: TaskPackage) -> None:
    """Close only the semantic prerequisites needed to issue the real prose task."""

    handlers = {
        "roleplay-agent-task": _complete_roleplay,
        "branch-agent-task": _complete_branches,
        "composition-agent-task": _complete_composition,
    }
    try:
        handlers[task.current_state](project)
    except KeyError as exc:
        raise ValueError(f"unsupported synthetic scene task: {task.current_state}") from exc


def _complete_roleplay(project: Path) -> None:
    relative = f"branches/{_SCENE_ID}/roleplay_simulation.md"
    payload = semantic_artifact_template("roleplay-agent-task", _SCENE_ID, source=relative)
    payload.update(
        {
            "status": "complete",
            "evidence_paths": [f"scenes/{_SCENE_ID}.yaml"],
            "findings": ["Pressure changes the next choice."],
            "character_actions": [{"action": "inspect the mechanism"}],
            "world_consequences": [{"impact": "the missing key matters"}],
            "branch_pressures": [{"pressure": "accuse or delay"}],
        }
    )
    _write_json(project / "branches" / _SCENE_ID / "roleplay_result.json", payload)
    _mark_complete(project, f"branches/{_SCENE_ID}/roleplay_simulation.agent_tasks.md")


def _complete_branches(project: Path) -> None:
    directory = project / "branches" / _SCENE_ID
    manifest = _read_json(directory / "branch_manifest.json")
    branch_count = int(manifest.get("branch_count") or 0)
    if branch_count < 1:
        raise ValueError("synthetic branch manifest has no branch slots")
    payload = semantic_artifact_template(
        "branch-agent-task",
        _SCENE_ID,
        source=f"branches/{_SCENE_ID}/branch_manifest.json",
    )
    payload.update(
        {
            "status": "complete",
            "evidence_paths": [
                f"branches/{_SCENE_ID}/roleplay_result.json",
                f"branches/{_SCENE_ID}/branch_manifest.json",
            ],
            "findings": ["Branches differ in cause, cost, and writeback."],
            "proposals": [_branch_proposal(index) for index in range(1, branch_count + 1)],
        }
    )
    _write_json(directory / "branch_proposals.json", payload)
    (directory / "branch_selection.md").write_text(
        "decision: selected\nselected_branch: agent_branch_1\n",
        encoding="utf-8",
    )
    _mark_complete(project, f"branches/{_SCENE_ID}/branch_manifest.agent_tasks.md")


def _branch_proposal(index: int) -> dict[str, Any]:
    alternating = index % 2 == 0
    beat_serves = (
        [["incoming_bridge", "cost"], ["goal", "reader_effect"], ["turn", "outgoing_hook"]]
        if alternating
        else [["incoming_bridge", "reader_effect"], ["goal", "outgoing_hook"], ["turn"], ["cost"]]
    )
    return {
        "branch_id": f"agent_branch_{index}",
        "title": f"branch {index}",
        "strategy": f"strategy {index}",
        "causal_premise": f"choice {index} changes evidence access.",
        "action_chain": [f"act {index}a", f"act {index}b", f"act {index}c"],
        "cost": f"cost {index} cannot be avoided",
        "reader_effect": f"reader effect {index}",
        "state_writeback": {
            "new_facts": [f"fact {index}"],
            "next_scene_inputs": [f"input {index}"],
        },
        "beat_plan": [
            {
                "beat_id": f"b{index}_{beat}",
                "function": f"phase {beat}",
                "visible_action": f"action b{index} {beat}",
                "causal_change": f"change b{index} {beat}",
                "pace": "measured" if beat == 1 else "accelerating",
                "detail_level": "standard" if beat == 1 else "expanded",
                "serves": serves,
            }
            for beat, serves in enumerate(beat_serves, start=1)
        ],
    }


def _complete_composition(project: Path) -> None:
    relative = f"drafts/compositions/{_SCENE_ID}_composition.json"
    source = project / relative
    payload = semantic_artifact_template("composition-agent-task", _SCENE_ID, source=relative)
    payload.update(
        {
            "status": "complete",
            "evidence_paths": [relative],
            "findings": ["Composition preserves the selected cause and cost."],
            "composition_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "verdict": "pass",
            "required_changes": [],
            "ready_for_generation": True,
        }
    )
    _write_json(
        project / "drafts" / "compositions" / f"{_SCENE_ID}_composition_review.json",
        payload,
    )
    _mark_complete(project, f"drafts/compositions/{_SCENE_ID}_composition.agent_tasks.md")


def _mark_complete(project: Path, relative: str) -> None:
    write_agent_completion_marker(project / relative, root=project, handled_by="benchmark-fixture")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
