"""Task blueprints for post-promotion scene writeback."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


WRITEBACK_STATES = frozenset(
    {
        "state-patch-json",
        "state-agent-task",
        "state-patch-approval",
        "state-apply",
        "canon-patch-json",
        "canon-agent-task",
        "continuity-ledger-prepare",
        "continuity-ledger-agent-task",
        "continuity-ledger-review-prepare",
        "continuity-ledger-review",
        "continuity-ledger-apply",
    }
)


@dataclass(frozen=True)
class SceneWritebackContext:
    scene_id: str
    scene_rel: str
    context: str
    context_trace: str
    scene_runtime_sources: tuple[str, ...]
    state_patch: str
    state_patch_character_files: tuple[str, ...]
    state_apply: str
    state_review: str
    canon_patch: str
    canon_review: str
    canon_formal_sources: tuple[str, ...]
    review: str
    ledger_delta: str
    ledger_task: str
    ledger_review: str
    ledger_review_task: str


def writeback_blueprint_for_state(
    current_state: str,
    ctx: SceneWritebackContext,
) -> dict[str, object] | None:
    """Return one writeback blueprint without owning route selection."""

    return _writeback_table(ctx).get(current_state)


def _writeback_table(ctx: SceneWritebackContext) -> dict[str, dict[str, object]]:
    return {
        **_state_blueprints(ctx),
        "canon-patch-json": _canon_candidate_blueprint(ctx),
        "canon-agent-task": _canon_review_blueprint(ctx),
        **_continuity_blueprints(ctx),
    }


def _state_blueprints(ctx: SceneWritebackContext) -> dict[str, dict[str, object]]:
    scene_id, scene_rel = ctx.scene_id, ctx.scene_rel
    trace, patch = ctx.context_trace, ctx.state_patch
    return {
        "state-patch-json": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.scene-development.state-evolve.prepare.v1",
            "command": f"python -m literary_engineering_studio_engine state-evolve <project> --scene {scene_rel} --agent-tasks",
            "source_paths": [
                *ctx.scene_runtime_sources,
                f"drafts/scenes/{scene_id}.md",
                f"drafts/promotions/{scene_id}_promotion.json",
                f"drafts/compositions/{scene_id}_composition.json",
                f"reviews/agent/{scene_id}_scene_review.json",
            ],
            "context_trace": trace,
            "expected_outputs": [f"{patch}.md", f"{patch}.json", f"{patch}.agent_tasks.md", ctx.state_review],
            "hard_constraints": ["Prepare the state patch and its review sidecar only; state review is a separate formal Agent task."],
            "style_constraints": [],
            "validation_gates": ["state patch JSON exists", "state-evolve sidecar exists"],
            "next_allowed_states": ["state-agent-task"],
        },
        "state-agent-task": {
            "task_type": "platform-agent-review",
            "prompt_asset_id": "route.scene-development.state-evolve.execute.v1",
            "command": "",
            "source_paths": _unique([
                scene_rel, ctx.context, trace, f"drafts/scenes/{scene_id}.md",
                f"drafts/promotions/{scene_id}_promotion.json",
                f"drafts/compositions/{scene_id}_composition.json",
                f"reviews/agent/{scene_id}_scene_review.json",
                *ctx.state_patch_character_files,
                f"{patch}.md", f"{patch}.json", f"{patch}.agent_tasks.md", ctx.state_review,
            ]),
            "context_trace": trace,
            "expected_outputs": [ctx.state_review, f"{patch}.agent_completion.json"],
            "hard_constraints": ["Review state patch consequences and write a schema-valid state review with exact source digest; Studio writes the completion marker after deterministic preflight passes. Do not apply state without approval."],
            "style_constraints": [],
            "validation_gates": ["state-evolve sidecar completion marker exists", "state_patch_review.v1 semantic artifact passes"],
            "next_allowed_states": ["state-patch-approval", "state-apply", "canon-patch-json", "ready"],
        },
        "state-patch-approval": {
            "task_type": "human-approval-boundary",
            "prompt_asset_id": "route.scene-development.state-approval.v1",
            "command": f"Ask the user to approve state patch `{patch}.json` and record state_patch_confirmation with approval_run_id `{Path(patch).name}` through the platform approval mechanism.",
            "source_paths": [scene_rel, f"{patch}.md", f"{patch}.json", ctx.state_review, "workflow/approvals/index.jsonl"],
            "context_trace": trace,
            "expected_outputs": ["workflow/approvals/index.jsonl"],
            "hard_constraints": ["Do not apply state as part of approval. Approval must be bound to the exact state patch SHA-256."],
            "style_constraints": [],
            "validation_gates": ["approval decision=approve and subject_sha256 matches the current state patch"],
            "next_allowed_states": ["state-apply"],
        },
        "state-apply": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.scene-development.state-apply.v1",
            "command": f"python -m literary_engineering_studio_engine state-apply <project> --patch {patch}.json --approval-run-id {Path(patch).name}",
            "source_paths": [
                scene_rel, f"{patch}.json", f"{patch}.agent_tasks.md",
                f"{patch}.agent_completion.json", ctx.state_review,
                "workflow/approvals/index.jsonl", *ctx.state_patch_character_files,
            ],
            "context_trace": trace,
            "expected_outputs": [
                *ctx.state_patch_character_files,
                f"{ctx.state_apply}.json", f"{ctx.state_apply}.md",
            ],
            "hard_constraints": [
                "State apply must keep Canon untouched, use the exact approved patch, and write every declared character record plus an atomic apply receipt.",
                "Only character files explicitly named by the current approved patch may be modified.",
            ],
            "style_constraints": [],
            "validation_gates": ["state apply receipt has the current patch digest and matching approval"],
            "next_allowed_states": ["canon-patch-json", "ready"],
        },
    }


def _continuity_blueprints(ctx: SceneWritebackContext) -> dict[str, dict[str, object]]:
    scene_id, scene_rel, trace = ctx.scene_id, ctx.scene_rel, ctx.context_trace
    return {
        "continuity-ledger-prepare": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.scene-development.continuity-ledger.v1",
            "command": f"python -m literary_engineering_studio_engine prepare-continuity-ledger <project> --scene {scene_rel}",
            "source_paths": [scene_rel, f"drafts/scenes/{scene_id}.md", f"drafts/promotions/{scene_id}_promotion.json"],
            "context_trace": trace,
            "expected_outputs": [ctx.ledger_delta, ctx.ledger_task],
            "hard_constraints": ["Prepare a candidate-only reader-question and promise/payoff delta from the exact promoted scene."],
            "style_constraints": [],
            "validation_gates": ["continuity ledger delta template and sidecar exist"],
            "next_allowed_states": ["continuity-ledger-agent-task"],
        },
        "continuity-ledger-agent-task": {
            "task_type": "platform-agent-judgment",
            "prompt_asset_id": "route.scene-development.continuity-ledger.v1",
            "command": "",
            "source_paths": [
                scene_rel, f"drafts/scenes/{scene_id}.md",
                f"drafts/promotions/{scene_id}_promotion.json", ctx.ledger_delta,
                ctx.ledger_task, "plot/reader_questions/ledger.json", "plot/promises/ledger.json",
            ],
            "context_trace": trace,
            "expected_outputs": [ctx.ledger_delta, f"plot/ledger_deltas/{scene_id}.agent_completion.json"],
            "hard_constraints": [
                "Main Agent records only prose-evidenced reader question and promise/payoff changes; do not edit formal ledgers.",
                "The lifecycle field is a fixed enum: write status=complete after the delta is ready. Do not invent status labels such as agent_judged.",
            ],
            "style_constraints": [],
            "validation_gates": ["ledger delta source digest matches promoted draft", "ledger delta has evidence or concrete no-change reason", "sidecar completion exists"],
            "next_allowed_states": ["continuity-ledger-review-prepare"],
        },
        "continuity-ledger-review-prepare": _ledger_review_prepare(ctx),
        "continuity-ledger-review": _ledger_review(ctx),
        "continuity-ledger-apply": _ledger_apply(ctx),
    }


def _canon_candidate_blueprint(ctx: SceneWritebackContext) -> dict[str, object]:
    scene_id, patch = ctx.scene_id, ctx.canon_patch
    return {
        "task_type": "deterministic-cli-plus-platform-review",
        "prompt_asset_id": "route.scene-development.canon-evolve.v1",
        "command": f"python -m literary_engineering_studio_engine canon-evolve <project> --scene {ctx.scene_rel}",
        "source_paths": [
            *ctx.scene_runtime_sources, f"drafts/scenes/{scene_id}.md",
            f"drafts/promotions/{scene_id}_promotion.json", f"{ctx.review}.json",
            f"{ctx.state_patch}.json", f"{ctx.state_patch}.agent_tasks.md",
            f"{ctx.state_patch}.agent_completion.json", ctx.state_review,
            *ctx.canon_formal_sources,
        ],
        "context_trace": ctx.context_trace,
        "expected_outputs": [f"{patch}.md", f"{patch}.json", f"{patch}.agent_tasks.md", ctx.canon_review],
        "core_managed_outputs": [f"{patch}.agent_tasks.md", ctx.canon_review],
        "hard_constraints": [
            "Canon writeback is a candidate-only judgment after state-evolve; it must not directly modify canon files.",
            "If no durable world fact changed, the platform agent must write no_canon_change_reason instead of silently skipping.",
        ],
        "style_constraints": [],
        "validation_gates": ["canon patch/no-change JSON exists", "canon-evolve sidecar exists when required"],
        "next_allowed_states": ["canon-agent-task"],
    }


def _canon_review_blueprint(ctx: SceneWritebackContext) -> dict[str, object]:
    scene_id, patch = ctx.scene_id, ctx.canon_patch
    return {
        "task_type": "platform-agent-review",
        "prompt_asset_id": "route.scene-development.canon-review.v1",
        "command": "",
        "source_paths": _unique([
            ctx.scene_rel, ctx.context, ctx.context_trace, f"drafts/scenes/{scene_id}.md",
            f"drafts/promotions/{scene_id}_promotion.json", f"{ctx.review}.json",
            f"{ctx.state_patch}.json", f"{patch}.md", f"{patch}.json",
            f"{patch}.agent_tasks.md", ctx.canon_review, *ctx.canon_formal_sources,
        ]),
        "context_trace": ctx.context_trace,
        "expected_outputs": [ctx.canon_review, f"{patch}.agent_completion.json"],
        "hard_constraints": [
            "Complete canon-evolve sidecar only after writing either a candidate canon patch/no-change rationale and a schema-valid semantic canon review with exact source digest.",
            "Do not apply canon; promotion to canon remains a separate review/approval route.",
        ],
        "style_constraints": [],
        "validation_gates": ["canon-evolve sidecar completion marker exists", "canon_patch_review.v1 semantic artifact passes"],
        "next_allowed_states": ["continuity-ledger-prepare"],
    }


def _ledger_review_prepare(ctx: SceneWritebackContext) -> dict[str, object]:
    return {
        "task_type": "deterministic-cli",
        "prompt_asset_id": "route.scene-development.continuity-ledger.v1",
        "command": f"python -m literary_engineering_studio_engine prepare-continuity-ledger-review <project> --scene {ctx.scene_rel}",
        "source_paths": [ctx.scene_rel, f"drafts/scenes/{ctx.scene_id}.md", ctx.ledger_delta],
        "context_trace": ctx.context_trace,
        "expected_outputs": [ctx.ledger_review, ctx.ledger_review_task],
        "hard_constraints": ["Bind the independent ledger review to the exact current delta digest."],
        "style_constraints": [],
        "validation_gates": ["ledger review template exists"],
        "next_allowed_states": ["continuity-ledger-review"],
    }


def _ledger_review(ctx: SceneWritebackContext) -> dict[str, object]:
    return {
        "task_type": "platform-agent-review",
        "prompt_asset_id": "route.scene-development.continuity-ledger.v1",
        "command": "",
        "source_paths": [
            ctx.scene_rel, f"drafts/scenes/{ctx.scene_id}.md", ctx.ledger_delta,
            ctx.ledger_review, ctx.ledger_review_task,
        ],
        "context_trace": ctx.context_trace,
        "expected_outputs": [ctx.ledger_review, f"reviews/continuity/{ctx.scene_id}_ledger_review.agent_completion.json"],
        "hard_constraints": [
            "Reviewer session differs from delta writer session; review does not edit formal ledgers.",
            "The lifecycle field is a fixed enum: write status=complete only when verdict=pass; do not invent status labels.",
        ],
        "style_constraints": [],
        "validation_gates": ["ledger review passes exact delta digest and independent session gate"],
        "next_allowed_states": ["continuity-ledger-apply"],
    }


def _ledger_apply(ctx: SceneWritebackContext) -> dict[str, object]:
    return {
        "task_type": "deterministic-cli",
        "prompt_asset_id": "route.scene-development.continuity-ledger.v1",
        "command": f"python -m literary_engineering_studio_engine apply-continuity-ledger <project> --scene {ctx.scene_rel}",
        "source_paths": [
            ctx.scene_rel, f"drafts/scenes/{ctx.scene_id}.md", ctx.ledger_delta, ctx.ledger_review,
        ],
        "context_trace": ctx.context_trace,
        "expected_outputs": [
            "plot/reader_questions/ledger.json", "plot/promises/ledger.json",
            f"plot/ledger_deltas/{ctx.scene_id}_apply.json",
        ],
        "hard_constraints": ["Only deterministic apply writes formal ledgers after independent review."],
        "style_constraints": [],
        "validation_gates": ["continuity ledger apply receipt exists"],
        "next_allowed_states": ["ready"],
    }


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


__all__ = ["SceneWritebackContext", "WRITEBACK_STATES", "writeback_blueprint_for_state"]
