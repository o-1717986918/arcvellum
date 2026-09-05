"""State-specific TaskPackage blueprints for project asset engineering."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ...agent_tasks import default_agent_completion_path
from ...asset_context import compact_asset_context_relpaths
from ...task_paths import relative_path as _rel
from ...task_paths import resolve_project_path as _resolve_project_path
from .evidence import (
    asset_promoted_output_rels,
    asset_promotion_group,
    asset_promotion_sources,
    pending_revision_action_ids,
    revision_evidence_requirement,
    worker_managed_revision_evidence_requirement,
)


@dataclass(frozen=True)
class AssetBlueprintContext:
    candidate_id: str
    asset_type: str
    candidate: str
    candidate_report: str
    creation_task: str
    creation_completion: str
    review: str
    review_json: str
    review_task: str
    review_completion: str
    promotion: str
    promotion_report: str
    promotion_group: str
    promoted_outputs: tuple[str, ...]
    type_hint: str
    compact_context: tuple[str, ...]
    pending_revision_ids: tuple[str, ...]


def asset_blueprint_for_state(
    root: Path,
    candidate_id: str,
    asset_type: str,
    candidate: str,
    current_state: str,
    next_action: str,
) -> dict[str, object]:
    context = _blueprint_context(root, candidate_id, asset_type, candidate)
    builders = {
        "asset-intake": _asset_intake,
        "asset-creation-agent-task": _asset_creation,
        "asset-review-task-file": _asset_review_prepare,
        "asset-review-agent-task": _asset_review_execute,
        "asset-review-pass": _asset_review_revise,
        "asset-approval-revision": _asset_approval_revise,
        "asset-approval": _asset_approval,
        "asset-promotion": _asset_promotion,
    }
    builder = builders.get(current_state)
    return builder(context) if builder else _route_repair(context, next_action)


def _blueprint_context(
    root: Path,
    candidate_id: str,
    asset_type: str,
    candidate: str,
) -> AssetBlueprintContext:
    candidate_path = (
        _resolve_project_path(root, candidate)
        if candidate
        else root / "characters" / "candidates" / f"{candidate_id}.json"
    )
    review_base = f"reviews/assets/{candidate_id}_review"
    compact_context = tuple(compact_asset_context_relpaths(root))
    return AssetBlueprintContext(
        candidate_id=candidate_id,
        asset_type=asset_type,
        candidate=candidate,
        candidate_report=_rel(candidate_path.with_suffix(".md"), root),
        creation_task=_rel(candidate_path.with_suffix(".agent_tasks.md"), root),
        creation_completion=_rel(default_agent_completion_path(candidate_path.with_suffix(".agent_tasks.md")), root),
        review=f"{review_base}.md",
        review_json=f"{review_base}.json",
        review_task=f"{review_base}.agent_tasks.md",
        review_completion=f"{review_base}.agent_completion.json",
        promotion=f"workflow/asset_promotions/{candidate_id}_promotion.json",
        promotion_report=f"workflow/asset_promotions/{candidate_id}_promotion.md",
        promotion_group=asset_promotion_group(asset_type),
        promoted_outputs=tuple(asset_promoted_output_rels(root, candidate_path, asset_type)),
        type_hint=asset_type or "<character|background-story|relationship|world|location|organization|outline|chapter-plan|scene-list>",
        compact_context=compact_context,
        pending_revision_ids=tuple(pending_revision_action_ids(root / f"{review_base}.json")),
    )


def _asset_intake(context: AssetBlueprintContext) -> dict[str, object]:
    return _blueprint(
        "deterministic-cli",
        "route.character-world-assets.intake.v1",
        "python -m literary_engineering_studio_engine seed-project-assets <project>",
        list(context.compact_context),
        [
            "canon/candidates/world_rules/world-foundation.agent_tasks.md",
            "characters/candidates/protagonist-foundation.agent_tasks.md",
        ],
        [
            "Run seed-project-assets to create stable world-foundation and protagonist-foundation platform-agent sidecars.",
            "This deterministic step creates task contracts only; it does not invent or promote canon and character facts.",
            "The platform agent must not write directly to confirmed canon, character files, outline, scenes, drafts, exports, or releases.",
        ],
        ["world and protagonist asset creation sidecars exist"],
        ["asset-creation-agent-task"],
    )


def _asset_creation(context: AssetBlueprintContext) -> dict[str, object]:
    return _blueprint(
        "platform-agent-asset-creation",
        "route.character-world-assets.create.v1",
        "",
        [*context.compact_context, context.creation_task],
        [context.candidate, context.candidate_report, context.creation_completion],
        [
            f"Read the asset creation sidecar and write a {context.type_hint} candidate asset, not a confirmed project file.",
            "Candidate JSON must satisfy its schema and include candidate_id, risks, source_paths, and promotion_notes.",
            "Character and background-story assets must preserve background_story as hidden behavioral causality, not exposition.",
        ],
        ["asset creation sidecar completed", "candidate JSON exists", "candidate report exists", "candidate schema validates"],
        ["asset-review-task-file"],
        style_constraints=["Mounted style may inform names/tone but cannot override canon, world rules, or user constraints."],
    )


def _asset_review_prepare(context: AssetBlueprintContext) -> dict[str, object]:
    return _blueprint(
        "deterministic-cli",
        "route.character-world-assets.review.prepare.v1",
        f"python -m literary_engineering_studio_engine review-candidate-asset <project> {context.candidate}",
        [context.candidate, context.candidate_report, *context.compact_context],
        [context.review_task],
        [
            "Run review-candidate-asset to create a formal platform-agent asset review sidecar.",
            "The command prepares the review task; the platform agent still performs the semantic review.",
        ],
        ["asset review sidecar exists"],
        ["asset-review-agent-task"],
    )


def _asset_review_execute(context: AssetBlueprintContext) -> dict[str, object]:
    return _blueprint(
        "platform-agent-asset-review",
        "route.character-world-assets.review.execute.v1",
        "",
        [context.candidate, context.candidate_report, context.review_task, *context.compact_context],
        [context.review, context.review_json, context.review_completion],
        [
            "Review candidate asset against schema, canon, character logic, originality, hidden background-story policy, and promotion risk.",
            "Write JSON with status pass|failed|revise_required plus blocking_issues, warnings, revision_actions, and promotion_risks.",
            "Revision actions may modify only the current candidate and its report. Put dependencies on other characters, canon assets, scenes, or routes into warnings/promotion_risks instead of blocking this candidate.",
            "Do not use review as approval. A clean review only permits asking the user whether to approve promotion.",
        ],
        [
            "asset review sidecar completed",
            "review JSON exists",
            "review Markdown exists",
            "review status is recorded as pass|failed|revise_required",
        ],
        ["asset-review-pass", "asset-approval"],
    )


def _asset_review_revise(context: AssetBlueprintContext) -> dict[str, object]:
    evidence = revision_evidence_requirement(list(context.pending_revision_ids))
    return _blueprint(
        "platform-agent-revision",
        "route.character-world-assets.review-fix.v1",
        "",
        [context.candidate, context.review, context.review_json],
        [context.candidate, context.candidate_report, context.review, context.review_json, context.review_completion],
        [
            "Resolve every blocking issue and revision action in the candidate asset before asking for approval.",
            "Do not create files outside Allowed Outputs. If an old review action asks for another asset or route, preserve it as a follow-up warning/promotion risk and revise only candidate-local findings.",
            "Do not bury revise_required findings as harmless warnings.",
            "Do not self-pass the review that requested this revision and do not replace critical findings with a clean verdict.",
            evidence,
            "After revising the candidate and candidate report, preserve the previous findings as applied_revision_actions, set review status to recheck_required, and reset the review completion marker to recheck_required with expected_artifacts_checked=false.",
            "A fresh asset-review-agent-task must independently inspect the revised candidate before approval is possible.",
        ],
        [
            "candidate schema validates",
            "candidate content changed from pre-revision sha256",
            "review status is recheck_required",
            "applied_revision_actions recorded",
            "review completion evidence reset for independent recheck",
        ],
        ["asset-review-agent-task"],
    )


def _asset_approval_revise(context: AssetBlueprintContext) -> dict[str, object]:
    evidence = worker_managed_revision_evidence_requirement(list(context.pending_revision_ids))
    return _blueprint(
        "platform-agent-revision",
        "route.character-world-assets.approval-fix.v1",
        "",
        [context.candidate, context.candidate_report, context.review, context.review_json, "workflow/approvals/index.jsonl"],
        [context.candidate, context.candidate_report, context.review, context.review_json, context.review_completion],
        [
            "Revise only the current candidate and its report against the latest matching approval decision rationale.",
            "A revise or reject approval is not permission to approve, promote, or edit confirmed project assets.",
            evidence,
            "After a real candidate change, Studio Worker records the approval rationale in applied_revision_actions, sets the prior review to recheck_required, and resets its completion marker for independent review.",
            "Do not self-pass the revised candidate; a fresh review and a new approval bound to the new candidate digest are mandatory.",
        ],
        [
            "candidate content changed from the approval-bound sha256",
            "candidate schema validates",
            "review status is recheck_required",
            "applied_revision_actions record the approval rationale",
            "review completion evidence reset for independent recheck",
        ],
        ["asset-review-agent-task"],
        core_managed_outputs=[context.review, context.review_json, context.review_completion],
    )


def _asset_approval(context: AssetBlueprintContext) -> dict[str, object]:
    return _blueprint(
        "human-approval-boundary",
        "route.character-world-assets.approval.v1",
        f"Ask the user whether to approve candidate `{context.candidate_id}` for promotion; record approve decision with run_id `{context.candidate_id}` through the platform approval mechanism.",
        [context.candidate, context.review, context.review_json, "workflow/approvals/index.jsonl"],
        ["workflow/approvals/index.jsonl"],
        [
            "The executing Worker must not self-approve candidate promotion. Approval may come from the user or a separately identified Creative Steward under an active DelegationPolicy.",
            "If the user asks for revision or rejection, record that decision and do not promote.",
            "Approval must reference the candidate_id/run_id that promote-candidate-asset will use.",
        ],
        ["approve record exists for candidate_id"],
        ["asset-promotion"],
    )


def _asset_promotion(context: AssetBlueprintContext) -> dict[str, object]:
    command = (
        "python -m literary_engineering_studio_engine promote-candidate-asset <project> "
        f"{context.candidate} --group {context.promotion_group or '<group>'} --approval-run-id {context.candidate_id}"
    )
    return _blueprint(
        "deterministic-cli",
        "route.character-world-assets.promote.v1",
        command,
        asset_promotion_sources(context.candidate, context.candidate_id),
        [context.promotion, context.promotion_report, *context.promoted_outputs],
        [
            "Promote only after clean review and matching approve record.",
            "Do not use --allow-unapproved in formal Skill-host work.",
            "After promotion, run canon-lint or the relevant downstream route before relying on the new project facts.",
        ],
        ["promotion manifest exists", "allow_unapproved is false", "promotion outputs exist"],
        ["ready"],
    )


def _route_repair(context: AssetBlueprintContext, next_action: str) -> dict[str, object]:
    sources = [context.candidate] if context.candidate else ["project.yaml", "canon", "characters", "plot"]
    return _blueprint(
        "route-diagnostic-boundary",
        "route.character-world-assets.repair.v1",
        next_action,
        sources,
        [],
        [next_action or "Inspect workflow-state and repair the missing character/world asset gate."],
        ["character/world asset gate resolved"],
        [],
    )


def _blueprint(
    task_type: str,
    prompt_asset_id: str,
    command: str,
    source_paths: list[str],
    expected_outputs: list[str],
    hard_constraints: list[str],
    validation_gates: list[str],
    next_allowed_states: list[str],
    *,
    style_constraints: list[str] | None = None,
    core_managed_outputs: list[str] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "task_type": task_type,
        "prompt_asset_id": prompt_asset_id,
        "command": command,
        "source_paths": source_paths,
        "expected_outputs": expected_outputs,
        "hard_constraints": hard_constraints,
        "style_constraints": style_constraints or [],
        "validation_gates": validation_gates,
        "next_allowed_states": next_allowed_states,
    }
    if core_managed_outputs is not None:
        payload["core_managed_outputs"] = core_managed_outputs
    return payload
