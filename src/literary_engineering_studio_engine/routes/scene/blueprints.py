"""Task blueprints for the formal scene-development route."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re

from ...scene_character_assets import scene_character_asset_requirements
from ...semantic_task_contracts import semantic_artifact_relative_path
from ...tasking.paths import read_json as _read_json
from ...task_paths import relative_path as _rel, resolve_project_path as _resolve_project_path
from ...workflow_state import current_scene_candidate
from ...scene_route_support import (
    _context_source_paths, _project_int, _project_scalar, _read_optional_json,
    _read_text, _unique,
)
from .writeback_blueprints import SceneWritebackContext, writeback_blueprint_for_state


def _branch_proposal_count(root: Path, scene_id: str) -> int:
    """Return the exact count already issued by the branch manifest.

    The Creative Policy Graph may choose any supported count.  Downstream
    task prose must repeat that decision instead of publishing a conflicting
    range that invites the Worker to guess.
    """

    payload, _error = _read_optional_json(
        root / "branches" / scene_id / "branch_manifest.json"
    )
    try:
        count = int(payload.get("branch_count") or 0)
    except (TypeError, ValueError):
        return 0
    return count if 2 <= count <= 5 else 0


def _state_patch_character_files(root: Path, state_patch: str) -> list[str]:
    """Return the existing, in-project character files a state apply may mutate.

    ``state-apply`` is deterministic, but it is still a multi-file write: the
    patch receipt is not the only output.  Its target character records must be
    staged into the control workspace and declared for atomic writeback too.
    Never trust a patch path outside ``characters/`` or outside the project.
    The apply command remains responsible for reporting malformed/missing
    records; this helper only describes files that can safely cross the sandbox
    boundary.
    """

    patch_path = root / f"{state_patch}.json"
    if not patch_path.is_file():
        return []
    payload = _read_json(patch_path)
    character_files: list[str] = []
    for item in payload.get("characters") or []:
        if not isinstance(item, dict):
            continue
        raw_path = str(item.get("file") or "").replace("\\", "/").strip()
        if not raw_path:
            character_id = str(item.get("character_id") or "").strip()
            raw_path = f"characters/{character_id}.yaml" if character_id else ""
        if not raw_path:
            continue
        candidate = _resolve_project_path(root, raw_path)
        try:
            relative = candidate.resolve().relative_to(root.resolve()).as_posix()
        except (OSError, ValueError):
            continue
        if not relative.startswith("characters/") or not candidate.is_file():
            continue
        character_files.append(relative)
    return _unique(character_files)


def _matching_revision_choice_sources(
    root: Path,
    scene_id: str,
    revision_source: str,
) -> list[str]:
    """Return only consumed revision choices bound to the exact source body."""

    source = _resolve_project_path(root, revision_source)
    if not source.is_file():
        return []
    source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    choices = root / "workflow" / "human_choices"
    matches: list[tuple[int, str]] = []
    for path in choices.glob("choice.revision_direction.*.json") if choices.is_dir() else ():
        payload = _read_json(path)
        target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
        if payload.get("consumed") is not True:
            continue
        if str(payload.get("decision_type") or "") != "revision_direction":
            continue
        if str(target.get("target_id") or "") != scene_id:
            continue
        if str(target.get("candidate_path") or "").replace("\\", "/") != revision_source:
            continue
        if str(target.get("candidate_sha256") or "").lower() != source_sha256:
            continue
        matches.append((path.stat().st_mtime_ns, _rel(path, root)))
    return [max(matches)[1]] if matches else []


def _next_revision_base(root: Path, scene_id: str, revision_source: str) -> str:
    """Allocate an immutable revision artifact set for the exact source."""

    first = f"drafts/revisions/{scene_id}_revision"
    normalized = revision_source.replace("\\", "/")
    if not normalized.startswith("drafts/revisions/") and not (root / f"{first}.md").exists():
        return first
    highest = 1 if (root / f"{first}.md").exists() else 0
    folder = root / "drafts" / "revisions"
    pattern = re.compile(rf"^{re.escape(scene_id)}_revision_(\d+)[.]md$")
    for path in folder.glob(f"{scene_id}_revision_*.md") if folder.is_dir() else ():
        match = pattern.match(path.name)
        if match:
            highest = max(highest, int(match.group(1)))
    return f"drafts/revisions/{scene_id}_revision_{highest + 1:02d}"


def _blueprint_for_state(root: Path, scene_id: str, scene_rel: str, current_state: str, next_action: str) -> dict[str, object]:
    scene_path = _resolve_project_path(root, scene_rel)
    scene_text = _read_text(scene_path)
    chapter_match = re.search(r"(?m)^[ \t]*chapter_obligation_id:[ \t]*['\"]?([^'\"\n#]+)", scene_text) or re.search(
        r"(?m)^[ \t]*chapter_id:[ \t]*['\"]?([^'\"\n#]+)", scene_text
    )
    chapter_id = chapter_match.group(1).strip().strip("\"'") if chapter_match else "chapter_0001"
    context = f"memory/context_packets/{scene_id}.md"
    context_trace = f"memory/context_packets/{scene_id}.trace.json"
    branch_dir = f"branches/{scene_id}"
    branch_proposal_count = _branch_proposal_count(root, scene_id)
    branch_count_rule = (
        f"Write exactly {branch_proposal_count} scene-specific proposals, matching branch_manifest.json branch_count."
        if branch_proposal_count
        else "Write the exact proposal count declared by branch_manifest.json; do not infer a range."
    )
    composition = f"drafts/compositions/{scene_id}_composition"
    current_candidate = current_scene_candidate(root, scene_id)
    candidate_markdown = (
        _rel(current_candidate, root)
        if current_candidate is not None
        else f"drafts/candidates/{scene_id}-platform-agent.md"
    )
    candidate = candidate_markdown[:-3] if candidate_markdown.endswith(".md") else candidate_markdown
    review = f"reviews/agent/{scene_id}_scene_review"
    review_path = root / f"{review}.json"
    review_payload = _read_json(review_path) if review_path.is_file() else {}
    revision_source = str(
        review_payload.get("candidate")
        or review_payload.get("reviewed_candidate")
        or review_payload.get("draft")
        or f"{candidate}.md"
    ).replace("\\", "/")
    if Path(revision_source).is_absolute():
        revision_source = _rel(Path(revision_source), root)
    if current_state == "static-revision":
        revision_source = f"drafts/scenes/{scene_id}.md"
    revision = _next_revision_base(root, scene_id, revision_source)
    state_patch = f"characters/state_patches/{scene_id}_state_patch"
    state_patch_character_files = _state_patch_character_files(root, state_patch)
    state_apply = f"characters/state_patches/{scene_id}_state_apply"
    canon_patch = f"canon/patches/{scene_id}_canon_patch"
    canon_formal_sources = [
        relative
        for relative in (
            "canon/facts.json",
            "canon/forbidden_changes.yaml",
            "canon/locations.yaml",
            "canon/organizations.yaml",
            "canon/timeline.yaml",
            "canon/world_rules.yaml",
        )
        if (root / relative).is_file()
    ]
    direction_sources = _matching_revision_choice_sources(
        root,
        scene_id,
        revision_source,
    )
    common_sources = [scene_rel]
    context_sources = _context_source_paths(root, scene_rel)
    roleplay_task = f"{branch_dir}/roleplay_simulation.agent_tasks.md"
    roleplay_completion = f"{branch_dir}/roleplay_simulation.agent_completion.json"
    roleplay_result = semantic_artifact_relative_path("roleplay-agent-task", scene_id)
    branch_task = f"{branch_dir}/branch_manifest.agent_tasks.md"
    branch_completion = f"{branch_dir}/branch_manifest.agent_completion.json"
    composition_task = f"{composition}.agent_tasks.md"
    composition_completion = f"{composition}.agent_completion.json"
    composition_review = semantic_artifact_relative_path("composition-agent-task", scene_id)
    state_review = semantic_artifact_relative_path("state-agent-task", scene_id)
    canon_review = semantic_artifact_relative_path("canon-agent-task", scene_id)
    ledger_delta = f"plot/ledger_deltas/{scene_id}.json"
    ledger_task = f"plot/ledger_deltas/{scene_id}.agent_tasks.md"
    ledger_review = f"reviews/continuity/{scene_id}_ledger_review.json"
    ledger_review_task = f"reviews/continuity/{scene_id}_ledger_review.agent_tasks.md"
    chapter_contract_sources = [
        f"plot/chapter_obligations/{chapter_id}.json",
        f"plot/chapter_obligations/{chapter_id}.md",
        f"plot/chapter_obligations/{chapter_id}.agent_tasks.md",
        f"plot/chapter_obligations/{chapter_id}.agent_completion.json",
        "plot/rhythm_plan.json",
    ]
    # These are not decorative planning artifacts: generate-scene verifies the
    # budget sidecar and its review before creating a prose task.  Carry the
    # evidence into the sandbox so a controlled worker observes the same gate
    # result as the project root.
    longform_budget_evidence_sources = [
        "plot/word_budget/word_budget.agent_tasks.md",
        "plot/word_budget/word_budget.agent_completion.json",
        "plot/word_budget/scene_inventory_expansion.agent_tasks.md",
        "plot/word_budget/scene_inventory_expansion.agent_completion.json",
        "reviews/word_budget/word_budget_review.md",
        "reviews/word_budget/scene_inventory_review.md",
        "reviews/word_budget/chapter_obligation_review.md",
    ]
    scene_runtime_sources = list(
        dict.fromkeys(
            [
                *context_sources,
                # Formal longform materialization and word-budget gates inspect
                # the complete scene inventory. This is control-workspace-only;
                # definition.py still limits the Agent reading set.
                "scenes",
                context,
                context_trace,
                *chapter_contract_sources,
                *longform_budget_evidence_sources,
            ]
        )
    )
    scene_character_assets = scene_character_asset_requirements(root, scene_path)
    scene_character_asset_tasks = [
        _rel(requirement.task_path, root)
        for requirement in scene_character_assets
    ]
    writeback = writeback_blueprint_for_state(
        current_state,
        SceneWritebackContext(
            scene_id=scene_id,
            scene_rel=scene_rel,
            context=context,
            context_trace=context_trace,
            scene_runtime_sources=tuple(scene_runtime_sources),
            state_patch=state_patch,
            state_patch_character_files=tuple(state_patch_character_files),
            state_apply=state_apply,
            state_review=state_review,
            canon_patch=canon_patch,
            canon_review=canon_review,
            canon_formal_sources=tuple(canon_formal_sources),
            review=review,
            ledger_delta=ledger_delta,
            ledger_task=ledger_task,
            ledger_review=ledger_review,
            ledger_review_task=ledger_review_task,
        ),
    )
    table: dict[str, dict[str, object]] = {
        "scene-character-asset-tasks": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.scene-development.character-assets.prepare.v1",
            "command": f"python -m literary_engineering_studio_engine prepare-scene-character-assets <project> --scene {scene_rel}",
            "source_paths": [scene_rel, "characters", "canon", "plot/outline.md"],
            "expected_outputs": scene_character_asset_tasks,
            "hard_constraints": [
                "Run the documented preparation command; it emits candidate task contracts only and never invents or promotes characters.",
                "Do not begin context, roleplay, composition, or prose while a durable named participant lacks a reviewed and promoted formal character asset.",
                "After this task completes, continue through character-and-world-assets until every dependency is promoted.",
            ],
            "style_constraints": [],
            "validation_gates": ["every unresolved named participant has a CLI-owned candidate-asset task sidecar"],
            "next_allowed_states": ["scene-character-asset-dependency", "context-packet"],
            "scene_character_assets": [item.as_dict(root) for item in scene_character_assets],
        },
        "scene-character-asset-dependency": {
            "task_type": "route-dependency",
            "prompt_asset_id": "route.scene-development.character-assets.prepare.v1",
            "command": "",
            "source_paths": [scene_rel, *scene_character_asset_tasks],
            "expected_outputs": [],
            "hard_constraints": [
                "Do not execute scene work while character candidate assets remain pending.",
                "Switch to character-and-world-assets and complete creation, independent review, approval, and promotion for every listed participant.",
            ],
            "style_constraints": [],
            "validation_gates": ["all durable named participants resolve to promoted formal character assets"],
            "next_allowed_states": ["character-and-world-assets", "context-packet"],
            "scene_character_assets": [item.as_dict(root) for item in scene_character_assets],
        },
        "context-packet": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.scene-development.context.v1",
            "command": f"python -m literary_engineering_studio_engine context <project> --scene {scene_rel}",
            "source_paths": context_sources,
            "context_trace": context_trace,
            "expected_outputs": [context, context_trace, "memory/index.json"],
            "hard_constraints": ["Run the documented context command; inspect both the context packet and context trace before submitting."],
            "style_constraints": [],
            "validation_gates": ["context packet exists", "context trace exists and validates loaded source groups"],
            "next_allowed_states": ["roleplay-simulation"],
        },
        "context-trace": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.scene-development.context.trace.v1",
            "command": f"python -m literary_engineering_studio_engine context <project> --scene {scene_rel}",
            "source_paths": list(dict.fromkeys([*context_sources, context])),
            "context_trace": context_trace,
            "expected_outputs": [context, context_trace, "memory/index.json"],
            "hard_constraints": [
                "The existing context packet is not formal without its context trace.",
                "Rerun the documented context command and inspect the trace before moving to roleplay.",
            ],
            "style_constraints": [],
            "validation_gates": ["context trace exists", "context trace validates loaded source groups"],
            "next_allowed_states": ["roleplay-simulation"],
        },
        "roleplay-simulation": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.scene-development.roleplay.prepare.v1",
            "command": f"python -m literary_engineering_studio_engine simulate-scene <project> --scene {scene_rel} --agent",
            "source_paths": scene_runtime_sources,
            "context_trace": context_trace,
            "expected_outputs": [f"{branch_dir}/roleplay_simulation.md", f"{branch_dir}/roleplay_simulation.agent_tasks.md", roleplay_result],
            "hard_constraints": ["Use --agent so the platform-agent RP task is emitted as a sidecar."],
            "style_constraints": [],
            "validation_gates": ["roleplay simulation exists", "roleplay sidecar exists"],
            "next_allowed_states": ["roleplay-agent-task"],
        },
        "roleplay-agent-task": {
            "task_type": "platform-agent-judgment",
            "prompt_asset_id": "route.scene-development.roleplay.execute.v1",
            "command": "",
            "source_paths": [scene_rel, context, context_trace, f"{branch_dir}/roleplay_simulation.md", f"{branch_dir}/roleplay_simulation.agent_tasks.md", roleplay_result],
            "context_trace": context_trace,
            "expected_outputs": [roleplay_result, f"{branch_dir}/roleplay_simulation.agent_completion.json"],
            "hard_constraints": [
                "Read the roleplay sidecar and write roleplay/world/branch/canon/writeback reasoning into the schema-valid roleplay_result.json semantic artifact.",
                "Create the original roleplay_simulation.agent_completion.json before continuing.",
            ],
            "style_constraints": [],
            "validation_gates": ["roleplay sidecar completion marker exists", "roleplay_result.v1 semantic artifact passes and is non-placeholder"],
            "next_allowed_states": ["branch-manifest"],
        },
        "branch-manifest": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.scene-development.branch.prepare.v1",
            "command": f"python -m literary_engineering_studio_engine branch-simulate <project> --scene {scene_rel} --agent",
            "source_paths": list(dict.fromkeys([
                *scene_runtime_sources,
                f"{branch_dir}/roleplay_simulation.md",
                roleplay_task,
                roleplay_completion,
                roleplay_result,
            ])),
            "context_trace": context_trace,
            "expected_outputs": [
                f"{branch_dir}/branch_simulation.md",
                f"{branch_dir}/branch_manifest.json",
                f"{branch_dir}/branch_manifest.agent_tasks.md",
                f"{branch_dir}/branch_selection.md",
            ],
            "hard_constraints": ["Use --agent so branch review and selection tasks are emitted."],
            "style_constraints": [],
            "validation_gates": ["branch manifest exists", "branch sidecar exists"],
            "next_allowed_states": ["branch-agent-task"],
        },
        "branch-agent-task": {
            "task_type": "platform-agent-judgment",
            "prompt_asset_id": "route.scene-development.branch.execute.v1",
            "command": "",
            "source_paths": [scene_rel, context, context_trace, roleplay_result, f"{branch_dir}/branch_simulation.md", f"{branch_dir}/branch_manifest.json", f"{branch_dir}/branch_manifest.agent_tasks.md", f"{branch_dir}/branch_proposals.json"],
            "context_trace": context_trace,
            "expected_outputs": [f"{branch_dir}/branch_proposals.json", f"{branch_dir}/branch_selection.md", f"{branch_dir}/branch_manifest.agent_completion.json"],
            "hard_constraints": [
                f"{branch_count_rule} Write them to branch_proposals.json before selecting; each must change causality, action, cost, reader effect, and state writeback rather than rename a fallback archetype.",
                "Keep each alternative economical: normally use the two-beat scaffold, and use a third beat only when the causal turn cannot be represented clearly in two; a beat may serve several named obligations.",
                "Use agent_branch_<slug> ids, write a formal selected decision, and let the Worker create the completion receipt only after deterministic preflight passes.",
            ],
            "style_constraints": [],
            "validation_gates": ["branch_proposals.v1 semantic artifact passes", "branch_selection.md exists", "branch sidecar completion marker exists"],
            "next_allowed_states": ["branch-selection"],
        },
        "branch-selection": {
            "task_type": "platform-agent-judgment",
            "prompt_asset_id": "route.scene-development.branch.selection.v1",
            "command": "",
            "source_paths": [scene_rel, f"{branch_dir}/branch_manifest.json", f"{branch_dir}/branch_proposals.json", f"{branch_dir}/branch_selection.md"],
            "expected_outputs": [f"{branch_dir}/branch_selection.md"],
            "hard_constraints": ["branch_selection.md must contain decision: selected and selected_branch before composition."],
            "style_constraints": [],
            "validation_gates": ["branch_selection_status == selected"],
            "next_allowed_states": ["composition-json"],
        },
        "composition-json": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.scene-development.composition.prepare.v1",
            "command": f"python -m literary_engineering_studio_engine compose-scene <project> --scene {scene_rel} --agent-tasks",
            "source_paths": list(dict.fromkeys([
                *scene_runtime_sources,
                f"{branch_dir}/branch_manifest.json",
                f"{branch_dir}/branch_proposals.json",
                f"{branch_dir}/branch_selection.md",
                branch_task,
                branch_completion,
                roleplay_result,
            ])),
            "context_trace": context_trace,
            "expected_outputs": [f"{composition}.md", f"{composition}.json", f"{composition}.agent_tasks.md", composition_review],
            "hard_constraints": ["Composition must use formal branch_selection and created_by=compose-scene provenance."],
            "style_constraints": [],
            "validation_gates": ["composition JSON exists", "composition sidecar exists"],
            "next_allowed_states": ["composition-agent-task"],
        },
        "composition-agent-task": {
            "task_type": "platform-agent-judgment",
            "prompt_asset_id": "route.scene-development.composition.review.execute.v1",
            "command": "",
            "source_paths": list(dict.fromkeys([
                *scene_runtime_sources,
                f"{composition}.md",
                f"{composition}.json",
                f"{composition}.agent_tasks.md",
                composition_review,
            ])),
            "context_trace": context_trace,
            "expected_outputs": [composition_review, f"{composition}.agent_completion.json"],
            "hard_constraints": [
                "Read the composition sidecar and write the schema-valid composition review with the exact source digest.",
                "The Studio Worker materializes the lifecycle receipt only after deterministic preflight accepts the review.",
            ],
            "style_constraints": [],
            "validation_gates": ["composition sidecar completion marker exists", "composition_review.v1 semantic artifact passes and declares generation readiness"],
            "next_allowed_states": ["scene-word-budget-contract"],
        },
        "scene-word-budget-contract": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.longform-planning.scene-budget.v1",
            "command": "",
            "source_paths": [scene_rel, context, context_trace, "project.yaml", "plot/word_budget/word_budget.json"],
            "context_trace": context_trace,
            "expected_outputs": ["plot/word_budget/word_budget.json"],
            "hard_constraints": [
                "This state validates the existing formal longform budget; create or repair the budget through the longform-planning route.",
                "Longform scenes must carry word_count_target/min/max before formal generation.",
            ],
            "style_constraints": [],
            "validation_gates": ["scene word budget contract passes or is not required"],
            "next_allowed_states": ["reader-experience-contract"],
        },
        "reader-experience-contract": {
            "task_type": "deterministic-cli-plus-platform-review",
            "prompt_asset_id": "route.longform-planning.reader-experience.v1",
            "command": f"python -m literary_engineering_studio_engine chapter-obligation <project> --chapter-id {chapter_id}",
            "source_paths": list(
                dict.fromkeys(
                    [
                        *scene_runtime_sources,
                        "scenes",
                        "plot/word_budget/word_budget.json",
                        "plot/chapter_obligations/",
                    ]
                )
            ),
            "context_trace": context_trace,
            "expected_outputs": [
                f"plot/chapter_obligations/{chapter_id}.json",
                f"plot/chapter_obligations/{chapter_id}.md",
                f"plot/chapter_obligations/{chapter_id}.agent_tasks.md",
                f"plot/chapter_obligations/{chapter_id}.agent_completion.json",
            ],
            "core_managed_outputs": [
                f"plot/chapter_obligations/{chapter_id}.md",
                f"plot/chapter_obligations/{chapter_id}.agent_tasks.md",
            ],
            "hard_constraints": [
                "Longform scenes must have a ready chapter obligation and reader-experience contract before prose generation.",
                "The platform agent must fill reader_question, promised_reward, withheld_information, payoff_or_delay, emotional_curve, tension_source, curiosity_hook, freshness_requirement, anti_summary_requirement, and reader_aftertaste for this scene.",
                "Write only the authoritative chapter obligation JSON; Studio renders the Markdown mirror and lifecycle evidence.",
            ],
            "style_constraints": ["Do not turn reader-experience notes into visible workflow text inside prose."],
            "validation_gates": ["reader-experience contract passes or is not required"],
            "next_allowed_states": ["scene-rhythm-contract"],
        },
        "scene-rhythm-contract": {
            "task_type": "platform-agent-judgment",
            "prompt_asset_id": "route.scene-development.rhythm.contract.v1",
            "command": "",
            "source_paths": list(
                dict.fromkeys(
                    [
                        *scene_runtime_sources,
                        "scenes",
                        "plot/rhythm_plan.json",
                        f"plot/chapter_obligations/{chapter_id}.json",
                    ]
                )
            ),
            "context_trace": context_trace,
            "expected_outputs": [scene_rel],
            "hard_constraints": [
                "Write explicit narrative_rhythm.tension_curve entry/peak/exit values from 1 to 5 and scene_bridge.incoming_pressure.",
                "Preserve scene facts and do not draft prose, alter canon, or create a branch decision in this task.",
                "For an opening scene, document its baseline pressure rather than leaving incoming_pressure blank.",
            ],
            "style_constraints": ["Specify uneven pacing through scene function, density, turn, and bridge; avoid a uniform high-pressure rhythm."],
            "validation_gates": ["narrative rhythm/bridge contract passes"],
            "next_allowed_states": ["composition-json"],
        },
        "candidate-generation-provenance": {
            "task_type": "main-platform-agent-prose",
            "prompt_asset_id": "route.scene-development.prose.generate.v1",
            "command": f"python -m literary_engineering_studio_engine generate-scene <project> --scene {scene_rel} --out {candidate}.md --materialization-scope scene",
            "source_paths": list(
                dict.fromkeys(
                    [
                        *scene_runtime_sources,
                        f"{composition}.md",
                        f"{composition}.json",
                        roleplay_task,
                        roleplay_completion,
                        roleplay_result,
                        branch_task,
                        branch_completion,
                        composition_task,
                        composition_completion,
                        composition_review,
                        f"{branch_dir}/branch_selection.md",
                    ]
                )
            ),
            "context_trace": context_trace,
            "expected_outputs": [
                f"{candidate}.md",
                f"{candidate}.json",
                f"{candidate}.prompt.json",
                f"{candidate}.agent_tasks.md",
                f"{candidate}.agent_completion.json",
            ],
            "hard_constraints": [
                "Studio has already run generate-scene in the isolated workspace. Read its prompt manifest and sidecar; then the main platform agent personally writes the candidate body. Do not run CLI commands in this task.",
                "The candidate must not be drafted by a subagent and must not include workflow traces.",
                "All declared durable participants must already resolve to formal character assets. Do not create planned character candidates from this prose task; record only genuinely prose-introduced characters through new_character_register.",
            ],
            "style_constraints": [
                "Apply mounted Style Skill first at expression level.",
                "Apply punctuation standard, Style Lint Gate, and anti-evasion rules before submitting.",
            ],
            "validation_gates": ["candidate Markdown exists", "candidate manifest exists", "prompt manifest exists", "generation sidecar completion marker exists"],
            "next_allowed_states": ["generation-agent-task", "candidate-review"],
            "core_managed_outputs": [
                f"{candidate}.prompt.json",
                f"{candidate}.agent_tasks.md",
            ],
        },
        "generation-agent-task": {
            "task_type": "main-platform-agent-prose",
            "prompt_asset_id": "route.scene-development.prose.complete.v1",
            "command": "",
            "source_paths": [scene_rel, context, context_trace, f"{candidate}.prompt.json", f"{candidate}.agent_tasks.md"],
            "context_trace": context_trace,
            "expected_outputs": [f"{candidate}.md", f"{candidate}.json", f"{candidate}.agent_completion.json"],
            "hard_constraints": ["Complete the generate-scene sidecar after candidate Markdown and manifest are checked."],
            "style_constraints": ["Candidate must satisfy style, punctuation, word budget, and anti-evasion protocol before completion."],
            "validation_gates": ["generation sidecar completion marker exists"],
            "next_allowed_states": ["candidate-review"],
        },
        "candidate-review": {
            "task_type": "platform-agent-review",
            "prompt_asset_id": "route.scene-development.agent-review.v1",
            "command": f"python -m literary_engineering_studio_engine agent-review-scene <project> --scene {scene_rel} --draft {candidate}.md --materialization-scope scene",
            "candidate": f"{candidate}.md",
            "source_paths": list(
                dict.fromkeys(
                    [
                        *scene_runtime_sources,
                        f"{candidate}.md",
                        f"{candidate}.json",
                    ]
                )
            ),
            "context_trace": context_trace,
            "expected_outputs": [f"{review}.json", f"{review}.md", f"{review}.agent_tasks.md", f"{review}.context.json", f"{review}.agent_completion.json"],
            "core_managed_outputs": [f"{review}.agent_tasks.md", f"{review}.context.json"],
            "hard_constraints": [
                "Review the exact candidate path. pass_with_notes and actionable findings block promotion; low/info observations explicitly marked blocks_pass=false remain evidence under a clean pass and must not manufacture revision work.",
                "A non-pass verdict is a valid completed review and must remain available to the formal candidate-revision task.",
                "Do not edit prose in this review task and do not soften findings to make the route advance.",
            ],
            "style_constraints": ["Handle deterministic Style Lint evidence and anti-evasion risks explicitly."],
            "validation_gates": ["scene_review.v1 JSON exists", "review cites exact candidate", "review conclusion is recorded", "new_character_register is recorded"],
            "next_allowed_states": ["candidate-revision", "agent-review-task", "promotion-manifest"],
        },
        "candidate-revision": {
            "task_type": "platform-agent-revision",
            "prompt_asset_id": "route.scene-development.revision.v1",
            "command": (
                f"python -m literary_engineering_studio_engine revise-scene <project> --scene {scene_rel} "
                f"--draft {revision_source} --review {review}.json --out {revision}.md "
                f"--report-out {revision}_report.md --manifest-out {revision}.json "
                f"--prompt-manifest-out {revision}.prompt.json --agent-tasks-out {revision}.agent_tasks.md"
            ),
            "source_paths": list(
                dict.fromkeys(
                    [
                        *scene_runtime_sources,
                        revision_source,
                        f"{review}.json",
                        f"{review}.md",
                        *direction_sources,
                    ]
                )
            ),
            "context_trace": context_trace,
            "candidate": f"{revision}.md",
            "revision_source": revision_source,
            "expected_outputs": [
                f"{revision}.md",
                f"{revision}_report.md",
                f"{revision}.json",
                f"{revision}.prompt.json",
                f"{revision}.agent_tasks.md",
                f"{revision}.agent_completion.json",
            ],
            "core_managed_outputs": [f"{revision}.prompt.json", f"{revision}.agent_tasks.md"],
            "hard_constraints": [
                "The main creative Agent must execute the revision personally; subagents cannot write or polish prose.",
                "Every blocking issue, warning, revision action, style deviation, budget gap, reader-contract gap, and rhythm/bridge gap must map to an observable prose change or remain explicitly blocking.",
                "The revised deliverable body must differ from the exact source candidate; changing only reports or manifests is forbidden.",
                "The revision remains a candidate and must receive a fresh exact-candidate AgentReview before promotion.",
                "When the review requires a human/delegated direction, follow only the consumed revision_direction choice file included in source_paths. It must match the exact revision source path and SHA-256; never reuse a global or stale direction. Do not alter canon or character assets from this prose task.",
            ],
            "style_constraints": [
                "Apply semantic anti-evasion revision rather than regex cleanup.",
                "Do not replace a banned contrast or transition with a cosmetic synonym.",
            ],
            "validation_gates": [
                "revision candidate and provenance files exist",
                "revision candidate differs from source sha256",
                "revision manifest records applied actions and ready_for_review=false",
                "revision sidecar completion marker exists",
            ],
            "next_allowed_states": ["candidate-review"],
        },
        "candidate-human-decision": {
            "task_type": "human-approval-boundary",
            "prompt_asset_id": "route.scene-development.cross-asset-alignment.v1",
            "command": "",
            "source_paths": [scene_rel, revision_source, f"{review}.json", f"{review}.md"],
            "context_trace": context_trace,
            "expected_outputs": [],
            "hard_constraints": [
                "Do not revise prose or change a canon/character asset before this exact candidate receives a recorded decision.",
                "Choose align_prose_to_formal_asset only when the existing formal asset should win; choose hold_for_asset_revision when the asset itself must be revised through its formal route.",
                "The decision must be bound to this scene_id and candidate_sha256. Generic revision notes do not satisfy this gate.",
            ],
            "style_constraints": [],
            "validation_gates": ["matching human or delegated revision direction is recorded for the exact candidate sha256"],
            "next_allowed_states": ["candidate-revision"],
        },
        "agent-review-task": {
            "task_type": "platform-agent-review",
            "prompt_asset_id": "route.scene-development.agent-review.complete.v1",
            "command": "",
            "source_paths": [scene_rel, context, context_trace, f"{review}.agent_tasks.md", f"{candidate}.md"],
            "context_trace": context_trace,
            "expected_outputs": [f"{review}.json", f"{review}.md", f"{review}.agent_completion.json"],
            "hard_constraints": ["Complete AgentReview sidecar only after writing JSON/Markdown review for the exact candidate."],
            "style_constraints": ["Medium+ Style Lint findings are blocking unless revised and re-reviewed."],
            "validation_gates": ["AgentReview completion marker exists"],
            "next_allowed_states": ["promotion-manifest"],
        },
        "promotion-manifest": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.scene-development.promote.v1",
            "command": (
                f"python -m literary_engineering_studio_engine promote-candidate <project> --scene {scene_rel} "
                f"--candidate {candidate_markdown}"
                + (" --overwrite" if (root / "drafts" / "scenes" / f"{scene_id}.md").exists() else "")
            ),
            "source_paths": list(
                dict.fromkeys(
                    [
                        *scene_runtime_sources,
                        candidate_markdown,
                        f"{candidate}.json",
                        f"{candidate}.prompt.json",
                        f"{candidate}.agent_tasks.md",
                        f"{candidate}.agent_completion.json",
                        f"{review}.json",
                        f"{review}.md",
                        f"{review}.agent_tasks.md",
                        f"{review}.agent_completion.json",
                    ]
                )
            ),
            "context_trace": context_trace,
            "expected_outputs": [f"drafts/promotions/{scene_id}_promotion.json", f"drafts/promotions/{scene_id}_promotion.md", f"drafts/scenes/{scene_id}.md"],
            "hard_constraints": ["Do not use --allow-unreviewed or --allow-review-notes."],
            "style_constraints": [],
            "validation_gates": ["promotion manifest exists", "promoted draft exists"],
            "next_allowed_states": ["static-review"],
        },
        "promoted-draft": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.scene-development.promote.v1",
            "command": (
                f"python -m literary_engineering_studio_engine promote-candidate <project> --scene {scene_rel} "
                f"--candidate {candidate_markdown}"
                + (" --overwrite" if (root / "drafts" / "scenes" / f"{scene_id}.md").exists() else "")
            ),
            "source_paths": list(
                dict.fromkeys(
                    [
                        *scene_runtime_sources,
                        candidate_markdown,
                        f"{candidate}.json",
                        f"{candidate}.prompt.json",
                        f"{candidate}.agent_tasks.md",
                        f"{candidate}.agent_completion.json",
                        f"{review}.json",
                        f"{review}.md",
                        f"{review}.agent_tasks.md",
                        f"{review}.agent_completion.json",
                    ]
                )
            ),
            "context_trace": context_trace,
            "expected_outputs": [f"drafts/scenes/{scene_id}.md"],
            "hard_constraints": ["Promoted draft must come from promote-candidate, not manual copy."],
            "style_constraints": [],
            "validation_gates": ["promoted draft exists"],
            "next_allowed_states": ["static-review"],
        },
        "static-review": {
            "task_type": "deterministic-review",
            "prompt_asset_id": "route.scene-development.static-review.v1",
            "command": f"python -m literary_engineering_studio_engine review-scene <project> drafts/scenes/{scene_id}.md",
            "source_paths": [*scene_runtime_sources, f"drafts/scenes/{scene_id}.md"],
            "context_trace": context_trace,
            "expected_outputs": [f"reviews/{scene_id}-review.md"],
            "hard_constraints": [
                "Run deterministic static review on the exact promoted draft and record its honest conclusion.",
                "A non-pass static verdict is a valid completed task and must route into static-revision rather than rerunning the same unchanged review.",
            ],
            "style_constraints": ["Apply punctuation and Style Lint concerns surfaced by review."],
            "validation_gates": ["static review conclusion is recorded for exact promoted draft"],
            "next_allowed_states": ["static-revision", "state-patch-json"],
        },
        "static-revision": {
            "task_type": "main-platform-agent-prose-revision",
            "prompt_asset_id": "route.scene-development.revision.v1",
            "command": (
                f"python -m literary_engineering_studio_engine revise-scene <project> --scene {scene_rel} "
                f"--draft {revision_source} --review reviews/{scene_id}-review.md --out {revision}.md "
                f"--report-out {revision}_report.md --manifest-out {revision}.json "
                f"--prompt-manifest-out {revision}.prompt.json --agent-tasks-out {revision}.agent_tasks.md"
            ),
            "source_paths": list(
                dict.fromkeys(
                    [
                        *scene_runtime_sources,
                        revision_source,
                        f"reviews/{scene_id}-review.md",
                    ]
                )
            ),
            "context_trace": context_trace,
            "candidate": f"{revision}.md",
            "revision_source": revision_source,
            "expected_outputs": [
                f"{revision}.md",
                f"{revision}_report.md",
                f"{revision}.json",
                f"{revision}.prompt.json",
                f"{revision}.agent_tasks.md",
                f"{revision}.agent_completion.json",
            ],
            "core_managed_outputs": [f"{revision}.prompt.json", f"{revision}.agent_tasks.md"],
            "hard_constraints": [
                "The main creative Agent must revise the prose personally against every static review finding.",
                "The revised body must differ from the promoted draft and remain a candidate.",
                "After revision, run fresh exact-candidate AgentReview, promotion, and static review; do not edit the promoted draft in place.",
            ],
            "style_constraints": ["Apply semantic repairs; never use regex cleanup or cosmetic transition substitution."],
            "validation_gates": [
                "revision candidate differs from promoted draft sha256",
                "revision provenance and completion files exist",
                "revision manifest records applied actions and ready_for_review=false",
            ],
            "next_allowed_states": ["candidate-review"],
        },
    }
    default = {
        "task_type": "manual-route-repair",
        "prompt_asset_id": "route.scene-development.repair.v1",
        "command": next_action,
        "source_paths": common_sources,
        "context_trace": context_trace,
        "expected_outputs": [],
        "hard_constraints": [next_action or "Inspect workflow-state and route-audit, then repair the missing formal gate."],
        "style_constraints": [],
        "validation_gates": ["route-specific gate resolved"],
        "next_allowed_states": [],
    }
    return _select_blueprint(current_state, writeback, table, default)


def _select_blueprint(
    current_state: str,
    writeback: dict[str, object] | None,
    table: dict[str, dict[str, object]],
    default: dict[str, object],
) -> dict[str, object]:
    return writeback if writeback is not None else table.get(current_state, default)
