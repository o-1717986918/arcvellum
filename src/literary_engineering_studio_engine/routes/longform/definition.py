"""Formal task blueprint and Gate logic for longform planning.

This route is the literary planning chain: causal story architecture precedes
word budgeting; budgeted inventory precedes chapter obligations; only reviewed
candidates may be materialized into formal scene contracts.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import re

from ...agent_tasks import agent_task_completion_status
from ...longform_materializer import longform_materialization_status, planned_longform_outputs
from ...story_architecture import story_architecture_status, story_architecture_task_status
from ...task_paths import TASK_SCHEMA, normalize_relative_path, now, relative_path, resolve_project_path, task_id
from .context_policy import agent_context_payload, apply_agent_context_policy


def build_task_payload(root: Path, route: str, state: dict[str, object]) -> dict[str, object]:
    current_state = str(state.get("current_step") or "")
    next_action = str(state.get("next_action") or "")
    blueprint = blueprint_for_state(root, current_state, next_action)
    identifier = task_id(route, "longform", current_state)
    expected_outputs = _unique([normalize_relative_path(item) for item in blueprint["expected_outputs"]])
    source_paths = _unique([normalize_relative_path(item) for item in blueprint["source_paths"]])
    payload: dict[str, object] = {
        "schema": TASK_SCHEMA,
        "task_id": identifier,
        "status": "issued",
        "created_at": now(),
        "route": route,
        "scene_id": "longform",
        "target_id": "longform",
        "scene": "project.yaml",
        "current_state": current_state,
        "task_type": blueprint["task_type"],
        "prompt_asset_id": blueprint["prompt_asset_id"],
        "command": blueprint["command"],
        "required_reading": blueprint.get(
            "required_reading",
            [
                "SKILL.md",
                "AGENTS.md",
                "agentread.yaml",
                "references/agent-run-protocol.md",
                "references/cli-run-protocol.md",
                "docs/modules/longform-word-budget.md",
            ],
        ),
        "source_paths": source_paths,
        "context_trace": blueprint.get("context_trace", ""),
        "hard_constraints": blueprint["hard_constraints"],
        "style_constraints": blueprint["style_constraints"],
        "word_count_target": blueprint.get("word_count_target", 0),
        "word_count_min": blueprint.get("word_count_min", 0),
        "word_count_max": blueprint.get("word_count_max", 0),
        "expected_outputs": expected_outputs,
        "submission_command": f"python -m literary_engineering_studio_engine task-submit <project> --task-id {identifier} --from <artifact>",
        "completion_command": f"python -m literary_engineering_studio_engine task-complete <project> --task-id {identifier}",
        "validation_gates": blueprint["validation_gates"],
        "forbidden_shortcuts": [
            "Do not treat word_budget.json as final plot or sufficient narrative inventory by itself.",
            "Do not bypass the semantic requirements compiled into the current budget, scene-inventory, or chapter-obligation task package.",
            "Do not start bulk scene generation while longform-planning is blocked.",
            "Do not satisfy target length by making each scene verbose; expand narrative inventory instead.",
            "Do not overwrite formal plot/outline.md or scenes/ before candidate review and user approval.",
            "Do not treat this task as complete until task-submit and task-complete have succeeded.",
        ],
        "next_allowed_states": blueprint["next_allowed_states"],
    }
    payload.update(agent_context_payload(blueprint))
    repair_targets = [str(item) for item in blueprint.get("repair_targets", [])]
    if repair_targets:
        payload["repair_targets"] = repair_targets
        payload["repair_target_sha256_before_revision"] = {
            relative: _file_sha256(resolve_project_path(root, relative))
            for relative in repair_targets
            if resolve_project_path(root, relative).is_file()
        }
    return payload


def blueprint_for_state(root: Path, current_state: str, next_action: str) -> dict[str, object]:
    project_text = _read_text(root / "project.yaml")
    target_words = _project_int(project_text, "target_length") or _project_int(project_text, "target_words") or 100000
    volumes = _project_int(project_text, "volumes")
    target_chapters = _project_int(project_text, "target_chapters")
    target_scenes = _project_int(project_text, "target_scenes")
    genre = _project_scalar(project_text, "genre")
    command = f"python -m literary_engineering_studio_engine word-budget <project> --target-words {target_words}"
    if volumes:
        command += f" --volumes {volumes}"
    if target_chapters:
        command += f" --target-chapters {target_chapters}"
    if target_scenes:
        command += f" --target-scenes {target_scenes}"
    if genre:
        command += f" --genre {genre}"
    common_sources = ["project.yaml", "plot/outline.md", "scenes/"]
    table: dict[str, dict[str, object]] = {
        "story-architecture-prepare": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.longform-planning.story-architecture.execute.v1",
            "command": "python -m literary_engineering_studio_engine prepare-story-architecture <project>",
            "source_paths": ["project.yaml", "plot/outline.md"],
            "expected_outputs": ["plot/story_architecture.candidate.json", "plot/story_architecture.agent_tasks.md"],
            "hard_constraints": ["Prepare a candidate-only story architecture task before word budgeting."],
            "style_constraints": [],
            "validation_gates": ["story architecture candidate template and Agent sidecar exist"],
            "next_allowed_states": ["story-architecture-agent-task"],
        },
        "story-architecture-agent-task": {
            "task_type": "platform-agent-judgment",
            "prompt_asset_id": "route.longform-planning.story-architecture.execute.v1",
            "command": "",
            "source_paths": ["project.yaml", "plot/outline.md", "plot/story_architecture.candidate.json", "plot/story_architecture.agent_tasks.md"],
            "expected_outputs": ["plot/story_architecture.candidate.json", "plot/story_architecture.agent_completion.json"],
            "hard_constraints": ["The main Agent must create a causal architecture candidate with an endgame choice; subagents do not write this literary decision."],
            "style_constraints": [],
            "validation_gates": ["story architecture candidate is complete", "writer session is recorded", "sidecar completion exists"],
            "next_allowed_states": ["story-architecture-review-prepare"],
        },
        "story-architecture-review-prepare": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.longform-planning.story-architecture.review.v1",
            "command": "python -m literary_engineering_studio_engine prepare-story-architecture-review <project>",
            "source_paths": ["project.yaml", "plot/story_architecture.candidate.json"],
            "expected_outputs": ["reviews/longform/story_architecture_review.json", "reviews/longform/story_architecture_review.agent_tasks.md"],
            "hard_constraints": ["Prepare an exact-digest independent review task; this step does not review the candidate."],
            "style_constraints": [],
            "validation_gates": ["review template binds to current architecture candidate sha256"],
            "next_allowed_states": ["story-architecture-review"],
        },
        "story-architecture-review": {
            "task_type": "platform-agent-review",
            "prompt_asset_id": "route.longform-planning.story-architecture.review.v1",
            "command": "",
            "source_paths": ["project.yaml", "plot/story_architecture.candidate.json", "reviews/longform/story_architecture_review.json", "reviews/longform/story_architecture_review.agent_tasks.md"],
            "expected_outputs": ["reviews/longform/story_architecture_review.json", "reviews/longform/story_architecture_review.agent_completion.json"],
            "hard_constraints": ["Reviewer session must differ from writer session and must not edit the candidate in place."],
            "style_constraints": [],
            "validation_gates": ["independent review binds to exact candidate sha256", "verdict is pass", "sidecar completion exists"],
            "next_allowed_states": ["word-budget-file"],
        },
        "word-budget-file": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.longform-planning.word-budget.prepare.v1",
            "command": command,
            "source_paths": common_sources,
            "expected_outputs": [
                "plot/word_budget/word_budget.md",
                "plot/word_budget/word_budget.json",
                "plot/word_budget/word_budget.agent_tasks.md",
                "plot/word_budget/scene_inventory_expansion.agent_tasks.md",
                "plot/chapter_obligations/chapter_obligations.agent_tasks.md",
            ],
            "hard_constraints": [
                "Run word-budget / longform-budget before bulk outline or scene generation.",
                "Inspect both emitted platform-agent sidecars; this task is only the deterministic budget scaffold.",
            ],
            "style_constraints": [],
            "word_count_target": target_words,
            "validation_gates": ["word_budget.json exists", "word budget schema is valid", "budget, scene inventory, and chapter obligation sidecars exist"],
            "next_allowed_states": ["budget-agent-task"],
        },
        "budget-agent-task": {
            "task_type": "platform-agent-judgment",
            "prompt_asset_id": "route.longform-planning.budget-expansion.execute.v1",
            "command": "",
            "source_paths": [
                "project.yaml",
                "plot/outline.md",
                "plot/word_budget/word_budget.md",
                "plot/word_budget/word_budget.json",
                "plot/word_budget/word_budget.agent_tasks.md",
            ],
            "expected_outputs": ["plot/candidates/outlines/word_budget_expansion.md", "reviews/word_budget/word_budget_review.md", "plot/word_budget/word_budget.agent_completion.json"],
            "hard_constraints": [
                "Write only the budgeted outline candidate and its semantic review; Studio owns lifecycle completion receipts.",
                "Judge whether the narrative inventory can support target length; do not solve shortfall by padding scenes.",
                "Keep expanded outline as candidate material until review and user approval.",
            ],
            "style_constraints": [],
            "word_count_target": target_words,
            "validation_gates": ["budget sidecar completion marker exists", "budgeted outline candidate exists", "word-budget review conclusion is recorded"],
            "next_allowed_states": ["budget-review", "scene-inventory-agent-task"],
        },
        "budget-review": {
            "task_type": "platform-agent-revision",
            "prompt_asset_id": "route.longform-planning.budget-review.v1",
            "command": "",
            "source_paths": ["plot/word_budget/word_budget.json", "plot/candidates/outlines/word_budget_expansion.md", "reviews/word_budget/word_budget_review.md"],
            "expected_outputs": ["plot/candidates/outlines/word_budget_expansion.md", "reviews/word_budget/word_budget_review.md"],
            "repair_targets": ["plot/candidates/outlines/word_budget_expansion.md"],
            "hard_constraints": [
                "Revise the budgeted outline candidate against every review finding; changing only the conclusion is forbidden.",
                "The review conclusion must be pass before scene inventory planning is treated as formal.",
            ],
            "style_constraints": [],
            "word_count_target": target_words,
            "validation_gates": ["word-budget review conclusion is pass"],
            "next_allowed_states": ["scene-inventory-agent-task"],
        },
        "scene-inventory-agent-task": {
            "task_type": "platform-agent-judgment",
            "prompt_asset_id": "route.longform-planning.scene-inventory.execute.v1",
            "command": "",
            "source_paths": ["plot/word_budget/word_budget.json", "plot/word_budget/scene_inventory_expansion.agent_tasks.md", "plot/candidates/outlines/word_budget_expansion.md"],
            "expected_outputs": ["plot/candidates/scenes/word_budget_scene_inventory.md", "reviews/word_budget/scene_inventory_review.md", "plot/word_budget/scene_inventory_expansion.agent_completion.json"],
            "hard_constraints": [
                "Follow the exact scene-inventory prompt contract and create budgeted scene inventory candidates; Studio owns the lifecycle sidecar and receipt.",
                "The inventory is a machine-readable materialization contract: use the required chapter heading and 11-column scene table, not free-form scene cards or prose summaries.",
                "Each added scene candidate needs target Chinese-content characters, function, participants, conflict, information release, consequence, and setup/payoff role.",
                "The participants column contains durable human/character roles only. Do not list locations, vehicles, signals, objects, organizations, camera subjects, or unnamed crowds as characters; express those through conflict, information release, consequence, or setting.",
                "Use the stable symbolic label 主角 for the foundational protagonist before its canonical name is fixed. Any other participant listed here is a deliberate request for a reusable character asset before RP and prose.",
                "Scene inventory remains candidate material until review and user approval.",
            ],
            "style_constraints": [],
            "word_count_target": target_words,
            "validation_gates": ["scene inventory sidecar completion marker exists", "scene inventory candidate exists", "scene inventory review conclusion is recorded"],
            "next_allowed_states": ["scene-inventory-review"],
        },
        "scene-inventory-review": {
            "task_type": "platform-agent-revision",
            "prompt_asset_id": "route.longform-planning.scene-inventory-review.v1",
            "command": "",
            "source_paths": ["plot/word_budget/word_budget.json", "plot/candidates/scenes/word_budget_scene_inventory.md", "reviews/word_budget/scene_inventory_review.md"],
            "expected_outputs": ["plot/candidates/scenes/word_budget_scene_inventory.md", "reviews/word_budget/scene_inventory_review.md"],
            "repair_targets": ["plot/candidates/scenes/word_budget_scene_inventory.md"],
            "hard_constraints": [
                "Revise the scene inventory candidate against every review finding; changing only the conclusion is forbidden.",
                "The scene inventory review conclusion must be pass before longform-planning is ready.",
            ],
            "style_constraints": [],
            "word_count_target": target_words,
            "validation_gates": ["scene inventory review conclusion is pass"],
            "next_allowed_states": ["chapter-obligation-agent-task"],
        },
        "chapter-obligation-agent-task": {
            "task_type": "platform-agent-judgment",
            "prompt_asset_id": "route.longform-planning.chapter-obligation.execute.v1",
            "command": "",
            "source_paths": ["project.yaml", "plot/outline.md", "plot/word_budget/word_budget.json", "plot/chapter_obligations/chapter_obligations.agent_tasks.md", "plot/candidates/scenes/word_budget_scene_inventory.md"],
            "expected_outputs": ["plot/candidates/chapters/chapter_obligation_plan.md", "reviews/word_budget/chapter_obligation_review.md", "plot/chapter_obligations/chapter_obligations.agent_completion.json"],
            "hard_constraints": [
                "Follow the exact chapter-obligation prompt contract and build a chapter-level promise/payoff plan; Studio owns the lifecycle sidecar and receipt.",
                "Each chapter must map target Chinese-content characters to reader questions, promised rewards, withheld information, payoff/delay, and anti-summary requirements.",
                "Per-scene chapter-obligation JSON files remain platform-agent contracts; create them with chapter-obligation before scene prose generation.",
            ],
            "style_constraints": [],
            "word_count_target": target_words,
            "validation_gates": ["chapter obligation sidecar completion marker exists", "chapter obligation plan candidate exists", "chapter obligation review conclusion is recorded"],
            "next_allowed_states": ["chapter-obligation-review"],
        },
        "chapter-obligation-review": {
            "task_type": "platform-agent-revision",
            "prompt_asset_id": "route.longform-planning.chapter-obligation-review.v1",
            "command": "",
            "source_paths": ["plot/word_budget/word_budget.json", "plot/chapter_obligations/chapter_obligations.agent_tasks.md", "plot/candidates/chapters/chapter_obligation_plan.md", "reviews/word_budget/chapter_obligation_review.md"],
            "expected_outputs": ["plot/candidates/chapters/chapter_obligation_plan.md", "reviews/word_budget/chapter_obligation_review.md"],
            "repair_targets": ["plot/candidates/chapters/chapter_obligation_plan.md"],
            "hard_constraints": [
                "Revise the chapter obligation plan against every review finding; changing only the conclusion is forbidden.",
                "The chapter obligation review conclusion must be pass before longform-planning is ready.",
            ],
            "style_constraints": [],
            "word_count_target": target_words,
            "validation_gates": ["chapter obligation review conclusion is pass"],
            "next_allowed_states": ["planning-materialization"],
        },
        "planning-materialization": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.longform-planning.materialize.v1",
            "command": "python -m literary_engineering_studio_engine materialize-longform-plan <project>",
            "source_paths": [
                "project.yaml",
                "plot/word_budget/word_budget.json",
                "plot/candidates/outlines/word_budget_expansion.md",
                "plot/candidates/scenes/word_budget_scene_inventory.md",
                "plot/candidates/chapters/chapter_obligation_plan.md",
                "reviews/word_budget/word_budget_review.md",
                "reviews/word_budget/scene_inventory_review.md",
                "reviews/word_budget/chapter_obligation_review.md",
                "scenes/scene_0001.yaml",
            ],
            "expected_outputs": planned_longform_outputs(root),
            "hard_constraints": [
                "Materialize only after the budget, scene inventory, and chapter obligation reviews all pass.",
                "Convert the reviewed candidate inventory into formal scene contracts; do not invent or omit scenes in this deterministic step.",
                "Never overwrite a scene that already contains formal development evidence. When every existing formal contract exactly matches the reviewed inventory, record a safe adoption manifest instead; if any contract differs, stop for manual reconciliation.",
            ],
            "style_constraints": [],
            "word_count_target": target_words,
            "validation_gates": ["materialization manifest is current", "formal outline exists", "all budgeted formal scene YAML files exist"],
            "next_allowed_states": ["ready"],
        },
    }
    blueprint = table.get(current_state) or _fallback_blueprint(
        next_action, target_words, common_sources
    )
    return apply_agent_context_policy(current_state, blueprint)


def _fallback_blueprint(
    next_action: str,
    target_words: int,
    common_sources: list[str],
) -> dict[str, object]:
    return {
        "task_type": "manual-route-repair",
        "prompt_asset_id": "route.longform-planning.repair.v1",
        "command": next_action,
        "source_paths": common_sources,
        "expected_outputs": [],
        "hard_constraints": [next_action or "Inspect workflow-state and route-audit, then repair the missing longform-planning gate."],
        "style_constraints": [],
        "word_count_target": target_words,
        "validation_gates": ["longform-planning gate resolved"],
        "next_allowed_states": [],
    }


def validate_task(root: Path, task: dict[str, object]) -> tuple[list[str], list[str]]:
    current_state = str(task.get("current_state") or "")
    errors: list[str] = []
    notes: list[str] = []
    if current_state == "story-architecture-prepare":
        if not (root / "plot" / "story_architecture.agent_tasks.md").is_file():
            errors.append("story architecture task sidecar is missing")
    if current_state == "story-architecture-agent-task":
        passed, message = story_architecture_task_status(root, review=False)
        if not passed:
            errors.append(message)
    if current_state == "story-architecture-review-prepare":
        if not (root / "reviews" / "longform" / "story_architecture_review.agent_tasks.md").is_file():
            errors.append("story architecture review task sidecar is missing")
    if current_state == "story-architecture-review":
        passed, message = story_architecture_task_status(root, review=True)
        if not passed:
            errors.append(message)
    planning_states = {
        "word-budget-file", "budget-agent-task", "budget-review", "scene-inventory-agent-task",
        "scene-inventory-review", "chapter-obligation-agent-task", "chapter-obligation-review", "planning-materialization",
    }
    if current_state in planning_states:
        passed, message, _payload = story_architecture_status(root, require_review=True)
        if not passed:
            errors.append("story architecture gate: " + message)
    if current_state == "word-budget-file":
        errors.extend(word_budget_file_gate_errors(root))
    if current_state in {"budget-agent-task", "budget-review"}:
        errors.extend(word_budget_file_gate_errors(root))
        errors.extend(_sidecar_completion_errors(root / "plot" / "word_budget" / "word_budget.agent_tasks.md", root, "word-budget expansion"))
        errors.extend(_required_artifact_errors(root, [root / "plot" / "candidates" / "outlines" / "word_budget_expansion.md"], "word-budget expansion"))
        errors.extend(_review_gate_errors(root / "reviews" / "word_budget" / "word_budget_review.md", root, "word-budget review", require_pass=current_state == "budget-review"))
        if current_state == "budget-review":
            errors.extend(_repair_targets_changed(root, task, "word-budget revision"))
    if current_state in {"scene-inventory-agent-task", "scene-inventory-review"}:
        errors.extend(word_budget_file_gate_errors(root))
        errors.extend(_sidecar_completion_errors(root / "plot" / "word_budget" / "scene_inventory_expansion.agent_tasks.md", root, "scene-inventory expansion"))
        errors.extend(_required_artifact_errors(root, [root / "plot" / "candidates" / "scenes" / "word_budget_scene_inventory.md"], "scene-inventory expansion"))
        errors.extend(_review_gate_errors(root / "reviews" / "word_budget" / "scene_inventory_review.md", root, "scene-inventory review", require_pass=current_state == "scene-inventory-review"))
        if current_state == "scene-inventory-review":
            errors.extend(_repair_targets_changed(root, task, "scene-inventory revision"))
    if current_state in {"chapter-obligation-agent-task", "chapter-obligation-review"}:
        errors.extend(word_budget_file_gate_errors(root))
        errors.extend(_sidecar_completion_errors(root / "plot" / "chapter_obligations" / "chapter_obligations.agent_tasks.md", root, "chapter obligation planning"))
        errors.extend(_required_artifact_errors(root, [root / "plot" / "candidates" / "chapters" / "chapter_obligation_plan.md"], "chapter obligation planning"))
        errors.extend(_review_gate_errors(root / "reviews" / "word_budget" / "chapter_obligation_review.md", root, "chapter obligation review", require_pass=current_state == "chapter-obligation-review"))
        if current_state == "chapter-obligation-review":
            errors.extend(_repair_targets_changed(root, task, "chapter-obligation revision"))
    if current_state in {"budget-agent-task", "budget-review"} and not errors:
        notes.append("word-budget expansion reviewed")
    if current_state in {"scene-inventory-agent-task", "scene-inventory-review"} and not errors:
        notes.append("scene inventory reviewed")
    if current_state in {"chapter-obligation-agent-task", "chapter-obligation-review"} and not errors:
        notes.append("chapter obligation reviewed")
    if current_state == "planning-materialization":
        passed, message = longform_materialization_status(root)
        if not passed:
            errors.append(message)
        else:
            notes.append(message)
    return errors, notes


def word_budget_file_gate_errors(root: Path) -> list[str]:
    json_path = root / "plot" / "word_budget" / "word_budget.json"
    markdown_path = root / "plot" / "word_budget" / "word_budget.md"
    budget_task = root / "plot" / "word_budget" / "word_budget.agent_tasks.md"
    scene_task = root / "plot" / "word_budget" / "scene_inventory_expansion.agent_tasks.md"
    obligation_task = root / "plot" / "chapter_obligations" / "chapter_obligations.agent_tasks.md"
    errors = [f"missing longform budget artifact: {relative_path(path, root)}" for path in (markdown_path, json_path, budget_task, scene_task, obligation_task) if not path.exists()]
    payload, error = _read_optional_json(json_path)
    if error:
        return [*errors, error]
    if payload.get("schema") != "literary-engineering-workbench/word-budget/v1":
        errors.append("word_budget.json has wrong or missing schema")
    target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    totals = payload.get("totals") if isinstance(payload.get("totals"), dict) else {}
    if _to_int(target.get("target_words") or totals.get("target_words")) <= 0:
        errors.append("word_budget.json target Chinese-content characters must be positive")
    if not isinstance(payload.get("chapter_budgets"), list) or not payload.get("chapter_budgets"):
        errors.append("word_budget.json must contain chapter_budgets")
    if not isinstance(payload.get("scene_inventory_binding"), dict):
        errors.append("word_budget.json must contain scene_inventory_binding")
    return errors


def _sidecar_completion_errors(task_path: Path, root: Path, label: str) -> list[str]:
    state = agent_task_completion_status(task_path, root=root)
    return [] if state.get("complete") is True else [f"{label} sidecar is incomplete: {state.get('message')}"]


def _required_artifact_errors(root: Path, paths: list[Path], label: str) -> list[str]:
    missing = [relative_path(path, root) for path in paths if not path.exists()]
    return [] if not missing else [f"{label} required artifact missing: {', '.join(missing)}"]


def _review_gate_errors(path: Path, root: Path, label: str, *, require_pass: bool = True) -> list[str]:
    conclusion = _static_review_conclusion(path)
    allowed = {"pass", "pass_with_notes", "revise_required", "reject"}
    if conclusion not in allowed:
        return [f"{label} conclusion must be recorded; got {conclusion or 'missing'} at {relative_path(path, root)}"]
    return [] if not require_pass or conclusion == "pass" else [f"{label} conclusion must be pass; got {conclusion or 'missing'} at {relative_path(path, root)}"]


def _repair_targets_changed(root: Path, task: dict[str, object], label: str) -> list[str]:
    targets = [str(item) for item in task.get("repair_targets") or [] if str(item).strip()]
    hashes = task.get("repair_target_sha256_before_revision")
    before = hashes if isinstance(hashes, dict) else {}
    if not targets or not before:
        return [f"{label} is missing declared repair target hash provenance"]
    for target in targets:
        path = resolve_project_path(root, target)
        previous = str(before.get(target) or "").strip().lower()
        if path.is_file() and previous and _file_sha256(path) != previous:
            return []
    return [f"{label} did not change any declared planning candidate; review-only edits cannot complete revision"]


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_optional_json(path: Path) -> tuple[dict[str, object], str]:
    if not path.exists():
        return {}, f"JSON file missing: {path}"
    try:
        import json
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, f"invalid JSON: {relative_path(path, path.parent)} ({exc.msg})"
    except OSError as exc:
        return {}, str(exc)
    return (payload, "") if isinstance(payload, dict) else ({}, f"JSON root is not an object: {path}")


def _static_review_conclusion(path: Path) -> str:
    text = _read_text(path).strip()
    match = re.search(r"(?m)^-\s*(?:审查)?结论：\s*(?:\*\*)?`?([a-z_]+)`?(?:\*\*)?\s*$", text, re.IGNORECASE)
    return match.group(1).strip().lower() if match else ""


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip() if path.exists() else ""


def _project_scalar(text: str, key: str) -> str:
    match = re.search(rf"(?m)^[ \t]*{re.escape(key)}:[ \t]*(.*?)\s*$", text)
    if not match:
        return ""
    value = match.group(1).strip()
    if value in {"null", "[]", "{}"}:
        return ""
    return value.strip("\"'")


def _project_int(text: str, key: str) -> int:
    return _to_int(_project_scalar(text, key))


def _to_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value).replace(",", "").replace("_", "").strip())
    except (TypeError, ValueError):
        return 0


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))
