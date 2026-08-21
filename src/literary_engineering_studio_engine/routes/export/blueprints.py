"""Immutable task blueprints for chapter export and release."""

from __future__ import annotations

from pathlib import Path

from ...literary.export.approval_evidence import (
    release_approval_evidence_paths,
    release_approval_scope,
)
from ...literary.export.contracts import (
    chapter_workspace_source_paths,
    export_package_source_paths,
    publish_chapter_source_paths,
)


def export_release_blueprint_for_state(
    root: Path,
    chapter_id: str,
    current_state: str,
    next_action: str,
) -> dict[str, object]:
    builders = {
        "chapter-workspace": _chapter_workspace,
        "export-package": _export_package,
        "target-length-repair-plan": _target_length_repair_plan,
        "release-approval": _release_approval,
        "release-revision-required": _release_revision,
        "publish-release": _publish_release,
    }
    builder = builders.get(current_state)
    if builder in {
        _chapter_workspace,
        _export_package,
        _release_approval,
        _publish_release,
    }:
        return builder(root, chapter_id)
    return builder(chapter_id) if builder else _repair(chapter_id, next_action)


def _target_length_repair_plan(_chapter_id: str) -> dict[str, object]:
    return {
        "task_type": "deterministic-cli",
        "prompt_asset_id": "route.export-release.length-repair.v1",
        "command": "python -m literary_engineering_studio_engine plan-length-repair <project>",
        "source_paths": [
            "project.yaml",
            "plot/word_budget",
            "plot/outline.md",
            "scenes",
            "drafts/scenes",
            "workflow/longform_materialization.json",
        ],
        "expected_outputs": [
            "reviews/longform/target_length_repair.json",
            "reviews/longform/target_length_repair.md",
        ],
        "hard_constraints": [
            "Allocate only the exact whole-work Chinese-content shortfall.",
            "Prefer scenes below their own target and never exceed scene max_chinese_chars.",
            "This deterministic task plans repair; it does not write or approve prose.",
        ],
        "style_constraints": [],
        "validation_gates": [
            "repair plan binds to current word budget",
            "allocated growth equals shortfall",
            "every allocation stays within scene capacity",
        ],
        "next_allowed_states": ["target-length-repair-scenes"],
    }


def _chapter_workspace(root: Path, chapter_id: str) -> dict[str, object]:
    return {
        "task_type": "deterministic-cli",
        "prompt_asset_id": "route.export-release.chapter-workspace.v1",
        "command": f"python -m literary_engineering_studio_engine chapter-workspace <project> --chapter-id {chapter_id}",
        "source_paths": list(chapter_workspace_source_paths(root, chapter_id)),
        "expected_outputs": [f"drafts/chapters/{chapter_id}.md", f"plot/chapters/{chapter_id}.json"],
        "hard_constraints": [
            "Rebuild or verify chapter workspace immediately before export.",
            "Every scene must be ready with formal flow gates, static review pass, exact-candidate AgentReview pass, and no unresolved notes.",
        ],
        "style_constraints": [
            "Final body extraction must exclude workflow traces, canon notes, state patches, review notes, and scene ids."
        ],
        "validation_gates": ["chapter workspace exists", "blocked_count is 0", "ready_count > 0"],
        "next_allowed_states": ["export-package"],
    }


def _export_package(root: Path, chapter_id: str) -> dict[str, object]:
    prefix = f"exports/{chapter_id}/{chapter_id}"
    expected_outputs = [
        f"exports/{chapter_id}/export_manifest.json",
        f"{prefix}_novel.md",
        f"{prefix}_screenplay.md",
        f"{prefix}_video_prompt_pack.md",
        f"{prefix}_novel.docx",
        f"{prefix}_novel.layout.json",
        f"{prefix}_novel.inspection.json",
        f"{prefix}_screenplay.docx",
        f"{prefix}_screenplay.layout.json",
        f"{prefix}_screenplay.inspection.json",
        f"{prefix}_video_prompt_pack.docx",
        f"{prefix}_video_prompt_pack.layout.json",
        f"{prefix}_video_prompt_pack.inspection.json",
    ]
    return {
        "task_type": "deterministic-cli",
        "prompt_asset_id": "route.export-release.package.v1",
        "command": f"python -m literary_engineering_studio_engine export-package <project> --chapter-id {chapter_id} --formats md,docx",
        "source_paths": list(export_package_source_paths(root, chapter_id)),
        "expected_outputs": expected_outputs,
        "hard_constraints": [
            "Do not use --include-blocked in formal Skill-host work.",
            "Export manifest must have zero skipped scenes and include_blocked=false.",
            "Final outputs must filter scene ids, canon notes, review notes, state patches, AGENT_TASK markers, and writeback candidates.",
        ],
        "style_constraints": [
            "Normalize punctuation for delivery; maintain Chinese quote standard and no raw workbench traces."
        ],
        "validation_gates": [
            "export manifest exists",
            "skipped_scenes is empty",
            "include_blocked is false",
            "delivery outputs exist",
        ],
        "next_allowed_states": ["release-approval"],
    }


def _release_approval(root: Path, chapter_id: str) -> dict[str, object]:
    run_id = f"release-{chapter_id}"
    scope = release_approval_scope(root, chapter_id)
    scope_constraint = (
        "This is the final formal chapter: evaluate whole-work evidence only after the deterministic whole-work target gate has passed."
        if scope["is_final_chapter"] == "true"
        else "This is a non-final chapter approval: do not use whole-work target length or final-project audit as a reason to revise this chapter."
    )
    return {
        "task_type": "human-approval-boundary",
        "prompt_asset_id": "route.export-release.approval.v1",
        "command": f"Ask the user whether to approve chapter `{chapter_id}` for release; record approve decision with run_id `{run_id}`.",
        "source_paths": list(release_approval_evidence_paths(root, chapter_id)),
        "expected_outputs": ["workflow/approvals/index.jsonl"],
        "hard_constraints": [
            "The executing Worker must not self-approve release publication. Approval may come from the user or a separately identified Creative Steward when the active DelegationPolicy explicitly delegates release.",
            "If the user requests revision or rejection, record that decision and return to the relevant review/export task.",
            scope_constraint,
            "A delegated decision must bind to the current scoped evidence context as well as the exported delivery fingerprint.",
            f"Approval run_id must be `{run_id}` so publish-chapter can verify it.",
        ],
        "style_constraints": [],
        "validation_gates": [f"approve record exists for {run_id}"],
        "next_allowed_states": ["publish-release"],
    }


def _release_revision(chapter_id: str) -> dict[str, object]:
    return {
        "task_type": "human-approval-boundary",
        "prompt_asset_id": "route.export-release.approval.v1",
        "command": f"Release `{chapter_id}` was rejected or returned for revision. Select the affected scene-development work before rebuilding export.",
        "source_paths": [
            f"exports/{chapter_id}/export_manifest.json",
            f"drafts/chapters/{chapter_id}.md",
            "workflow/approvals/index.jsonl",
            "reviews/agent",
        ],
        "expected_outputs": ["workflow/approvals/index.jsonl"],
        "hard_constraints": [
            "Do not regenerate the same export and ask for the same approval again.",
            "Return requested prose changes through scene revision, exact-candidate AgentReview, promotion, and chapter workspace before a fresh export.",
            "A new release decision must bind to the rebuilt export fingerprint.",
        ],
        "style_constraints": [],
        "validation_gates": ["affected scene revisions are explicitly selected before workflow resumes"],
        "next_allowed_states": ["chapter-workspace"],
    }


def _publish_release(root: Path, chapter_id: str) -> dict[str, object]:
    run_id = f"release-{chapter_id}"
    release_dir = f"releases/{chapter_id}/formal-release"
    return {
        "task_type": "deterministic-cli",
        "prompt_asset_id": "route.export-release.publish.v1",
        "command": f"python -m literary_engineering_studio_engine publish-chapter <project> --chapter-id {chapter_id} --release-id formal-release --approval-run-id {run_id} --export-formats md,docx --overwrite",
        "source_paths": list(publish_chapter_source_paths(root, chapter_id)),
        "expected_outputs": [
            f"{release_dir}/publish_manifest.json",
            f"{release_dir}/release_notes.md",
            f"{release_dir}/rollback.md",
            f"{release_dir}/{chapter_id}_novel.md",
            f"{release_dir}/{chapter_id}_screenplay.md",
            f"{release_dir}/{chapter_id}_video_prompt_pack.md",
            f"{release_dir}/source_export_manifest.json",
            f"{release_dir}/{chapter_id}_novel.docx",
            f"{release_dir}/{chapter_id}_screenplay.docx",
            f"{release_dir}/{chapter_id}_video_prompt_pack.docx",
            f"releases/{chapter_id}/latest.json",
            "reviews/canon_lint.md",
            "reviews/canon_lint.json",
        ],
        "hard_constraints": [
            "Do not use --allow-unapproved in formal Skill-host work.",
            "Published manifest must have status=published and copied delivery outputs.",
            "Overwrite formal-release only inside the isolated task sandbox and only after the current content-and-context approval Gate has passed.",
        ],
        "style_constraints": [],
        "validation_gates": [
            "publish manifest exists",
            "status is published",
            "latest.json points to release",
            "no approval bypass",
        ],
        "next_allowed_states": ["ready"],
    }


def _repair(chapter_id: str, next_action: str) -> dict[str, object]:
    return {
        "task_type": "manual-route-repair",
        "prompt_asset_id": "route.export-release.repair.v1",
        "command": next_action,
        "source_paths": [
            f"plot/chapters/{chapter_id}.json",
            f"exports/{chapter_id}",
            f"releases/{chapter_id}",
        ],
        "expected_outputs": [],
        "hard_constraints": [
            next_action or "Inspect workflow-state and route-audit, then repair the missing export-and-release gate."
        ],
        "style_constraints": [],
        "validation_gates": ["export-and-release gate resolved"],
        "next_allowed_states": [],
    }


__all__ = ["export_release_blueprint_for_state"]
