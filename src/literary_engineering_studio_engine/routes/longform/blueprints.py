"""Declarative task blueprints for the longform-planning route."""

from __future__ import annotations

from pathlib import Path

from ...longform_materializer import planned_longform_outputs
from .context_policy import apply_agent_context_policy
from .support import project_int, project_scalar, read_text


def blueprint_for_state(root: Path, current_state: str, next_action: str) -> dict[str, object]:
    project_text = read_text(root / "project.yaml")
    target_words = project_int(project_text, "target_length") or project_int(project_text, "target_words") or 100000
    volumes = project_int(project_text, "volumes")
    target_chapters = project_int(project_text, "target_chapters")
    target_scenes = project_int(project_text, "target_scenes")
    genre = project_scalar(project_text, "genre")
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
    table = {
        **_story_architecture_blueprints(),
        **_budget_blueprints(target_words, command, common_sources),
        **_inventory_blueprints(target_words),
        **_chapter_blueprints(root, target_words),
    }
    blueprint = table.get(current_state) or _fallback_blueprint(
        next_action, target_words, common_sources
    )
    return apply_agent_context_policy(current_state, blueprint)


def _story_architecture_blueprints() -> dict[str, dict[str, object]]:
    return {
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
            "validation_gates": ["independent review binds to exact candidate sha256", "terminal verdict is recorded", "sidecar completion exists"],
            "next_allowed_states": ["story-architecture-revision", "word-budget-file"],
        },
        "story-architecture-revision": {
            "task_type": "platform-agent-revision",
            "prompt_asset_id": "route.longform-planning.story-architecture.execute.v1",
            "command": "",
            "source_paths": ["project.yaml", "plot/outline.md", "plot/story_architecture.candidate.json", "plot/story_architecture.agent_tasks.md", "reviews/longform/story_architecture_review.json"],
            "expected_outputs": ["plot/story_architecture.candidate.json", "plot/story_architecture.agent_completion.json"],
            "repair_targets": ["plot/story_architecture.candidate.json"],
            "hard_constraints": [
                "Revise the exact story architecture candidate against every required_changes item; do not edit the review verdict.",
                "Preserve every valid architecture field and make a substantive causal change rather than paraphrasing the same answer.",
                "A fresh independent review bound to the revised candidate digest is mandatory before word budgeting.",
            ],
            "style_constraints": [],
            "validation_gates": ["architecture candidate changed", "candidate remains complete", "fresh independent review is required"],
            "next_allowed_states": ["story-architecture-review-prepare"],
        },
    }


def _budget_blueprints(
    target_words: int, command: str, common_sources: list[str]
) -> dict[str, dict[str, object]]:
    return {
        "word-budget-file": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.longform-planning.word-budget.prepare.v1",
            "command": command,
            "source_paths": common_sources,
            "expected_outputs": [
                "plot/word_budget/word_budget.md", "plot/word_budget/word_budget.json",
                "plot/word_budget/word_budget.agent_tasks.md", "plot/word_budget/scene_inventory_expansion.agent_tasks.md",
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
            "source_paths": ["project.yaml", "plot/outline.md", "plot/word_budget/word_budget.md", "plot/word_budget/word_budget.json", "plot/word_budget/word_budget.agent_tasks.md"],
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
    }


def _inventory_blueprints(target_words: int) -> dict[str, dict[str, object]]:
    return {
        "scene-inventory-agent-task": {
            "task_type": "platform-agent-judgment",
            "prompt_asset_id": "route.longform-planning.scene-inventory.execute.v1",
            "command": "",
            "source_paths": ["plot/word_budget/word_budget.json", "plot/word_budget/scene_inventory_expansion.agent_tasks.md", "plot/candidates/outlines/word_budget_expansion.md"],
            "expected_outputs": ["plot/candidates/scenes/word_budget_scene_inventory.md", "reviews/word_budget/scene_inventory_review.md", "plot/word_budget/scene_inventory_expansion.agent_completion.json"],
            "hard_constraints": [
                "Follow the exact scene-inventory prompt contract and create budgeted scene inventory candidates; Studio owns the lifecycle sidecar and receipt.",
                "The inventory is a machine-readable materialization contract: use the required chapter heading and 11-column scene table, not free-form scene cards or prose summaries; preserve exact total/per-chapter scene and Chinese-character budgets, and replace invalid rows in place rather than appending a corrected copy unless the user explicitly replans.",
                "Each added scene candidate needs target Chinese-content characters, function, participants, conflict, information release, consequence, and setup/payoff role.",
                "The participants column contains durable human/character roles only. Do not list locations, vehicles, signals, objects, organizations, camera subjects, or unnamed crowds as characters; express those through conflict, information release, consequence, or setting.",
                "Every participant is a bare stable identity label. Parentheses, action notes, aliases, reveal timing, and descriptive clauses belong in the other scene columns, never in a character identity.",
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
                "Revise the scene inventory candidate against every review finding by replacing invalid rows rather than appending duplicates; changing only the conclusion is forbidden.",
                "The scene inventory review conclusion must be pass before longform-planning is ready, and must recount parsed rows and target_chars against word_budget.json instead of trusting asserted totals.",
            ],
            "style_constraints": [],
            "word_count_target": target_words,
            "validation_gates": ["scene inventory review conclusion is pass"],
            "next_allowed_states": ["chapter-obligation-agent-task"],
        },
    }


def _chapter_blueprints(root: Path, target_words: int) -> dict[str, dict[str, object]]:
    return {
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
                "project.yaml", "plot/word_budget/word_budget.json", "plot/candidates/outlines/word_budget_expansion.md",
                "plot/candidates/scenes/word_budget_scene_inventory.md", "plot/candidates/chapters/chapter_obligation_plan.md",
                "reviews/word_budget/word_budget_review.md", "reviews/word_budget/scene_inventory_review.md",
                "reviews/word_budget/chapter_obligation_review.md", "scenes/scene_0001.yaml",
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


def _fallback_blueprint(
    next_action: str, target_words: int, common_sources: list[str]
) -> dict[str, object]:
    return {
        "task_type": "route-diagnostic-boundary",
        "prompt_asset_id": "route.longform-planning.repair.v1",
        "command": next_action,
        "source_paths": common_sources,
        "expected_outputs": [],
        "hard_constraints": [
            next_action or "Inspect workflow-state and route-audit, then repair the missing longform-planning gate.",
            "This unsupported state is a maintenance boundary. Do not invoke an Agent, invent outputs, or retry automatically.",
        ],
        "style_constraints": [],
        "word_count_target": target_words,
        "validation_gates": ["longform-planning gate resolved"],
        "next_allowed_states": [],
    }


__all__ = ["blueprint_for_state"]
