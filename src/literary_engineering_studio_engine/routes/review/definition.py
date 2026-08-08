"""Formal task blueprint and Gate logic for project-level review and Canon apply.

The route turns Canon patch candidates into durable project facts only through
content-bound approval, then runs independent Canon and committee reviews before
any export route is considered ready.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from ...agent_schema import validate_payload
from ...agent_tasks import agent_task_completion_status, default_agent_completion_path
from ...literary.review.longform_contract import longform_audit_gate_errors
from ...task_paths import (
    TASK_SCHEMA,
    normalize_relative_path as _normalize_rel,
    now as _now,
    read_json as _read_json,
    relative_path as _rel,
    resolve_project_path as _resolve_project_path,
    task_id as _task_id,
)
def _build_review_audit_task_payload(root: Path, route: str, state: dict[str, object]) -> dict[str, object]:
    current_state = str(state.get("current_step") or "")
    next_action = str(state.get("next_action") or "")
    blueprint = _review_audit_blueprint_for_state(root, current_state, next_action, state)
    target_id = str(state.get("patch_id") or "project-review")
    task_id = _task_id(route, target_id, current_state)
    expected_outputs = _unique([_normalize_rel(item) for item in blueprint["expected_outputs"]])
    source_paths = _unique([_normalize_rel(item) for item in blueprint["source_paths"]])
    now = _now()
    payload = {
        "schema": TASK_SCHEMA,
        "task_id": task_id,
        "status": "issued",
        "created_at": now,
        "route": route,
        "scene_id": str(state.get("scene_id") or "project-review"),
        "target_id": target_id,
        "patch": str(state.get("patch") or ""),
        "patch_id": str(state.get("patch_id") or ""),
        "candidate_sha256": str(state.get("candidate_sha256") or ""),
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
                "references/artifact-contracts.md",
                "references/workflows.md",
                "docs/implementation/phase30-agent-canon-review.md",
                "docs/implementation/phase33-agent-review-committee.md",
                "docs/implementation/phase8-longform-audit.md",
            ],
        ),
        "source_paths": source_paths,
        "context_trace": blueprint.get("context_trace", ""),
        "hard_constraints": blueprint["hard_constraints"],
        "style_constraints": blueprint["style_constraints"],
        "word_count_target": 0,
        "word_count_min": 0,
        "word_count_max": 0,
        "expected_outputs": expected_outputs,
        "submission_command": f"python -m literary_engineering_studio_engine task-submit <project> --task-id {task_id} --from <artifact>",
        "completion_command": f"python -m literary_engineering_studio_engine task-complete <project> --task-id {task_id}",
        "validation_gates": blueprint["validation_gates"],
        "forbidden_shortcuts": [
            "Do not treat canon-lint or longform-audit as a semantic review by themselves.",
            "Do not use local dry-run/http-chat provider output as the formal review judgment.",
            "Do not let review pass_with_notes, unresolved facts, timeline risks, committee action_items, or disagreements move into export/release.",
            "A semantic review task must not edit project sources. A formal revision task may edit only its exact declared repair_targets inside the isolated sandbox.",
            "Do not treat this task as complete until task-submit and task-complete have succeeded.",
        ],
        "next_allowed_states": blueprint["next_allowed_states"],
    }
    repair_targets = [str(item) for item in blueprint.get("repair_targets", [])]
    if repair_targets:
        payload["repair_targets"] = repair_targets
        payload["repair_target_sha256_before_revision"] = {
            relative: _file_sha256(_resolve_project_path(root, relative))
            for relative in repair_targets
            if _resolve_project_path(root, relative).is_file()
        }
    return payload

def _project_review_repair_targets(root: Path, review_path: Path, fields: tuple[str, ...]) -> list[str]:
    if not review_path.is_file():
        return []
    payload = _read_json(review_path)
    allowed_prefixes = ("canon/", "characters/", "plot/", "scenes/", "drafts/candidates/")
    targets: list[str] = []
    for field in fields:
        items = payload.get(field) if isinstance(payload.get(field), list) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            target = str(item.get("target_path") or item.get("target") or "").replace("\\", "/").strip()
            target = target.split("#", 1)[0]
            if (
                target
                and not Path(target).is_absolute()
                and ".." not in Path(target).parts
                and target.startswith(allowed_prefixes)
                and Path(target).suffix.lower() in {".md", ".json", ".yaml", ".yml", ".csv"}
            ):
                targets.append(target)
    return _unique(targets)


def _review_audit_blueprint_for_state(
    root: Path,
    current_state: str,
    next_action: str,
    state: dict[str, object] | None = None,
) -> dict[str, object]:
    state = state or {}
    patch = str(state.get("patch") or "")
    patch_id = str(state.get("patch_id") or (Path(patch).stem if patch else "canon-patch"))
    patch_report = str(Path(patch).with_suffix(".md")).replace("\\", "/") if patch else ""
    patch_task = str(Path(patch).with_suffix(".agent_tasks.md")).replace("\\", "/") if patch else ""
    patch_completion = str(Path(patch).with_suffix(".agent_completion.json")).replace("\\", "/") if patch else ""
    canon_review = "reviews/agent/canon_review"
    committee = "reviews/agent/committee_project-final-audit"
    canon_repair_targets = _project_review_repair_targets(
        root,
        root / f"{canon_review}.json",
        ("blocking_issues", "warnings", "unresolved_facts", "timeline_risks", "recommendations"),
    )
    committee_repair_targets = _project_review_repair_targets(
        root,
        root / f"{committee}.json",
        ("action_items", "disagreements"),
    )
    table: dict[str, dict[str, object]] = {
        "canon-patch-revision": {
            "task_type": "platform-agent-revision",
            "prompt_asset_id": "route.review-audit.canon-patch.fix.v1",
            "command": "",
            "source_paths": [item for item in [patch, patch_report, patch_task, patch_completion, "workflow/approvals/index.jsonl", "canon", "scenes", "drafts/scenes"] if item],
            "expected_outputs": [item for item in [patch, patch_report, patch_completion] if item],
            "repair_targets": [item for item in [patch, patch_report] if item],
            "hard_constraints": [
                "Revise only the current canon patch candidate and report against the recorded approval or validation findings.",
                "Do not edit durable canon files and do not mark the patch applied.",
                "Keep canon_change=true only for cross-scene durable facts; every item must retain exact evidence, target_files, risk, and approval requirements.",
                "After a real content change, complete the canon-evolve marker and request a fresh content-bound decision.",
            ],
            "style_constraints": [],
            "validation_gates": ["canon patch candidate changed", "canon patch schema is apply-ready", "canon-evolve completion is complete", "patch remains unapplied"],
            "next_allowed_states": ["canon-patch-approval"],
        },
        "canon-patch-approval": {
            "task_type": "human-approval-boundary",
            "prompt_asset_id": "route.review-audit.canon-patch.approval.v1",
            "command": f"Ask for a decision on canon patch `{patch_id}` and bind it to the current candidate SHA-256.",
            "source_paths": [item for item in [patch, patch_report, "workflow/approvals/index.jsonl"] if item],
            "expected_outputs": ["workflow/approvals/index.jsonl"],
            "hard_constraints": [
                "The writing Worker must not self-approve its own canon patch.",
                "Record approve, revise, reject, or defer against the exact current patch digest.",
                f"The approval run_id must be `{patch_id}`.",
            ],
            "style_constraints": [],
            "validation_gates": ["a current-content canon patch decision is recorded"],
            "next_allowed_states": ["canon-patch-apply", "canon-patch-revision", "canon-patch-deferred"],
        },
        "canon-patch-deferred": {
            "task_type": "human-approval-boundary",
            "prompt_asset_id": "route.review-audit.canon-patch.approval.v1",
            "command": f"Canon patch `{patch_id}` is deferred. Resume it from the decision panel when ready.",
            "source_paths": [item for item in [patch, patch_report, "workflow/approvals/index.jsonl"] if item],
            "expected_outputs": ["workflow/approvals/index.jsonl"],
            "hard_constraints": ["Do not silently apply or discard a deferred canon patch."],
            "style_constraints": [],
            "validation_gates": ["user or delegated steward explicitly resumes the deferred patch"],
            "next_allowed_states": ["canon-patch-apply", "canon-patch-revision"],
        },
        "canon-patch-apply": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.review-audit.canon-patch.apply.v1",
            "command": f"python -m literary_engineering_studio_engine canon-apply <project> --patch {patch} --approval-run-id {patch_id}",
            "source_paths": [item for item in [patch, patch_report, patch_completion, "workflow/approvals/index.jsonl"] if item],
            "expected_outputs": [
                patch,
                f"canon/applied/{patch_id}_apply.json",
                f"canon/applied/{patch_id}_apply.md",
                "canon/canon_change_log.md",
            ],
            "hard_constraints": [
                "Apply only the exact approved patch candidate.",
                "Do not use --allow-unapproved in formal operation.",
                "The apply manifest must preserve approval evidence and the pre-apply candidate digest.",
            ],
            "style_constraints": [],
            "validation_gates": ["patch status is applied", "apply manifest is valid", "approval digest matches applied candidate", "no approval bypass"],
            "next_allowed_states": ["canon-lint-file"],
        },
        "canon-lint-file": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.review-audit.canon-lint.v1",
            "command": "python -m literary_engineering_studio_engine canon-lint <project>",
            "source_paths": ["project.yaml", "canon", "characters", "plot", "scenes", "drafts/scenes"],
            "expected_outputs": ["reviews/canon_lint.md", "reviews/canon_lint.json"],
            "hard_constraints": [
                "Run canon-lint before any platform-agent project-level semantic review.",
                "Blocking canon-lint issues must be fixed or explicitly captured as candidate repair tasks before export.",
            ],
            "style_constraints": [],
            "validation_gates": ["canon-lint report exists", "canon-lint JSON schema/status is usable", "blocking_count is 0"],
            "next_allowed_states": ["canon-review-task-file"],
        },
        "canon-review-task-file": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.review-audit.canon-review.prepare.v1",
            "command": "python -m literary_engineering_studio_engine agent-canon-review <project>",
            "source_paths": ["reviews/canon_lint.md", "reviews/canon_lint.json", "canon", "characters", "plot", "scenes"],
            "expected_outputs": [f"{canon_review}.agent_tasks.md"],
            "hard_constraints": [
                "Run agent-canon-review only to create a platform-agent sidecar.",
                "The command prepares the task; the platform agent writes canon_review.v1 JSON/Markdown.",
            ],
            "style_constraints": [],
            "validation_gates": ["canon review sidecar exists"],
            "next_allowed_states": ["canon-review-agent-task"],
        },
        "canon-review-agent-task": {
            "task_type": "platform-agent-review",
            "prompt_asset_id": "route.review-audit.canon-review.execute.v1",
            "command": "",
            "source_paths": ["reviews/canon_lint.md", "reviews/canon_lint.json", f"{canon_review}.agent_tasks.md", "canon", "characters", "plot", "scenes"],
            "expected_outputs": [f"{canon_review}.json", f"{canon_review}.md", f"{canon_review}.agent_completion.json"],
            "hard_constraints": [
                "Read canon lint, canon files, characters, scenes, plot, and write canon_review.v1.",
                "pass_with_notes is not a clean release gate; unresolved facts and timeline risks must become repair tasks or be resolved.",
                "A non-pass conclusion is a valid completed review. Every actionable finding must name one exact target_path under canon/, characters/, plot/, scenes/, or drafts/candidates/.",
                "Do not call local providers. The host platform agent is the reviewer.",
            ],
            "style_constraints": [],
            "validation_gates": ["canon review sidecar completed", "canon_review.v1 validates", "canon review conclusion is recorded"],
            "next_allowed_states": ["canon-review-pass", "longform-audit-file"],
        },
        "canon-review-pass": {
            "task_type": "platform-agent-revision",
            "prompt_asset_id": "route.review-audit.canon-review.fix.v1",
            "command": "",
            "source_paths": [f"{canon_review}.json", f"{canon_review}.md", "reviews/canon_lint.json", *canon_repair_targets],
            "expected_outputs": [
                *canon_repair_targets,
                "reviews/canon_lint.md",
                "reviews/canon_lint.json",
                f"{canon_review}.json",
                f"{canon_review}.md",
                f"{canon_review}.agent_completion.json",
            ],
            "repair_targets": canon_repair_targets,
            "hard_constraints": [
                "Resolve every finding only in its declared target_path; do not touch files outside Allowed Outputs.",
                "Do not relabel unresolved findings as warnings to pass the gate.",
                "After repair run canon-lint in the sandbox, set canon review conclusion to recheck_required, and reset its completion marker for a fresh independent canon review.",
            ],
            "style_constraints": [],
            "validation_gates": ["at least one declared repair target changed", "canon-lint passes", "canon review reset to recheck_required"],
            "next_allowed_states": ["canon-review-agent-task"],
        },
        "longform-audit-file": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.review-audit.longform-audit.v1",
            "command": "python -m literary_engineering_studio_engine longform-audit <project>",
            "source_paths": ["project.yaml", "plot/chapters", "scenes", "drafts/scenes", "reviews/agent", "plot/word_budget"],
            "expected_outputs": ["reviews/longform/longform_audit.md", "reviews/longform/longform_audit.json", "plot/longform_graph.json"],
            "hard_constraints": [
                "Run longform-audit after canon review so the committee sees structural risks, word-budget gaps, and chapter readiness.",
                "Longform audit facts are evidence; the committee must still make semantic judgment.",
            ],
            "style_constraints": [],
            "validation_gates": ["longform audit JSON exists", "longform audit schema is valid", "longform graph exists"],
            "next_allowed_states": ["committee-task-file"],
        },
        "committee-task-file": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.review-audit.committee.prepare.v1",
            "command": "python -m literary_engineering_studio_engine agent-committee <project> --subject project-final-audit --source reviews/agent/canon_review.md",
            "source_paths": [f"{canon_review}.md", f"{canon_review}.json", "reviews/longform/longform_audit.md", "reviews/longform/longform_audit.json"],
            "expected_outputs": [f"{committee}.agent_tasks.md"],
            "hard_constraints": [
                "Run agent-committee only to create a platform-agent sidecar.",
                "Committee review must inspect canon review and longform audit; it cannot approve by vibe.",
            ],
            "style_constraints": [],
            "validation_gates": ["committee sidecar exists"],
            "next_allowed_states": ["committee-agent-task"],
        },
        "committee-agent-task": {
            "task_type": "platform-agent-review",
            "prompt_asset_id": "route.review-audit.committee.execute.v1",
            "command": "",
            "source_paths": [f"{committee}.agent_tasks.md", f"{canon_review}.json", f"{canon_review}.md", "reviews/longform/longform_audit.json", "reviews/longform/longform_audit.md"],
            "expected_outputs": [f"{committee}.json", f"{committee}.md", f"{committee}.agent_completion.json"],
            "hard_constraints": [
                "Act as a multi-perspective review committee: chief editor, character psychology, canon auditor, style auditor, readability, and anti-homogeneity.",
                "final_recommendation=approve is allowed only when no action_items or disagreements remain.",
                "approve_with_notes, revise, reject, action_items, or disagreements block export readiness.",
                "A non-approve recommendation is a valid completed committee review. Each action item or disagreement that requires repair must name an exact target_path.",
            ],
            "style_constraints": [],
            "validation_gates": ["committee sidecar completed", "committee_review.v1 validates", "final_recommendation is recorded"],
            "next_allowed_states": ["committee-pass"],
        },
        "committee-pass": {
            "task_type": "platform-agent-revision",
            "prompt_asset_id": "route.review-audit.committee.fix.v1",
            "command": "",
            "source_paths": [f"{committee}.json", f"{committee}.md", f"{canon_review}.json", "reviews/longform/longform_audit.json", *committee_repair_targets],
            "expected_outputs": [
                *committee_repair_targets,
                "reviews/canon_lint.md",
                "reviews/canon_lint.json",
                "reviews/longform/longform_audit.md",
                "reviews/longform/longform_audit.json",
                "plot/longform_graph.json",
                f"{canon_review}.json",
                f"{canon_review}.md",
                f"{canon_review}.agent_completion.json",
                f"{committee}.json",
                f"{committee}.md",
                f"{committee}.agent_completion.json",
            ],
            "repair_targets": committee_repair_targets,
            "hard_constraints": [
                "Resolve every committee action item and disagreement only in its declared target_path.",
                "Do not move to export-and-release on approve_with_notes.",
                "Rerun canon-lint and longform-audit after repair, then reset canon and committee completion evidence so both receive fresh independent review.",
            ],
            "style_constraints": [],
            "validation_gates": ["at least one declared repair target changed", "canon and committee reviews reset to recheck_required", "fresh deterministic audits exist"],
            "next_allowed_states": ["canon-review-agent-task"],
        },
    }
    default = {
        "task_type": "manual-route-repair",
        "prompt_asset_id": "route.review-audit.repair.v1",
        "command": next_action,
        "source_paths": ["reviews", "canon", "characters", "plot", "scenes"],
        "expected_outputs": [],
        "hard_constraints": [next_action or "Inspect workflow-state and route-audit, then repair the missing review-and-audit gate."],
        "style_constraints": [],
        "validation_gates": ["review-and-audit gate resolved"],
        "next_allowed_states": [],
    }
    return table.get(current_state, default)

def _review_audit_state_gate_validation(root: Path, task: dict[str, object]) -> tuple[list[str], list[str]]:
    current_state = str(task.get("current_state") or "")
    errors: list[str] = []
    notes: list[str] = []
    if current_state == "canon-patch-revision":
        errors.extend(_declared_repair_targets_changed(root, task, "canon-patch revision"))
        errors.extend(_canon_patch_candidate_gate_errors(root, task))
    if current_state == "canon-patch-approval":
        errors.extend(_canon_patch_candidate_gate_errors(root, task))
        errors.extend(_canon_patch_decision_gate_errors(root, task, require_approve=False))
    if current_state == "canon-patch-deferred":
        errors.append("canon patch is intentionally deferred; resume it through an explicit new decision")
    if current_state == "canon-patch-apply":
        errors.extend(_canon_patch_apply_gate_errors(root, task))
    if current_state == "canon-lint-file":
        errors.extend(_canon_lint_gate_errors(root))
    if current_state == "canon-review-task-file":
        errors.extend(_canon_lint_gate_errors(root))
        canon_task = root / "reviews" / "agent" / "canon_review.agent_tasks.md"
        if not canon_task.exists():
            errors.append(f"canon review sidecar missing: {_rel(canon_task, root)}")
    if current_state == "canon-review-agent-task":
        errors.extend(_canon_lint_gate_errors(root))
        errors.extend(_canon_review_gate_errors(root, require_pass=False))
    if current_state == "canon-review-pass":
        errors.extend(_project_review_revision_gate_errors(root, task, review_kind="canon"))
    if current_state == "longform-audit-file":
        errors.extend(_canon_review_gate_errors(root, require_pass=True))
        errors.extend(_longform_audit_file_gate_errors(root))
    if current_state == "committee-task-file":
        errors.extend(_canon_review_gate_errors(root, require_pass=True))
        errors.extend(_longform_audit_file_gate_errors(root))
        committee_task = root / "reviews" / "agent" / "committee_project-final-audit.agent_tasks.md"
        if not committee_task.exists():
            errors.append(f"committee sidecar missing: {_rel(committee_task, root)}")
    if current_state == "committee-agent-task":
        errors.extend(_canon_review_gate_errors(root, require_pass=True))
        errors.extend(_longform_audit_file_gate_errors(root))
        errors.extend(_committee_review_gate_errors(root, require_approve=False))
    if current_state == "committee-pass":
        errors.extend(_project_review_revision_gate_errors(root, task, review_kind="committee"))
    if current_state == "canon-patch-revision" and not errors:
        notes.append("canon patch candidate revised; fresh content-bound approval is required")
    if current_state == "canon-patch-approval" and not errors:
        notes.append("canon patch decision recorded against the current candidate")
    if current_state == "canon-patch-apply" and not errors:
        notes.append("approved canon patch applied to durable ledger")
    if current_state == "canon-review-agent-task" and not errors:
        notes.append("canon review verdict recorded; clean pass or formal revision routing may continue")
    if current_state == "canon-review-pass" and not errors:
        notes.append("canon repair completed; deterministic lint refreshed and review evidence reset")
    if current_state == "committee-agent-task" and not errors:
        notes.append("committee verdict recorded; approval or formal revision routing may continue")
    if current_state == "committee-pass" and not errors:
        notes.append("committee repair completed; project audits refreshed and review evidence reset")
    return errors, notes

def _canon_patch_path_for_task(root: Path, task: dict[str, object]) -> Path:
    patch = str(task.get("patch") or "").strip()
    if patch:
        return _resolve_project_path(root, patch)
    for value in [*task.get("expected_outputs", []), *task.get("source_paths", [])]:
        relative = str(value).replace("\\", "/")
        if relative.startswith("canon/patches/") and relative.endswith("_canon_patch.json"):
            return _resolve_project_path(root, relative)
    return root / "canon" / "patches" / "missing_canon_patch.json"


def _canon_patch_candidate_gate_errors(root: Path, task: dict[str, object]) -> list[str]:
    patch = _canon_patch_path_for_task(root, task)
    payload, error = _read_optional_json(patch)
    if error:
        return [error]
    errors: list[str] = []
    if payload.get("schema") != "literary-engineering-workbench/canon-patch-candidate/v0.1":
        errors.append("canon patch has wrong or missing schema")
    if payload.get("canon_change") is not True:
        errors.append("canon patch must declare canon_change=true before project-level approval")
    if payload.get("applied") is True or str(payload.get("status") or "").strip().lower() == "applied":
        errors.append("canon patch revision/approval task must not mark the candidate applied")
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    if not items:
        errors.append("canon patch must contain at least one durable fact item")
    required = ("type", "summary", "source_evidence", "target_files", "risk_level", "requires_user_approval")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"canon patch item {index + 1} must be an object")
            continue
        missing = [
            field
            for field in required
            if field not in item or item.get(field) is None or item.get(field) == "" or item.get(field) == []
        ]
        if missing:
            errors.append(f"canon patch item {index + 1} missing fields: {', '.join(missing)}")
        targets = item.get("target_files") if isinstance(item.get("target_files"), list) else []
        for target in targets:
            value = str(target).replace("\\", "/")
            if Path(value).is_absolute() or ".." in Path(value).parts or not value.startswith("canon/"):
                errors.append(f"canon patch item {index + 1} has unsafe target_file: {value}")
    completion = agent_task_completion_status(patch.with_suffix(".agent_tasks.md"), root=root)
    if completion.get("complete") is not True:
        errors.append(f"canon-evolve sidecar is incomplete: {completion.get('message')}")
    report = patch.with_suffix(".md")
    if not report.is_file():
        errors.append(f"canon patch report missing: {_rel(report, root)}")
    return errors


def _canon_patch_decision_gate_errors(
    root: Path,
    task: dict[str, object],
    *,
    require_approve: bool,
) -> list[str]:
    patch = _canon_patch_path_for_task(root, task)
    patch_id = str(task.get("patch_id") or patch.stem)
    approval = _approval_record_for_run(root, patch_id)
    decision = str(approval.get("decision") or "").strip().lower()
    allowed = {"approve"} if require_approve else {"approve", "revise", "reject", "defer"}
    if decision not in allowed:
        return [f"canon patch decision for {patch_id} must be one of {sorted(allowed)}; got {decision or 'missing'}"]
    if not _approval_matches_file(approval, patch):
        return [f"canon patch decision for {patch_id} is stale or not bound to the current candidate"]
    return []


def _canon_patch_apply_gate_errors(root: Path, task: dict[str, object]) -> list[str]:
    patch = _canon_patch_path_for_task(root, task)
    patch_id = str(task.get("patch_id") or patch.stem)
    apply_manifest = root / "canon" / "applied" / f"{patch_id}_apply.json"
    payload, error = _read_optional_json(apply_manifest)
    if error:
        return [error]
    errors: list[str] = []
    if payload.get("schema") != "literary-engineering-workbench/canon-patch-apply/v0.1":
        errors.append("canon apply manifest has wrong or missing schema")
    if payload.get("status") != "applied":
        errors.append(f"canon apply status must be applied; got {payload.get('status') or 'missing'}")
    if payload.get("allow_unapproved") is True:
        errors.append("canon apply used allow_unapproved")
    approval = payload.get("approval") if isinstance(payload.get("approval"), dict) else {}
    candidate_sha256 = str(payload.get("candidate_sha256") or "").strip().lower()
    if approval.get("decision") != "approve":
        errors.append("canon apply manifest must carry an approve record")
    if not candidate_sha256 or str(approval.get("subject_sha256") or "").strip().lower() != candidate_sha256:
        errors.append("canon apply approval digest does not match the pre-apply patch candidate")
    patch_payload, patch_error = _read_optional_json(patch)
    if patch_error:
        errors.append(patch_error)
    elif patch_payload.get("applied") is not True or patch_payload.get("apply_manifest") != _rel(apply_manifest, root):
        errors.append("canon patch does not point to its applied manifest")
    if not (root / "canon" / "canon_change_log.md").is_file():
        errors.append("canon change log is missing after apply")
    return errors


def _canon_lint_gate_errors(root: Path) -> list[str]:
    json_path = root / "reviews" / "canon_lint.json"
    report_path = root / "reviews" / "canon_lint.md"
    errors: list[str] = []
    for path in (report_path, json_path):
        if not path.exists():
            errors.append(f"canon-lint artifact missing: {_rel(path, root)}")
    payload, error = _read_optional_json(json_path)
    if error:
        errors.append(error)
        return errors
    if payload.get("schema") != "literary-engineering-workbench/canon-lint/v0.1":
        errors.append("canon_lint.json has wrong or missing schema")
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    blocking = _to_int(summary.get("blocking_count"))
    status = str(payload.get("status") or "").strip().lower()
    if blocking:
        errors.append(f"canon-lint blocking_count must be 0; got {blocking}")
    if status not in {"pass", "pass_with_warnings"}:
        errors.append(f"canon-lint status must be pass/pass_with_warnings; got {status or 'missing'}")
    return errors


def _canon_review_gate_errors(root: Path, *, require_pass: bool) -> list[str]:
    json_path = root / "reviews" / "agent" / "canon_review.json"
    report_path = json_path.with_suffix(".md")
    task_path = json_path.with_suffix(".agent_tasks.md")
    errors: list[str] = []
    state = agent_task_completion_status(task_path, root=root)
    if state.get("complete") is not True:
        errors.append(f"canon review sidecar is incomplete: {state.get('message')}")
    for path in (json_path, report_path):
        if not path.exists():
            errors.append(f"canon review artifact missing: {_rel(path, root)}")
    payload, error = _read_optional_json(json_path)
    if error:
        errors.append(error)
        return errors
    schema_errors, _warnings = validate_payload(payload, "canon_review.v1")
    errors.extend(f"canon_review.v1 schema error at {item.get('path')}: {item.get('message')}" for item in schema_errors)
    if require_pass:
        conclusion = str(payload.get("conclusion") or "").strip().lower()
        blocking = payload.get("blocking_issues") if isinstance(payload.get("blocking_issues"), list) else []
        warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
        unresolved = payload.get("unresolved_facts") if isinstance(payload.get("unresolved_facts"), list) else []
        timeline = payload.get("timeline_risks") if isinstance(payload.get("timeline_risks"), list) else []
        if conclusion != "pass":
            errors.append(f"canon review conclusion must be pass; got {conclusion or 'missing'}")
        if blocking:
            errors.append(f"canon review blocking_issues must be empty; got {len(blocking)}")
        if warnings:
            errors.append(f"canon review warnings must be resolved before export/release; got {len(warnings)}")
        if unresolved:
            errors.append(f"canon review unresolved_facts must be empty; got {len(unresolved)}")
        if timeline:
            errors.append(f"canon review timeline_risks must be empty; got {len(timeline)}")
    return errors


def _project_review_revision_gate_errors(
    root: Path,
    task: dict[str, object],
    *,
    review_kind: str,
) -> list[str]:
    errors: list[str] = []
    targets = [str(item) for item in task.get("repair_targets") or [] if str(item).strip()]
    before = task.get("repair_target_sha256_before_revision")
    hashes = before if isinstance(before, dict) else {}
    if not targets:
        errors.append(f"{review_kind} revision has no declared repair_targets; reviewer must provide exact target_path values")
    changed = False
    for relative in targets:
        path = _resolve_project_path(root, relative)
        if not path.is_file():
            errors.append(f"declared review repair target missing after revision: {relative}")
            continue
        previous = str(hashes.get(relative) or "")
        if not previous or _file_sha256(path) != previous:
            changed = True
    if targets and not changed:
        errors.append("project review repair did not change any declared repair target")

    def reset_errors(prefix: str) -> None:
        json_path = root / "reviews" / "agent" / f"{prefix}.json"
        task_path = json_path.with_suffix(".agent_tasks.md")
        completion = default_agent_completion_path(task_path)
        payload, payload_error = _read_optional_json(json_path)
        if payload_error:
            errors.append(payload_error)
        else:
            field = "conclusion" if prefix == "canon_review" else "final_recommendation"
            status = str(payload.get(field) or "").strip().lower()
            if status != "recheck_required":
                errors.append(f"{prefix} {field} must be recheck_required after revision; got {status or 'missing'}")
            applied = payload.get("applied_repair_actions")
            if not isinstance(applied, list) or not applied:
                errors.append(f"{prefix} must record non-empty applied_repair_actions")
        marker, marker_error = _read_optional_json(completion)
        if marker_error:
            errors.append(marker_error)
        else:
            marker_status = str(marker.get("status") or "").strip().lower()
            if marker_status != "recheck_required":
                errors.append(f"{prefix} completion status must be recheck_required after revision")
            if marker.get("expected_artifacts_checked") is not False:
                errors.append(f"{prefix} completion expected_artifacts_checked must be false after revision")

    reset_errors("canon_review")
    errors.extend(_canon_lint_gate_errors(root))
    if review_kind == "committee":
        reset_errors("committee_project-final-audit")
        errors.extend(_longform_audit_file_gate_errors(root))
    return errors


def _longform_audit_file_gate_errors(root: Path, *, require_clean: bool = False) -> list[str]:
    json_path = root / "reviews" / "longform" / "longform_audit.json"
    report_path = json_path.with_suffix(".md")
    graph_path = root / "plot" / "longform_graph.json"
    errors: list[str] = []
    for path in (json_path, report_path, graph_path):
        if not path.exists():
            errors.append(f"longform audit artifact missing: {_rel(path, root)}")
    payload, error = _read_optional_json(json_path)
    if error:
        errors.append(error)
        return errors
    errors.extend(longform_audit_gate_errors(root, payload, require_clean=require_clean))
    return errors


def _committee_review_gate_errors(root: Path, *, require_approve: bool) -> list[str]:
    json_path = root / "reviews" / "agent" / "committee_project-final-audit.json"
    report_path = json_path.with_suffix(".md")
    task_path = json_path.with_suffix(".agent_tasks.md")
    errors: list[str] = []
    state = agent_task_completion_status(task_path, root=root)
    if state.get("complete") is not True:
        errors.append(f"committee review sidecar is incomplete: {state.get('message')}")
    for path in (json_path, report_path):
        if not path.exists():
            errors.append(f"committee review artifact missing: {_rel(path, root)}")
    payload, error = _read_optional_json(json_path)
    if error:
        errors.append(error)
        return errors
    schema_errors, _warnings = validate_payload(payload, "committee_review.v1")
    errors.extend(f"committee_review.v1 schema error at {item.get('path')}: {item.get('message')}" for item in schema_errors)
    recommendation = str(payload.get("final_recommendation") or "").strip().lower()
    if recommendation == "approve":
        errors.extend(_longform_audit_file_gate_errors(root, require_clean=True))
    if require_approve:
        action_items = payload.get("action_items") if isinstance(payload.get("action_items"), list) else []
        disagreements = payload.get("disagreements") if isinstance(payload.get("disagreements"), list) else []
        if recommendation != "approve":
            errors.append(f"committee final_recommendation must be approve; got {recommendation or 'missing'}")
        if action_items:
            errors.append(f"committee action_items must be empty before export/release; got {len(action_items)}")
        if disagreements:
            errors.append(f"committee disagreements must be empty before export/release; got {len(disagreements)}")
    return errors

def _declared_repair_targets_changed(root: Path, task: dict[str, object], label: str) -> list[str]:
    targets = [str(item) for item in task.get("repair_targets") or [] if str(item).strip()]
    before = task.get("repair_target_sha256_before_revision")
    hashes = before if isinstance(before, dict) else {}
    if not targets or not hashes:
        return [f"{label} is missing declared repair target hash provenance"]
    for target in targets:
        path = _resolve_project_path(root, target)
        previous = str(hashes.get(target) or "").strip().lower()
        if path.is_file() and previous and _file_sha256(path) != previous:
            return []
    return [f"{label} did not change any declared planning candidate; review-only edits cannot complete revision"]


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_optional_json(path: Path) -> tuple[dict[str, object], str]:
    if not path.exists():
        return {}, f"JSON file missing: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, f"invalid JSON: {_rel(path, path.parent)} ({exc.msg})"
    except OSError as exc:
        return {}, str(exc)
    if not isinstance(payload, dict):
        return {}, f"JSON root is not an object: {path}"
    return payload, ""


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip() if path.exists() else ""


def _static_review_conclusion(path: Path) -> str:
    text = _read_text(path)
    match = re.search(r"(?m)^-\\s*(?:审查)?结论：\\s*(?:\\*\\*)?`?([a-z_]+)`?(?:\\*\\*)?\\s*$", text, re.IGNORECASE)
    return match.group(1).strip().lower() if match else ""


def _approval_record_for_run(root: Path, run_id: str) -> dict[str, object]:
    index = root / "workflow" / "approvals" / "index.jsonl"
    if not index.exists():
        return {}
    latest: dict[str, object] = {}
    for line in index.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("run_id") == run_id:
            latest = payload
    return latest


def _approval_matches_file(approval: dict[str, object], subject: Path) -> bool:
    if not approval or not subject.is_file():
        return False
    recorded = str(approval.get("subject_sha256") or "").strip().lower()
    if recorded:
        return recorded == _file_sha256(subject)
    recorded_at = _parse_datetime(str(approval.get("recorded_at") or ""))
    if recorded_at is None:
        return False
    subject_time = datetime.fromtimestamp(subject.stat().st_mtime, tz=timezone.utc)
    return subject_time <= recorded_at


def _parse_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result


build_task_payload = _build_review_audit_task_payload
validate_task = _review_audit_state_gate_validation
