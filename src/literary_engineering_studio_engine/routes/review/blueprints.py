"""State-specific task blueprints for project review and Canon apply."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ...literary.assets.canon.contracts import CANON_LINT_SOURCE_PATHS
from ...literary.review.longform_contract import LONGFORM_AUDIT_SOURCE_PATHS
from .evidence import project_review_repair_targets


@dataclass(frozen=True)
class ReviewBlueprintContext:
    patch: str
    patch_id: str
    patch_report: str
    patch_task: str
    patch_completion: str
    patch_review: str
    canon_review: str
    committee: str
    canon_repair_targets: tuple[str, ...]
    committee_repair_targets: tuple[str, ...]


def review_audit_blueprint_for_state(
    root: Path,
    current_state: str,
    next_action: str,
    state: dict[str, object] | None = None,
) -> dict[str, object]:
    context = _blueprint_context(root, state or {})
    builders = {
        "canon-patch-revision": _canon_patch_revision,
        "canon-patch-approval": _canon_patch_approval,
        "canon-patch-deferred": _canon_patch_deferred,
        "canon-patch-apply": _canon_patch_apply,
        "canon-lint-file": _canon_lint,
        "canon-review-task-file": _canon_review_prepare,
        "canon-review-agent-task": _canon_review_execute,
        "canon-review-pass": _canon_review_revise,
        "longform-audit-file": _longform_audit,
        "committee-task-file": _committee_prepare,
        "committee-agent-task": _committee_execute,
        "committee-pass": _committee_revise,
    }
    builder = builders.get(current_state)
    return builder(context) if builder else _route_repair(next_action)


def _blueprint_context(root: Path, state: dict[str, object]) -> ReviewBlueprintContext:
    patch = str(state.get("patch") or "")
    patch_id = str(state.get("patch_id") or (Path(patch).stem if patch else "canon-patch"))
    canon_review = "reviews/agent/canon_review"
    committee = "reviews/agent/committee_project-final-audit"
    return ReviewBlueprintContext(
        patch=patch,
        patch_id=patch_id,
        patch_report=_related_path(patch, ".md"),
        patch_task=_related_path(patch, ".agent_tasks.md"),
        patch_completion=_related_path(patch, ".agent_completion.json"),
        patch_review=_sibling_path(patch, "_review.json"),
        canon_review=canon_review,
        committee=committee,
        canon_repair_targets=tuple(
            project_review_repair_targets(
                root,
                root / f"{canon_review}.json",
                ("blocking_issues", "warnings", "unresolved_facts", "timeline_risks", "recommendations"),
            )
        ),
        committee_repair_targets=tuple(
            project_review_repair_targets(
                root,
                root / f"{committee}.json",
                ("action_items", "disagreements"),
            )
        ),
    )


def _related_path(path: str, suffix: str) -> str:
    return str(Path(path).with_suffix(suffix)).replace("\\", "/") if path else ""


def _sibling_path(path: str, suffix: str) -> str:
    if not path:
        return ""
    source = Path(path)
    return str(source.with_name(f"{source.stem}{suffix}")).replace("\\", "/")


def _canon_patch_revision(context: ReviewBlueprintContext) -> dict[str, object]:
    sources = [
        context.patch,
        context.patch_report,
        context.patch_task,
        context.patch_completion,
        context.patch_review,
        "workflow/approvals/index.jsonl",
        "canon",
        "scenes",
        "drafts/scenes",
    ]
    return _blueprint(
        "platform-agent-revision",
        "route.review-audit.canon-patch.fix.v1",
        "",
        [item for item in sources if item],
        [item for item in [context.patch, context.patch_report, context.patch_completion] if item],
        [
            "Revise only the current canon patch candidate and report against the recorded approval or validation findings.",
            "Do not edit durable canon files and do not mark the patch applied.",
            "Keep canon_change=true only for cross-scene durable facts; every item must retain exact evidence, target_files, risk, and approval requirements.",
            "After a real content change, complete the canon-evolve marker and request a fresh content-bound decision.",
        ],
        ["canon patch candidate changed", "canon patch schema is apply-ready", "canon-evolve completion is complete", "patch remains unapplied"],
        ["canon-patch-approval"],
        repair_targets=[item for item in [context.patch, context.patch_report] if item],
    )


def _canon_patch_approval(context: ReviewBlueprintContext) -> dict[str, object]:
    return _blueprint(
        "human-approval-boundary",
        "route.review-audit.canon-patch.approval.v1",
        f"Ask for a decision on canon patch `{context.patch_id}` and bind it to the current candidate SHA-256.",
        [
            item
            for item in [
                context.patch,
                context.patch_report,
                context.patch_task,
                context.patch_completion,
                context.patch_review,
                "workflow/approvals/index.jsonl",
            ]
            if item
        ],
        ["workflow/approvals/index.jsonl"],
        [
            "The writing Worker must not self-approve its own canon patch.",
            "Record approve, revise, reject, or defer against the exact current patch digest.",
            f"The approval run_id must be `{context.patch_id}`.",
        ],
        ["a current-content canon patch decision is recorded"],
        ["canon-patch-apply", "canon-patch-revision", "canon-patch-deferred"],
    )


def _canon_patch_deferred(context: ReviewBlueprintContext) -> dict[str, object]:
    return _blueprint(
        "human-approval-boundary",
        "route.review-audit.canon-patch.approval.v1",
        f"Canon patch `{context.patch_id}` is deferred. Resume it from the decision panel when ready.",
        [
            item
            for item in [
                context.patch,
                context.patch_report,
                context.patch_task,
                context.patch_completion,
                context.patch_review,
                "workflow/approvals/index.jsonl",
            ]
            if item
        ],
        ["workflow/approvals/index.jsonl"],
        ["Do not silently apply or discard a deferred canon patch."],
        ["user or delegated steward explicitly resumes the deferred patch"],
        ["canon-patch-apply", "canon-patch-revision"],
    )


def _canon_patch_apply(context: ReviewBlueprintContext) -> dict[str, object]:
    command = (
        "python -m literary_engineering_studio_engine canon-apply <project> "
        f"--patch {context.patch} --approval-run-id {context.patch_id}"
    )
    return _blueprint(
        "deterministic-cli",
        "route.review-audit.canon-patch.apply.v1",
        command,
        [
            item
            for item in [
                context.patch,
                context.patch_report,
                context.patch_task,
                context.patch_completion,
                context.patch_review,
                "workflow/approvals/index.jsonl",
            ]
            if item
        ],
        [
            context.patch,
            f"canon/applied/{context.patch_id}_apply.json",
            f"canon/applied/{context.patch_id}_apply.md",
            "canon/canon_change_log.md",
        ],
        [
            "Apply only the exact approved patch candidate.",
            "Do not use --allow-unapproved in formal operation.",
            "The apply manifest must preserve approval evidence and the pre-apply candidate digest.",
        ],
        ["patch status is applied", "apply manifest is valid", "approval digest matches applied candidate", "no approval bypass"],
        ["canon-lint-file"],
    )


def _canon_lint(_context: ReviewBlueprintContext) -> dict[str, object]:
    return _blueprint(
        "deterministic-cli",
        "route.review-audit.canon-lint.v1",
        "python -m literary_engineering_studio_engine canon-lint <project>",
        list(CANON_LINT_SOURCE_PATHS),
        ["reviews/canon_lint.md", "reviews/canon_lint.json"],
        [
            "Run canon-lint before any platform-agent project-level semantic review.",
            "Blocking canon-lint issues must be fixed or explicitly captured as candidate repair tasks before export.",
        ],
        ["canon-lint report exists", "canon-lint JSON schema/status is usable", "blocking_count is 0"],
        ["canon-review-task-file"],
    )


def _canon_review_prepare(context: ReviewBlueprintContext) -> dict[str, object]:
    return _blueprint(
        "deterministic-cli",
        "route.review-audit.canon-review.prepare.v1",
        "python -m literary_engineering_studio_engine agent-canon-review <project>",
        ["reviews/canon_lint.md", "reviews/canon_lint.json", "canon", "characters", "plot", "scenes"],
        [f"{context.canon_review}.agent_tasks.md"],
        [
            "Run agent-canon-review only to create a platform-agent sidecar.",
            "The command prepares the task; the platform agent writes canon_review.v1 JSON/Markdown.",
        ],
        ["canon review sidecar exists"],
        ["canon-review-agent-task"],
    )


def _canon_review_execute(context: ReviewBlueprintContext) -> dict[str, object]:
    review = context.canon_review
    return _blueprint(
        "platform-agent-review",
        "route.review-audit.canon-review.execute.v1",
        "",
        ["reviews/canon_lint.md", "reviews/canon_lint.json", f"{review}.agent_tasks.md", "canon", "characters", "plot", "scenes"],
        [f"{review}.json", f"{review}.md", f"{review}.agent_completion.json"],
        [
            "Read canon lint, canon files, characters, scenes, plot, and write canon_review.v1.",
            "pass_with_notes is not a clean release gate; unresolved facts and timeline risks must become repair tasks or be resolved.",
            "Treat lint severity=info as context only; do not promote it to warnings, unresolved_facts, or repair recommendations without independent contradictory evidence.",
            "A non-pass conclusion is a valid completed review. Every actionable finding must name one exact target_path under canon/, characters/, plot/, scenes/, or drafts/candidates/.",
            "Do not call local providers. The host platform agent is the reviewer.",
        ],
        ["canon review sidecar completed", "canon_review.v1 validates", "canon review conclusion is recorded"],
        ["canon-review-pass", "longform-audit-file"],
    )


def _canon_review_revise(context: ReviewBlueprintContext) -> dict[str, object]:
    review = context.canon_review
    targets = list(context.canon_repair_targets)
    review_json = f"{review}.json"
    completion = f"{review}.agent_completion.json"
    return _blueprint(
        "platform-agent-revision",
        "route.review-audit.canon-review.fix.v1",
        "",
        [f"{review}.json", f"{review}.md", "reviews/canon_lint.json", *targets],
        [*targets, review_json, completion],
        [
            "Resolve every finding only in its declared target_path; do not touch files outside Allowed Outputs.",
            "Do not relabel unresolved findings as warnings to pass the gate.",
            "Read every existing repair target before replacing it and preserve all unaffected structure and facts.",
            "Follow every canon-lint allowed_values and repair_hint exactly; never invent lifecycle labels or trade one warning for a different warning.",
            "Do not write canon-lint or CanonReview lifecycle artifacts; Studio resets them and reruns deterministic lint plus a fresh independent review after import.",
        ],
        ["at least one declared repair target changed", "refreshed canon lint has zero blocking issues and zero warnings", "canon review reset to recheck_required"],
        ["canon-lint-file"],
        repair_targets=targets,
        core_managed_outputs=[review_json],
    )


def _longform_audit(_context: ReviewBlueprintContext) -> dict[str, object]:
    return _blueprint(
        "deterministic-cli",
        "route.review-audit.longform-audit.v1",
        "python -m literary_engineering_studio_engine longform-audit <project>",
        list(LONGFORM_AUDIT_SOURCE_PATHS),
        ["reviews/longform/longform_audit.md", "reviews/longform/longform_audit.json", "plot/longform_graph.json"],
        [
            "Run longform-audit after canon review so the committee sees structural risks, word-budget gaps, and chapter readiness.",
            "Longform audit facts are evidence; the committee must still make semantic judgment.",
        ],
        ["longform audit JSON exists", "longform audit schema is valid", "longform graph exists"],
        ["committee-task-file"],
    )


def _committee_prepare(context: ReviewBlueprintContext) -> dict[str, object]:
    review = context.canon_review
    return _blueprint(
        "deterministic-cli",
        "route.review-audit.committee.prepare.v1",
        "python -m literary_engineering_studio_engine agent-committee <project> --subject project-final-audit --source reviews/agent/canon_review.md",
        [f"{review}.md", f"{review}.json", "reviews/longform/longform_audit.md", "reviews/longform/longform_audit.json"],
        [f"{context.committee}.agent_tasks.md"],
        [
            "Run agent-committee only to create a platform-agent sidecar.",
            "Committee review must inspect canon review and longform audit; it cannot approve by vibe.",
        ],
        ["committee sidecar exists"],
        ["committee-agent-task"],
    )


def _committee_execute(context: ReviewBlueprintContext) -> dict[str, object]:
    committee = context.committee
    review = context.canon_review
    return _blueprint(
        "platform-agent-review",
        "route.review-audit.committee.execute.v1",
        "",
        [f"{committee}.agent_tasks.md", f"{review}.json", f"{review}.md", "reviews/longform/longform_audit.json", "reviews/longform/longform_audit.md"],
        [f"{committee}.json", f"{committee}.md", f"{committee}.agent_completion.json"],
        [
            "Act as a multi-perspective review committee: chief editor, character psychology, canon auditor, style auditor, readability, and anti-homogeneity.",
            "final_recommendation=approve is allowed only when no action_items or disagreements remain.",
            "approve_with_notes, revise, reject, action_items, or disagreements block export readiness.",
            "A non-approve recommendation is a valid completed committee review. Each action item or disagreement that requires repair must name an exact target_path.",
        ],
        ["committee sidecar completed", "committee_review.v1 validates", "final_recommendation is recorded"],
        ["committee-pass"],
    )


def _committee_revise(context: ReviewBlueprintContext) -> dict[str, object]:
    committee = context.committee
    review = context.canon_review
    targets = list(context.committee_repair_targets)
    canon_review_json = f"{review}.json"
    canon_completion = f"{review}.agent_completion.json"
    committee_json = f"{committee}.json"
    committee_completion = f"{committee}.agent_completion.json"
    return _blueprint(
        "platform-agent-revision",
        "route.review-audit.committee.fix.v1",
        "",
        [f"{committee}.json", f"{committee}.md", f"{review}.json", "reviews/longform/longform_audit.json", *targets],
        [
            *targets,
            canon_review_json,
            canon_completion,
            committee_json,
            committee_completion,
        ],
        [
            "Resolve every committee action item and disagreement only in its declared target_path.",
            "Do not move to export-and-release on approve_with_notes.",
            "Read every existing repair target before replacing it and preserve all unaffected structure and facts.",
            "Do not write canon-lint, longform-audit, CanonReview, or Committee lifecycle artifacts; Studio resets and reruns them after import.",
        ],
        ["at least one declared repair target changed", "canon and committee reviews reset to recheck_required"],
        ["canon-lint-file"],
        repair_targets=targets,
        core_managed_outputs=[canon_review_json, committee_json],
    )


def _route_repair(next_action: str) -> dict[str, object]:
    return _blueprint(
        "manual-route-repair",
        "route.review-audit.repair.v1",
        next_action,
        ["reviews", "canon", "characters", "plot", "scenes"],
        [],
        [next_action or "Inspect workflow-state and route-audit, then repair the missing review-and-audit gate."],
        ["review-and-audit gate resolved"],
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
    repair_targets: list[str] | None = None,
    core_managed_outputs: list[str] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "task_type": task_type,
        "prompt_asset_id": prompt_asset_id,
        "command": command,
        "source_paths": source_paths,
        "expected_outputs": expected_outputs,
        "hard_constraints": hard_constraints,
        "style_constraints": [],
        "validation_gates": validation_gates,
        "next_allowed_states": next_allowed_states,
    }
    if repair_targets is not None:
        payload["repair_targets"] = repair_targets
    if core_managed_outputs is not None:
        payload["core_managed_outputs"] = core_managed_outputs
    return payload
