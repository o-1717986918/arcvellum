"""Formal scene-development task payload owner."""

from __future__ import annotations

from pathlib import Path
import re

from .context_contract import scene_context_contract
from ...tasking.state_contracts import SCENE_REVISION_STATES
from ...literary.review.chapter_obligation_machine import chapter_obligation_machine_contract
from ...literary.scene.promotion.historical_context import (
    historical_revision_reading_paths,
    historical_revision_source_paths,
)
from ...scene_route_blueprints import _blueprint_for_state
from ...scene_route_gates import (
    _candidate_review_gate_errors,
    _composition_gate_errors,
    _state_gate_validation,
)
from ...scene_route_support import _file_sha256, _static_review_conclusion, _unique
from ...semantic_task_contracts import semantic_artifact_contract
from ...task_paths import (
    TASK_SCHEMA,
    normalize_relative_path as _normalize_rel,
    now as _now,
    resolve_project_path as _resolve_project_path,
    task_id as _task_id,
)


def _build_task_payload(root: Path, route: str, scene_state: dict[str, object]) -> dict[str, object]:
    scene_id = str(scene_state.get("scene_id") or "")
    scene_rel = str(scene_state.get("scene") or f"scenes/{scene_id}.yaml")
    current_state = str(scene_state.get("current_step") or "")
    next_action = str(scene_state.get("next_action") or "")
    blueprint = _blueprint_for_state(root, scene_id, scene_rel, current_state, next_action)
    task_id = _task_id(route, scene_id, current_state)
    expected_outputs = _unique([_normalize_rel(item) for item in blueprint["expected_outputs"]])
    source_paths = _unique([_normalize_rel(item) for item in blueprint["source_paths"]])
    word_target, word_minimum, word_maximum = _scene_word_count_contract(root, scene_rel, blueprint)
    payload = {
        "schema": TASK_SCHEMA,
        "task_id": task_id,
        "status": "issued",
        "created_at": _now(),
        "route": route,
        "scene_id": scene_id,
        "scene": scene_rel,
        "current_state": current_state,
        "task_type": blueprint["task_type"],
        "prompt_asset_id": blueprint["prompt_asset_id"],
        "command": blueprint["command"],
        "required_reading": [
            "SKILL.md", "AGENTS.md", "agentread.yaml", "references/agent-run-protocol.md", "references/cli-run-protocol.md", "references/punctuation-standard.md",
        ],
        "source_paths": source_paths,
        "context_trace": blueprint.get("context_trace", ""),
        "hard_constraints": blueprint["hard_constraints"],
        "style_constraints": blueprint["style_constraints"],
        "word_count_target": word_target,
        "word_count_min": word_minimum,
        "word_count_max": word_maximum,
        "agent_source_paths": _agent_reading_paths(root, source_paths, current_state=current_state, scene_id=scene_id),
        "expected_outputs": expected_outputs,
        "submission_command": f"python -m literary_engineering_studio_engine task-submit <project> --task-id {task_id} --from <artifact>",
        "completion_command": f"python -m literary_engineering_studio_engine task-complete <project> --task-id {task_id}",
        "validation_gates": blueprint["validation_gates"],
        "forbidden_shortcuts": [
            "Do not hand-write same-named formal files to bypass the documented command.",
            "Do not use debug/bypass flags such as --allow-unreviewed, --allow-review-notes, --include-blocked, --allow-unapproved, --allow-missing-composition, --allow-unselected-composition, --allow-recommended-branch, or --allow-missing-branch.",
            "Do not treat this task as complete until task-submit and task-complete have succeeded.",
            "Do not let subagents draft, revise, polish, expand, or finalize creative body text.",
            "Do not write API keys or provider secrets into the work project.",
        ],
        "next_allowed_states": blueprint["next_allowed_states"],
    }
    _apply_blueprint_contracts(payload, blueprint, root, current_state, scene_id)
    payload.update(scene_context_contract(root, payload))
    return payload


def _apply_blueprint_contracts(
    payload: dict[str, object],
    blueprint: dict[str, object],
    root: Path,
    current_state: str,
    scene_id: str,
) -> None:
    for key in ("candidate", "revision_source"):
        if blueprint.get(key):
            payload[key] = blueprint[key]
    if blueprint.get("scene_character_assets"):
        payload["scene_character_assets"] = blueprint["scene_character_assets"]
    if blueprint.get("core_managed_outputs"):
        payload["core_managed_outputs"] = [str(item) for item in blueprint["core_managed_outputs"]]
    repair_targets = [str(item) for item in blueprint.get("repair_targets", []) if str(item).strip()]
    if repair_targets:
        payload["repair_targets"] = repair_targets
        payload["repair_target_sha256_before_revision"] = {
            relative: _file_sha256(path)
            for relative in repair_targets
            if (path := _resolve_project_path(root, relative)).is_file()
        }
    if current_state == "reader-experience-contract":
        payload["system_owned_fields"] = {
            "chapter_obligation": chapter_obligation_machine_contract(
                root, _scene_chapter_id(root, scene_id)
            )
        }
    semantic = semantic_artifact_contract(current_state, scene_id)
    if semantic is not None:
        payload["semantic_artifact"] = semantic
    if current_state in SCENE_REVISION_STATES and blueprint.get("revision_source"):
        source = _resolve_project_path(root, str(blueprint["revision_source"]))
        if source.is_file():
            payload["candidate_sha256_before_revision"] = _file_sha256(source)


def _scene_word_count_contract(root: Path, scene_rel: str, blueprint: dict[str, object]) -> tuple[int, int, int]:
    """Carry the formal scene budget into every task package.

    The CLI gate already reads these values from scene YAML.  Repeating them in
    the Agent contract keeps the writing task from seeing a meaningless zero
    while preserving any route-specific explicit override.
    """

    text = _resolve_project_path(root, scene_rel).read_text(encoding="utf-8", errors="ignore")

    def value(key: str, fallback: object) -> int:
        match = re.search(rf"(?m)^\s*{re.escape(key)}:\s*['\"]?([0-9][0-9,_]*)", text)
        raw = match.group(1) if match else fallback
        try:
            return max(0, int(str(raw or 0).replace(",", "").replace("_", "")))
        except (TypeError, ValueError):
            return 0

    return (
        value("word_count_target", blueprint.get("word_count_target", 0)),
        value("word_count_min", blueprint.get("word_count_min", 0)),
        value("word_count_max", blueprint.get("word_count_max", 0)),
    )


def _agent_reading_paths(root: Path, source_paths: list[str], *, current_state: str, scene_id: str) -> list[str]:
    """Separate CLI dependency staging from the main Agent's bounded reading list.

    Formal commands may need broad folders in their isolated workspace.  Those
    folders are implementation dependencies, not an invitation for a prose
    Agent to recursively inspect every world, character, or archive file.
    Context packets and the exact task artifacts carry the focused evidence.
    """

    prose_states = {
        "candidate-generation-provenance",
        "generation-agent-task",
        "candidate-review",
        "agent-review-task",
        *SCENE_REVISION_STATES,
        "static-review",
    }
    if current_state == "reader-experience-contract":
        return _reader_experience_reading_paths(root, scene_id)
    prose_minimum = {
        "project.yaml",
        f"scenes/{scene_id}.yaml",
        f"memory/context_packets/{scene_id}.md",
        f"memory/context_packets/{scene_id}.trace.json",
        f"branches/{scene_id}/roleplay_result.json",
        f"branches/{scene_id}/branch_manifest.json",
        f"branches/{scene_id}/branch_selection.md",
        f"drafts/compositions/{scene_id}_composition.md",
        f"drafts/compositions/{scene_id}_composition.json",
        f"drafts/compositions/{scene_id}_composition_review.json",
        "plot/outline.md",
        "plot/word_budget/word_budget.json",
        "plot/rhythm_plan.json",
        "style/creative_quality_profile.json",
        "style/style-profile.md",
    }
    if current_state == "candidate-review":
        return _candidate_review_reading_paths(root, source_paths, scene_id)

    if current_state in SCENE_REVISION_STATES:
        return _revision_reading_paths(root, source_paths, scene_id, current_state)

    if current_state in prose_states:
        scene_path = _resolve_project_path(root, f"scenes/{scene_id}.yaml")
        scene_text = scene_path.read_text(encoding="utf-8", errors="ignore") if scene_path.is_file() else ""
        chapter_match = re.search(r"(?m)^\s*(?:chapter_obligation_id|chapter_id):\s*['\"]?([^'\"\n#]+)", scene_text)
        if chapter_match:
            prose_minimum.add(f"plot/chapter_obligations/{chapter_match.group(1).strip().strip(chr(34)).strip(chr(39))}.json")
        return _unique([relative for relative in prose_minimum if (root / relative).is_file()])

    curated: list[str] = []
    for relative in source_paths:
        path = _resolve_project_path(root, relative)
        if path.is_dir():
            continue
        curated.append(relative)
    for relative in ("style/creative_quality_profile.json", "style/style-profile.md"):
        if (root / relative).is_file():
            curated.append(relative)
    return _unique(curated)


def _revision_reading_paths(
    root: Path,
    source_paths: list[str],
    scene_id: str,
    current_state: str,
) -> list[str]:
    """Expose revision inputs while keeping promotion proof machine-only."""

    historical_proof_paths = set(
        historical_revision_source_paths(
            root,
            scene_id,
            root / "drafts" / "scenes" / f"{scene_id}.md",
        )
    )
    archived_context_paths = set(
        historical_revision_reading_paths(
            root,
            scene_id,
            root / "drafts" / "scenes" / f"{scene_id}.md",
        )
    )
    historical_proof_paths.difference_update(archived_context_paths)
    revision_inputs = [
        relative
        for relative in source_paths
        if _is_revision_input(relative, scene_id, current_state)
        and relative not in historical_proof_paths
        and relative.endswith((".md", ".json"))
    ]
    minimum = [
        *revision_inputs,
        f"scenes/{scene_id}.yaml",
        f"drafts/compositions/{scene_id}_composition.md",
        f"drafts/compositions/{scene_id}_composition.json",
        f"drafts/compositions/{scene_id}_composition_review.json",
        f"branches/{scene_id}/branch_selection.md",
        *(
            sorted(archived_context_paths)
            if archived_context_paths
            else [
                f"memory/context_packets/{scene_id}.md",
                f"memory/context_packets/{scene_id}.trace.json",
            ]
        ),
        "plot/word_budget/word_budget.json",
        "plot/rhythm_plan.json",
        "style/creative_quality_profile.json",
        "style/style-profile.md",
    ]
    return _unique([relative for relative in minimum if (root / relative).is_file()])


def _candidate_review_reading_paths(root: Path, source_paths: list[str], scene_id: str) -> list[str]:
    candidates = [
        relative
        for relative in source_paths
        if relative.startswith(("drafts/candidates/", "drafts/revisions/"))
        and relative.endswith((".md", ".json"))
    ]
    required = [
        *candidates,
        f"scenes/{scene_id}.yaml",
        f"drafts/compositions/{scene_id}_composition_review.json",
        f"branches/{scene_id}/branch_selection.md",
        f"memory/context_packets/{scene_id}.md",
        f"memory/context_packets/{scene_id}.trace.json",
        "style/creative_quality_profile.json",
        "style/style-profile.md",
        "plot/word_budget/word_budget.json",
    ]
    return _unique([relative for relative in required if (root / relative).is_file()])


def _reader_experience_reading_paths(root: Path, scene_id: str) -> list[str]:
    chapter_id = _scene_chapter_id(root, scene_id)
    generated_scaffold = f"plot/chapter_obligations/{chapter_id}.json"
    candidates = [
        "project.yaml",
        "plot/word_budget/word_budget.json",
        generated_scaffold,
        *(
            _normalize_rel(path.relative_to(root))
            for path in sorted((root / "scenes").glob("*.yaml"))
            if _yaml_scalar(path, "chapter_id") == chapter_id
        ),
    ]
    return _unique(
        [
            relative
            for relative in candidates
            if relative == generated_scaffold or (root / relative).is_file()
        ]
    )


def _scene_chapter_id(root: Path, scene_id: str) -> str:
    return _yaml_scalar(root / "scenes" / f"{scene_id}.yaml", "chapter_id") or "chapter_0001"


def _yaml_scalar(path: Path, key: str) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore") if path.is_file() else ""
    match = re.search(rf"(?m)^\s*{re.escape(key)}:\s*['\"]?([^'\"\n#]+)", text)
    return match.group(1).strip().strip("\"'") if match else ""


def _is_revision_input(
    relative: str,
    scene_id: str,
    current_state: str,
) -> bool:
    if relative.startswith(
        (
            "drafts/candidates/",
            "drafts/revisions/",
            "drafts/scenes/",
            "reviews/agent/",
        )
    ) or relative == f"reviews/{scene_id}-review.md":
        return True
    return (
        current_state == "target-length-revision"
        and relative == "reviews/longform/target_length_repair.json"
    )


build_task_payload = _build_task_payload
blueprint_for_state = _blueprint_for_state
validate_task = _state_gate_validation
composition_gate_errors = _composition_gate_errors
candidate_review_gate_errors = _candidate_review_gate_errors
