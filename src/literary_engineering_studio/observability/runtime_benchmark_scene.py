"""Synthetic scene closure used by the runtime prose benchmark."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from ..contracts import TaskPackage
from ..runtime.engine_bridge import CoreBridge
from literary_engineering_studio_engine.public.tasking import (
    write_agent_completion_marker,
)
from literary_engineering_studio_engine.public.projections import (
    count_delivery_chars,
    count_delivery_chinese_content_chars,
)
from literary_engineering_studio_engine.public.tasking import (
    semantic_artifact_template,
)


_SCENE_ID = "scene_0001"
_SYNTHETIC_AGENT_STATES = {
    "roleplay-agent-task",
    "branch-agent-task",
    "composition-agent-task",
    "candidate-generation-provenance",
}


def seed_synthetic_scene(project: Path) -> None:
    """Populate the initialized scaffold before any route artifacts are issued."""

    # A cacheable formal trace needs identities for the empty canon-patch set
    # and the rhythm plan. Production projects acquire these naturally; the
    # compact benchmark fixture declares them explicitly.
    (project / "canon" / "patches").mkdir(parents=True, exist_ok=True)
    _write_json(
        project / "plot" / "rhythm_plan.json",
        {
            "schema": "literary-engineering-workbench/rhythm-plan/v1",
            "revision": 1,
            "entries": [],
        },
    )
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


def complete_synthetic_scene_task(
    project: Path,
    task: TaskPackage,
    *,
    bridge: CoreBridge,
) -> None:
    """Close semantic prerequisites needed to issue a real downstream Agent task."""

    handlers = {
        "roleplay-agent-task": lambda: _complete_roleplay(project),
        "branch-agent-task": lambda: _complete_branches(project),
        "composition-agent-task": lambda: _complete_composition(project),
        "candidate-generation-provenance": lambda: _complete_candidate_generation(
            project,
            task,
            bridge=bridge,
        ),
    }
    try:
        handlers[task.current_state]()
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


def _complete_candidate_generation(
    project: Path,
    task: TaskPackage,
    *,
    bridge: CoreBridge,
) -> None:
    """Create a controlled candidate while retaining formal CLI provenance.

    The benchmark is not testing prose quality here. It needs a stable,
    non-sensitive candidate so the authoritative route can issue the exact
    candidate-review contract used by production.
    """

    bridge.execute_task_command(task.command, project)
    candidate = project / "drafts" / "candidates" / f"{_SCENE_ID}-platform-agent.md"
    candidate.write_text(_benchmark_candidate_text(), encoding="utf-8")
    prompt_path = candidate.with_suffix(".prompt.json")
    prompt = _read_json(prompt_path)
    standards = prompt.get("generation_standards")
    standards = standards if isinstance(standards, dict) else {}
    rhythm = standards.get("narrative_rhythm_contract")
    rhythm = rhythm if isinstance(rhythm, dict) else {}
    reader = standards.get("reader_experience_contract")
    reader = reader if isinstance(reader, dict) else {}
    budget = standards.get("scene_word_budget_contract")
    budget = budget if isinstance(budget, dict) else {}
    body = candidate.read_text(encoding="utf-8")
    manifest = {
        "schema": "literary-engineering-workbench/scene-candidate/v1",
        "formal_contract_revision": "2026-07-23.3",
        "generated_by": "platform-agent",
        "provider": "benchmark-fixture",
        "candidate": candidate.relative_to(project).as_posix(),
        "writer_session_id": "benchmark-main-writer",
        "prompt_manifest": prompt_path.relative_to(project).as_posix(),
        "source_paths": [
            relative
            for relative in task.source_paths
            if (project / relative).is_file()
        ],
        "style_profile": str(prompt.get("style_profile") or ""),
        "context": str(prompt.get("context") or ""),
        "composition": str(prompt.get("composition") or ""),
        "style_mount_snapshot": prompt.get("style_mount_snapshot") or {},
        "creative_quality_profile_digest": str(
            standards.get("creative_quality_profile_digest") or ""
        ),
        "style_generation_standard_applied": True,
        "reader_experience_contract": reader,
        "reader_experience_standard_applied": True,
        "word_budget_standard_applied": False,
        "narrative_rhythm_contract": rhythm,
        "narrative_rhythm_standard_applied": True,
        "hard_constraints_applied": True,
        "anti_evasion_protocol_applied": True,
        "pass_with_notes_actions_applied": False,
        "word_budget_contract": budget,
        "clean_body_chinese_chars": count_delivery_chinese_content_chars(body),
        "clean_body_machine_chars": count_delivery_chars(body),
        "word_budget_adherence": {"status": "not_required"},
        "new_character_register": {
            "schema": "literary-engineering-workbench/new-character-register/v0.1",
            "status": "none",
            "introduced": [],
            "ephemeral_waivers": [],
            "blocking_issues": [],
        },
        "canon_writeback": {
            "canon_change": False,
            "no_canon_change_reason": "The benchmark candidate only exercises existing fixture facts.",
        },
        "blocking_issues": [],
    }
    _write_json(candidate.with_suffix(".json"), manifest)
    _mark_complete(
        project,
        f"drafts/candidates/{_SCENE_ID}-platform-agent.agent_tasks.md",
    )


def _benchmark_candidate_text() -> str:
    return """# 脱敏候选正文

## 正文候选

钟铺的门留着一道缝。守钟人推门进去，把提灯放在工作台边。铜屑贴着桌面，账册压在钟锤下面。昨夜的记录写着三更，墨迹已经干透。

他取下钟壳，先看摆轮，再量发条。齿轮没有裂口，调时螺钉上留着新鲜擦痕。有人在鸣钟前动过它，还把工具擦净放回原位。

街口传来车轮声。搬运账册的人到了门外。守钟人合上钟壳，抽出账册最末一页。他把缺失的钥匙编号记在纸角，然后将那页纸藏进袖中。

门被推开时，工作台已经收拾妥当。来人搬走账册，只看见一盏提灯和一座停摆的钟。守钟人等脚步离开，才从门后的灰尘里捡起半枚蜡印。

蜡印属于能接触内门的人。下一步要查清昨夜是谁领走了钥匙。

## 状态变化候选

- 守钟人确认鸣钟时间遭到人为调整。
- 缺失钥匙和半枚蜡印成为后续调查线索。

## 新角色候选登记

- 无。
"""


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
