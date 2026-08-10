"""Formal task blueprint and Gate logic for character and world assets.

This route controls candidate creation, independent review, digest-bound revision,
human approval, and deterministic promotion.  It deliberately keeps all
approval evidence inside the Engine rather than duplicating it in Studio.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from ...agent_schema import compact_schema_contract, validate_payload
from ...agent_tasks import agent_task_completion_status, default_agent_completion_path
from ...asset_context import compact_asset_context_relpaths
from ...asset_workshop import ASSET_CANDIDATE_DIRS, ASSET_SCHEMA_NAMES, PROMOTABLE_GROUPS
from ...literary.assets.promotion import (
    approval_gate_errors as _shared_approval_gate_errors,
    approval_matches_file as _shared_approval_matches_file,
    candidate_review_gate_errors as _shared_review_gate_errors,
    file_sha256 as _shared_file_sha256,
    promotion_output_paths as _shared_promotion_output_paths,
)
from ...task_paths import (
    TASK_SCHEMA,
    normalize_relative_path as _normalize_rel,
    now as _now,
    read_json as _read_json,
    relative_path as _rel,
    resolve_project_path as _resolve_project_path,
    task_id as _task_id,
)
def _build_asset_task_payload(root: Path, route: str, state: dict[str, object]) -> dict[str, object]:
    candidate_id = str(state.get("candidate_id") or state.get("target_id") or "asset-intake")
    asset_type = str(state.get("asset_type") or "")
    candidate = str(state.get("candidate") or "")
    current_state = str(state.get("current_step") or "")
    next_action = str(state.get("next_action") or "")
    blueprint = _asset_blueprint_for_state(root, candidate_id, asset_type, candidate, current_state, next_action)
    task_id = _task_id(route, candidate_id, current_state)
    expected_outputs = _unique([_normalize_rel(item) for item in blueprint["expected_outputs"]])
    source_paths = _unique([_normalize_rel(item) for item in blueprint["source_paths"]])
    now = _now()
    payload = {
        "schema": TASK_SCHEMA,
        "task_id": task_id,
        "status": "issued",
        "created_at": now,
        "route": route,
        "scene_id": candidate_id,
        "target_id": candidate_id,
        "candidate_id": candidate_id,
        "asset_type": asset_type,
        "candidate": candidate,
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
                "docs/implementation/phase38-agent-character-creation.md",
                "docs/implementation/phase41-candidate-review-promotion.md",
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
        "core_managed_outputs": [
            _normalize_rel(item)
            for item in blueprint.get("core_managed_outputs", [])
            if _normalize_rel(item) in expected_outputs
        ],
        "system_owned_fields": _asset_system_owned_fields(
            candidate_id=candidate_id,
            asset_type=asset_type,
            candidate=candidate,
            current_state=current_state,
            source_paths=source_paths,
            expected_outputs=expected_outputs,
            candidate_sha256=_candidate_digest(root, candidate),
        ),
        "submission_command": f"python -m literary_engineering_studio_engine task-submit <project> --task-id {task_id} --from <artifact>",
        "completion_command": f"python -m literary_engineering_studio_engine task-complete <project> --task-id {task_id}",
        "validation_gates": blueprint["validation_gates"],
        "forbidden_shortcuts": [
            "Do not write directly into canon/, characters/, plot/outline.md, scenes/, drafts/, exports/, or releases/ from a candidate task.",
            "Do not promote any candidate asset without a clean platform-agent asset review and an approve record.",
            "Do not use --allow-unapproved or any debug approval bypass in formal Skill-host work.",
            "Do not let extracted/source-derived claims become canon without evidence_refs, confidence, review, and approval.",
            "Do not treat this task as complete until task-submit and task-complete have succeeded.",
        ],
        "next_allowed_states": blueprint["next_allowed_states"],
    }
    if current_state in {"asset-review-pass", "asset-approval-revision"} and candidate:
        candidate_path = _resolve_project_path(root, candidate)
        if candidate_path.is_file():
            payload["candidate_sha256_before_revision"] = _file_sha256(candidate_path)
    return payload


def _asset_system_owned_fields(
    *,
    candidate_id: str,
    asset_type: str,
    candidate: str,
    current_state: str,
    source_paths: list[str],
    expected_outputs: list[str],
    candidate_sha256: str = "",
) -> dict[str, object]:
    """Describe machine-owned asset metadata separately from Agent-authored content.

    Candidate prose/setting and review reasoning remain creative work.  IDs,
    paths, schema discriminators, and completion lifecycle values are emitted by
    the task state machine so a runtime can normalize them before a core gate.
    """

    schema_name = ASSET_SCHEMA_NAMES.get(asset_type, "")
    schema_contract: dict[str, object] = {}
    if schema_name:
        try:
            schema_contract = compact_schema_contract(schema_name)
        except (OSError, ValueError):
            schema_contract = {}
    review_json = next(
        (
            item
            for item in expected_outputs
            if item.replace("\\", "/").startswith("reviews/assets/")
            and item.endswith("_review.json")
        ),
        f"reviews/assets/{candidate_id}_review.json",
    )
    completion_status = "recheck_required" if current_state in {"asset-review-pass", "asset-approval-revision"} else "complete"
    review_statuses = ["recheck_required"] if completion_status == "recheck_required" else ["pass", "failed", "revise_required"]
    return {
        "contract_version": "v1",
        "candidate": {
            "path": candidate,
            "candidate_id": candidate_id,
            "asset_type": asset_type,
            "schema": str(schema_contract.get("schema_value") or ""),
            "schema_contract": schema_contract,
            "source_paths": source_paths,
        },
        "review": {
            "path": review_json,
            "schema": "literary-engineering-workbench/candidate-asset-review/v0.1",
            "candidate": candidate,
            "candidate_id": candidate_id,
            "asset_type": asset_type,
            "candidate_sha256": candidate_sha256,
        },
        "completion": {
            "schema": "literary-engineering-workbench/agent-task-completion/v1",
            "status": completion_status,
            "expected_artifacts_checked": completion_status == "complete",
        },
        "enums": {
            "asset_review.status": review_statuses,
            "asset_revision.review_status": ["recheck_required"],
            "completion.status": ["complete", "recheck_required"],
        },
    }

def _asset_blueprint_for_state(root: Path, candidate_id: str, asset_type: str, candidate: str, current_state: str, next_action: str) -> dict[str, object]:
    candidate_rel = candidate or ""
    candidate_path = _resolve_project_path(root, candidate_rel) if candidate_rel else root / "characters" / "candidates" / f"{candidate_id}.json"
    candidate_report = _rel(candidate_path.with_suffix(".md"), root)
    creation_task = _rel(candidate_path.with_suffix(".agent_tasks.md"), root)
    creation_completion = _rel(default_agent_completion_path(candidate_path.with_suffix(".agent_tasks.md")), root)
    review = f"reviews/assets/{candidate_id}_review.md"
    review_json = f"reviews/assets/{candidate_id}_review.json"
    review_task = f"reviews/assets/{candidate_id}_review.agent_tasks.md"
    review_completion = f"reviews/assets/{candidate_id}_review.agent_completion.json"
    promotion = f"workflow/asset_promotions/{candidate_id}_promotion.json"
    promotion_report = f"workflow/asset_promotions/{candidate_id}_promotion.md"
    group = _asset_promotion_group(asset_type)
    promoted_outputs = _asset_promoted_output_rels(root, candidate_path, asset_type)
    type_hint = asset_type or "<character|background-story|relationship|world|location|organization|outline|chapter-plan|scene-list>"
    compact_context = compact_asset_context_relpaths(root)
    pending_revision_ids = _pending_revision_action_ids(root / review_json)
    revision_evidence_requirement = _revision_evidence_requirement(pending_revision_ids)
    creation_sources = [*compact_context, creation_task]
    review_sources = [candidate_rel, candidate_report, review_task, *compact_context]
    table: dict[str, dict[str, object]] = {
        "asset-intake": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.character-world-assets.intake.v1",
            "command": "python -m literary_engineering_studio_engine seed-project-assets <project>",
            "source_paths": compact_context,
            "expected_outputs": [
                "canon/candidates/world_rules/world-foundation.agent_tasks.md",
                "characters/candidates/protagonist-foundation.agent_tasks.md",
            ],
            "hard_constraints": [
                "Run seed-project-assets to create stable world-foundation and protagonist-foundation platform-agent sidecars.",
                "This deterministic step creates task contracts only; it does not invent or promote canon and character facts.",
                "The platform agent must not write directly to confirmed canon, character files, outline, scenes, drafts, exports, or releases.",
            ],
            "style_constraints": [],
            "validation_gates": ["world and protagonist asset creation sidecars exist"],
            "next_allowed_states": ["asset-creation-agent-task"],
        },
        "asset-creation-agent-task": {
            "task_type": "platform-agent-asset-creation",
            "prompt_asset_id": "route.character-world-assets.create.v1",
            "command": "",
            "source_paths": creation_sources,
            "expected_outputs": [candidate_rel, candidate_report, creation_completion],
            "hard_constraints": [
                f"Read the asset creation sidecar and write a {type_hint} candidate asset, not a confirmed project file.",
                "Candidate JSON must satisfy its schema and include candidate_id, risks, source_paths, and promotion_notes.",
                "Character and background-story assets must preserve background_story as hidden behavioral causality, not exposition.",
            ],
            "style_constraints": ["Mounted style may inform names/tone but cannot override canon, world rules, or user constraints."],
            "validation_gates": ["asset creation sidecar completed", "candidate JSON exists", "candidate report exists", "candidate schema validates"],
            "next_allowed_states": ["asset-review-task-file"],
        },
        "asset-review-task-file": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.character-world-assets.review.prepare.v1",
            "command": f"python -m literary_engineering_studio_engine review-candidate-asset <project> {candidate_rel}",
            "source_paths": [candidate_rel, candidate_report, *compact_context],
            "expected_outputs": [review_task],
            "hard_constraints": [
                "Run review-candidate-asset to create a formal platform-agent asset review sidecar.",
                "The command prepares the review task; the platform agent still performs the semantic review.",
            ],
            "style_constraints": [],
            "validation_gates": ["asset review sidecar exists"],
            "next_allowed_states": ["asset-review-agent-task"],
        },
        "asset-review-agent-task": {
            "task_type": "platform-agent-asset-review",
            "prompt_asset_id": "route.character-world-assets.review.execute.v1",
            "command": "",
            "source_paths": review_sources,
            "expected_outputs": [review, review_json, review_completion],
            "hard_constraints": [
                "Review candidate asset against schema, canon, character logic, originality, hidden background-story policy, and promotion risk.",
                "Write JSON with status pass|failed|revise_required plus blocking_issues, warnings, revision_actions, and promotion_risks.",
                "Revision actions may modify only the current candidate and its report. Put dependencies on other characters, canon assets, scenes, or routes into warnings/promotion_risks instead of blocking this candidate.",
                "Do not use review as approval. A clean review only permits asking the user whether to approve promotion.",
            ],
            "style_constraints": [],
            "validation_gates": [
                "asset review sidecar completed",
                "review JSON exists",
                "review Markdown exists",
                "review status is recorded as pass|failed|revise_required",
            ],
            "next_allowed_states": ["asset-review-pass", "asset-approval"],
        },
        "asset-review-pass": {
            "task_type": "platform-agent-revision",
            "prompt_asset_id": "route.character-world-assets.review-fix.v1",
            "command": "",
            "source_paths": [candidate_rel, review, review_json],
            "expected_outputs": [candidate_rel, candidate_report, review, review_json, review_completion],
            "hard_constraints": [
                "Resolve every blocking issue and revision action in the candidate asset before asking for approval.",
                "Do not create files outside Allowed Outputs. If an old review action asks for another asset or route, preserve it as a follow-up warning/promotion risk and revise only candidate-local findings.",
                "Do not bury revise_required findings as harmless warnings.",
                "Do not self-pass the review that requested this revision and do not replace critical findings with a clean verdict.",
                revision_evidence_requirement,
                "After revising the candidate and candidate report, preserve the previous findings as applied_revision_actions, set review status to recheck_required, and reset the review completion marker to recheck_required with expected_artifacts_checked=false.",
                "A fresh asset-review-agent-task must independently inspect the revised candidate before approval is possible.",
            ],
            "style_constraints": [],
            "validation_gates": [
                "candidate schema validates",
                "candidate content changed from pre-revision sha256",
                "review status is recheck_required",
                "applied_revision_actions recorded",
                "review completion evidence reset for independent recheck",
            ],
            "next_allowed_states": ["asset-review-agent-task"],
        },
        "asset-approval-revision": {
            "task_type": "platform-agent-revision",
            "prompt_asset_id": "route.character-world-assets.approval-fix.v1",
            "command": "",
            "source_paths": [candidate_rel, candidate_report, review, review_json, "workflow/approvals/index.jsonl"],
            "expected_outputs": [candidate_rel, candidate_report, review, review_json, review_completion],
            "core_managed_outputs": [review, review_json, review_completion],
            "hard_constraints": [
                "Revise only the current candidate and its report against the latest matching approval decision rationale.",
                "A revise or reject approval is not permission to approve, promote, or edit confirmed project assets.",
                _worker_managed_revision_evidence_requirement(pending_revision_ids),
                "After a real candidate change, Studio Worker records the approval rationale in applied_revision_actions, sets the prior review to recheck_required, and resets its completion marker for independent review.",
                "Do not self-pass the revised candidate; a fresh review and a new approval bound to the new candidate digest are mandatory.",
            ],
            "style_constraints": [],
            "validation_gates": [
                "candidate content changed from the approval-bound sha256",
                "candidate schema validates",
                "review status is recheck_required",
                "applied_revision_actions record the approval rationale",
                "review completion evidence reset for independent recheck",
            ],
            "next_allowed_states": ["asset-review-agent-task"],
        },
        "asset-approval": {
            "task_type": "human-approval-boundary",
            "prompt_asset_id": "route.character-world-assets.approval.v1",
            "command": f"Ask the user whether to approve candidate `{candidate_id}` for promotion; record approve decision with run_id `{candidate_id}` through the platform approval mechanism.",
            "source_paths": [candidate_rel, review, review_json, "workflow/approvals/index.jsonl"],
            "expected_outputs": ["workflow/approvals/index.jsonl"],
            "hard_constraints": [
                "The executing Worker must not self-approve candidate promotion. Approval may come from the user or a separately identified Creative Steward under an active DelegationPolicy.",
                "If the user asks for revision or rejection, record that decision and do not promote.",
                "Approval must reference the candidate_id/run_id that promote-candidate-asset will use.",
            ],
            "style_constraints": [],
            "validation_gates": ["approve record exists for candidate_id"],
            "next_allowed_states": ["asset-promotion"],
        },
        "asset-promotion": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.character-world-assets.promote.v1",
            "command": f"python -m literary_engineering_studio_engine promote-candidate-asset <project> {candidate_rel} --group {group or '<group>'} --approval-run-id {candidate_id}",
            "source_paths": _asset_promotion_sources(candidate_rel, candidate_id),
            "expected_outputs": [promotion, promotion_report, *promoted_outputs],
            "hard_constraints": [
                "Promote only after clean review and matching approve record.",
                "Do not use --allow-unapproved in formal Skill-host work.",
                "After promotion, run canon-lint or the relevant downstream route before relying on the new project facts.",
            ],
            "style_constraints": [],
            "validation_gates": ["promotion manifest exists", "allow_unapproved is false", "promotion outputs exist"],
            "next_allowed_states": ["ready"],
        },
    }
    default = {
        "task_type": "manual-route-repair",
        "prompt_asset_id": "route.character-world-assets.repair.v1",
        "command": next_action,
        "source_paths": [candidate_rel] if candidate_rel else ["project.yaml", "canon", "characters", "plot"],
        "expected_outputs": [],
        "hard_constraints": [next_action or "Inspect workflow-state and repair the missing character/world asset gate."],
        "style_constraints": [],
        "validation_gates": ["character/world asset gate resolved"],
        "next_allowed_states": [],
    }
    return table.get(current_state, default)

def _asset_state_gate_validation(root: Path, task: dict[str, object]) -> tuple[list[str], list[str]]:
    current_state = str(task.get("current_state") or "")
    candidate = _asset_candidate_path_for_task(root, task)
    candidate_id = str(task.get("candidate_id") or task.get("target_id") or candidate.stem)
    errors: list[str] = []
    notes: list[str] = []
    if current_state == "asset-intake":
        errors.extend(_asset_intake_gate_errors(root))
    if current_state == "asset-creation-agent-task":
        errors.extend(_asset_creation_gate_errors(root, candidate))
    if current_state == "asset-review-task-file":
        errors.extend(_asset_creation_gate_errors(root, candidate))
        review_task = root / "reviews" / "assets" / f"{candidate_id}_review.agent_tasks.md"
        if not review_task.exists():
            errors.append(f"asset review sidecar missing: {_rel(review_task, root)}")
    if current_state == "asset-review-agent-task":
        errors.extend(_asset_creation_gate_errors(root, candidate))
        errors.extend(_task_review_gate_errors(root, candidate, candidate_id, require_pass=False))
    if current_state in {"asset-review-pass", "asset-approval-revision"}:
        errors.extend(_asset_creation_gate_errors(root, candidate))
        errors.extend(_asset_revision_gate_errors(root, task, candidate, candidate_id))
    if current_state == "asset-approval":
        errors.extend(_asset_creation_gate_errors(root, candidate))
        errors.extend(_task_review_gate_errors(root, candidate, candidate_id, require_pass=True))
        errors.extend(_asset_approval_gate_errors(root, candidate_id, candidate))
    if current_state == "asset-promotion":
        errors.extend(_asset_creation_gate_errors(root, candidate))
        errors.extend(_task_review_gate_errors(root, candidate, candidate_id, require_pass=True))
        errors.extend(_asset_approval_gate_errors(root, candidate_id, candidate))
        errors.extend(_asset_promotion_gate_errors(root, candidate_id))
    if current_state in {"asset-creation-agent-task", "asset-review-task-file"} and not errors:
        notes.append("asset candidate creation gate passed")
    if current_state == "asset-review-agent-task" and not errors:
        notes.append("asset review verdict recorded; pass or formal revision routing may continue")
    if current_state in {"asset-review-pass", "asset-approval-revision"} and not errors:
        notes.append("asset candidate revised and prior review evidence reset for independent recheck")
    if current_state == "asset-promotion" and not errors:
        notes.append("asset promotion gate passed")
    return errors, notes

def _asset_intake_gate_errors(root: Path) -> list[str]:
    for folder in ASSET_CANDIDATE_DIRS.values():
        base = root / folder
        if not base.exists():
            continue
        if any(base.glob("*.agent_tasks.md")) or any(base.glob("*.json")):
            return []
    return ["no candidate asset or asset creation sidecar exists; run seed-project-assets first"]


def _asset_creation_gate_errors(root: Path, candidate: Path) -> list[str]:
    errors: list[str] = []
    task_path = candidate.with_suffix(".agent_tasks.md")
    report_path = candidate.with_suffix(".md")
    state = agent_task_completion_status(task_path, root=root)
    if state.get("complete") is not True:
        errors.append(f"asset creation sidecar is incomplete: {state.get('message')}")
    payload, error = _read_optional_json(candidate)
    if error:
        errors.append(error)
    else:
        asset_type = _asset_type_from_payload_or_path(root, candidate, payload)
        schema_name = ASSET_SCHEMA_NAMES.get(asset_type, "")
        if not schema_name:
            errors.append(f"unknown asset type for candidate: {asset_type or _rel(candidate, root)}")
        else:
            schema_errors, _warnings = validate_payload(payload, schema_name)
            errors.extend(f"asset candidate schema error at {item.get('path')}: {item.get('message')}" for item in schema_errors)
        candidate_id = str(payload.get("candidate_id") or "").strip()
        if not candidate_id:
            errors.append("asset candidate JSON must contain candidate_id")
        if not isinstance(payload.get("risks"), list):
            errors.append("asset candidate JSON must contain risks list")
        if not isinstance(payload.get("source_paths"), list):
            errors.append("asset candidate JSON must contain source_paths list")
        if not isinstance(payload.get("promotion_notes"), str) or not str(payload.get("promotion_notes") or "").strip():
            errors.append("asset candidate JSON must contain promotion_notes")
    if not report_path.exists():
        errors.append(f"asset candidate report missing: {_rel(report_path, root)}")
    return errors


def _asset_review_gate_errors(
    root: Path,
    candidate_id: str,
    *,
    require_pass: bool,
    candidate: Path | None = None,
    asset_type: str = "",
) -> list[str]:
    """Compatibility wrapper around the shared exact-content review gate."""

    candidate_path = candidate or _candidate_path_for_id(root, candidate_id)
    payload = _read_json(candidate_path)
    resolved_type = asset_type or _asset_type_from_payload_or_path(root, candidate_path, payload)
    return _shared_review_gate_errors(
        root,
        candidate_path,
        asset_type=resolved_type,
        require_pass=require_pass,
    )


def _task_review_gate_errors(
    root: Path,
    candidate: Path,
    candidate_id: str,
    *,
    require_pass: bool,
) -> list[str]:
    asset_type = _asset_type_from_payload_or_path(root, candidate, _read_json(candidate))
    return _asset_review_gate_errors(
        root,
        candidate_id,
        require_pass=require_pass,
        candidate=candidate,
        asset_type=asset_type,
    )


def _asset_revision_gate_errors(
    root: Path,
    task: dict[str, object],
    candidate: Path,
    candidate_id: str,
) -> list[str]:
    review = root / "reviews" / "assets" / f"{candidate_id}_review.md"
    review_json = review.with_suffix(".json")
    review_task = review_json.with_suffix(".agent_tasks.md")
    completion = default_agent_completion_path(review_task)
    errors: list[str] = []

    previous_hash = str(task.get("candidate_sha256_before_revision") or "").strip().lower()
    if not previous_hash:
        errors.append("asset revision task is missing candidate_sha256_before_revision provenance")
    elif not candidate.is_file():
        errors.append(f"asset candidate missing after revision: {_rel(candidate, root)}")
    elif _file_sha256(candidate) == previous_hash:
        errors.append("asset candidate content did not change; review labels cannot substitute for a real revision")

    payload, error = _read_optional_json(review_json)
    if error:
        errors.append(error)
    else:
        status = str(payload.get("status") or "").strip().lower()
        if status != "recheck_required":
            errors.append(f"revised asset review status must be recheck_required; got {status or 'missing'}")
        candidate_ref = str(payload.get("candidate") or "").strip()
        if candidate_ref and Path(candidate_ref).stem != candidate_id:
            errors.append(f"asset revision candidate mismatch: {candidate_ref} does not match {candidate_id}")
        applied = payload.get("applied_revision_actions")
        if not isinstance(applied, list) or not applied:
            errors.append("revised asset review must record non-empty applied_revision_actions")
        round_value = payload.get("revision_round")
        if not isinstance(round_value, int) or isinstance(round_value, bool) or round_value < 1:
            errors.append("revised asset review must record revision_round as an integer >= 1")

    completion_payload, completion_error = _read_optional_json(completion)
    if completion_error:
        errors.append(completion_error)
    else:
        status = str(completion_payload.get("status") or "").strip().lower()
        if status != "recheck_required":
            errors.append(f"asset review completion status must be recheck_required after revision; got {status or 'missing'}")
        if completion_payload.get("expected_artifacts_checked") is not False:
            errors.append("asset review completion expected_artifacts_checked must be false until fresh review")
        expected_source = _rel(review_task, root)
        source_task = str(completion_payload.get("source_task") or "").replace("\\", "/")
        if source_task != expected_source:
            errors.append(f"asset review completion source_task must be {expected_source}")

    for path, label in ((candidate.with_suffix(".md"), "candidate report"), (review, "asset review report")):
        if not path.exists():
            errors.append(f"{label} missing: {_rel(path, root)}")
    return errors


def _pending_revision_action_ids(review_path: Path) -> list[str]:
    """Read just the stable identifiers that a revision task must account for."""

    payload, error = _read_optional_json(review_path)
    if error:
        return []
    actions = payload.get("revision_actions") if isinstance(payload.get("revision_actions"), list) else []
    identifiers: list[str] = []
    for index, action in enumerate(actions, start=1):
        if isinstance(action, dict):
            identifier = str(action.get("id") or "").strip()
        else:
            identifier = ""
        identifiers.append(identifier or f"revision-action-{index}")
    return identifiers


def _revision_evidence_requirement(action_ids: list[str]) -> str:
    listed = ", ".join(f"`{item}`" for item in action_ids) if action_ids else "每一项原始 revision_action"
    return (
        "先完成候选资产修改，再重写 review JSON 的复审字段："
        "`status` 必须为 `recheck_required`，`revision_round` 必须是 >= 1 的整数，"
        "`applied_revision_actions` 必须是非空数组；数组内每项至少写 `id`、`action` 和 `evidence`。"
        f"本轮必须逐项覆盖：{listed}。不得只保留旧 `revision_actions` 来代替落实证据。"
    )


def _worker_managed_revision_evidence_requirement(action_ids: list[str]) -> str:
    listed = ", ".join(f"`{item}`" for item in action_ids) if action_ids else "当前审批理由"
    return (
        "先完成候选资产和候选报告的实质性修改。不要改写 review JSON、review Markdown 或 completion receipt；"
        "Studio Worker 会在检测到候选摘要变化后，将审批理由写入 applied_revision_actions、"
        "设置 review status 为 recheck_required，并重置独立复审回执。"
        f"本轮候选修改必须可追溯地回应：{listed}。"
    )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _candidate_digest(root: Path, candidate: str) -> str:
    path = _resolve_project_path(root, candidate) if candidate else None
    return _shared_file_sha256(path) if path is not None and path.is_file() else ""


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


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result


def _parse_datetime(value: str) -> datetime | None:
    normalized = value.strip().replace("Z", "+00:00")
    if not normalized:
        return None
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _asset_approval_gate_errors(root: Path, candidate_id: str, candidate: Path) -> list[str]:
    return _shared_approval_gate_errors(root, candidate_id, candidate)


def _approval_matches_file(approval: dict[str, object], subject: Path) -> bool:
    return _shared_approval_matches_file(approval, subject)


def _asset_promotion_gate_errors(root: Path, candidate_id: str) -> list[str]:
    manifest = root / "workflow" / "asset_promotions" / f"{candidate_id}_promotion.json"
    report = manifest.with_suffix(".md")
    payload, error = _read_optional_json(manifest)
    errors: list[str] = []
    if error:
        errors.append(error)
        return errors
    if payload.get("status") != "promoted":
        errors.append(f"asset promotion status must be promoted; got {payload.get('status') or 'missing'}")
    if payload.get("allow_unapproved"):
        errors.append("asset promotion used allow_unapproved; formal Skill-host route must not use approval bypass")
    if str(payload.get("candidate_id") or "") != candidate_id:
        errors.append(f"asset promotion candidate_id mismatch: {payload.get('candidate_id') or 'missing'}")
    outputs = payload.get("outputs") if isinstance(payload.get("outputs"), list) else []
    if not outputs:
        errors.append("asset promotion manifest must list outputs")
    for item in outputs:
        path = _resolve_project_path(root, str(item))
        if not path.exists():
            errors.append(f"asset promotion output missing: {_rel(path, root)}")
    if not report.exists():
        errors.append(f"asset promotion report missing: {_rel(report, root)}")
    return errors


def _asset_candidate_path_for_task(root: Path, task: dict[str, object]) -> Path:
    candidate = str(task.get("candidate") or "").strip()
    if candidate:
        return _resolve_project_path(root, candidate)
    candidates = [
        *[str(item) for item in task.get("submitted_artifacts") or []],
        *[str(item) for item in task.get("expected_outputs") or []],
        *[str(item) for item in task.get("source_paths") or []],
    ]
    for item in candidates:
        normalized = item.replace("\\", "/")
        if not normalized.endswith(".json"):
            continue
        if ".agent_" in normalized or "/reviews/" in f"/{normalized}" or "/workflow/" in f"/{normalized}":
            continue
        if _is_asset_candidate_rel(normalized):
            return _resolve_project_path(root, item)
    candidate_id = str(task.get("candidate_id") or task.get("target_id") or "asset-intake")
    return root / "characters" / "candidates" / f"{candidate_id}.json"


def _candidate_path_for_id(root: Path, candidate_id: str) -> Path:
    matches: list[Path] = []
    seen: set[Path] = set()
    for folder in ASSET_CANDIDATE_DIRS.values():
        candidate = root / folder / f"{candidate_id}.json"
        if candidate.is_file() and candidate not in seen:
            matches.append(candidate)
            seen.add(candidate)
    if len(matches) > 1:
        paths = ", ".join(_rel(path, root) for path in matches)
        raise ValueError(f"duplicate asset candidate id {candidate_id}: {paths}")
    if matches:
        return matches[0]
    return root / "characters" / "candidates" / f"{candidate_id}.json"


def _is_asset_candidate_rel(value: str) -> bool:
    normalized = value.replace("\\", "/").lstrip("/")
    return any(normalized.startswith(folder.as_posix() + "/") for folder in ASSET_CANDIDATE_DIRS.values())


def _asset_type_from_payload_or_path(root: Path, candidate: Path, payload: dict[str, object]) -> str:
    asset_type = str(payload.get("asset_type") or "").strip().lower().replace("_", "-")
    if asset_type:
        return asset_type
    rel = _rel(candidate, root)
    for item_type, folder in ASSET_CANDIDATE_DIRS.items():
        if rel.startswith(folder.as_posix() + "/"):
            return item_type
    return ""


def _asset_promotion_sources(candidate: str, candidate_id: str) -> list[str]:
    review_base = f"reviews/assets/{candidate_id}_review"
    return [
        candidate,
        f"{review_base}.md",
        f"{review_base}.json",
        f"{review_base}.agent_tasks.md",
        f"{review_base}.agent_completion.json",
        "workflow/approvals/index.jsonl",
    ]


def _asset_promotion_group(asset_type: str) -> str:
    normalized = asset_type.strip().lower().replace("_", "-")
    for group, members in PROMOTABLE_GROUPS.items():
        if normalized in members:
            return group
    return ""


def _asset_promoted_output_rels(root: Path, candidate: Path, asset_type: str) -> list[str]:
    """Predict the formal files written by promote-candidate-asset.

    The Worker treats every undeclared write as a contract violation, so the
    deterministic promotion task must declare both its manifest and the exact
    project asset paths produced by ``asset_workshop._write_promoted_asset``.
    """

    if not candidate.is_file():
        return []
    payload = _read_json(candidate)
    return [_rel(path, root) for path in _shared_promotion_output_paths(root, asset_type, payload)]


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
build_task_payload = _build_asset_task_payload
validate_task = _asset_state_gate_validation
