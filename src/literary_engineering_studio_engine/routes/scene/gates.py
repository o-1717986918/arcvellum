"""Evidence gates for the formal scene-development route."""
from __future__ import annotations

import json
from pathlib import Path
import re

from ...agent_tasks import agent_task_completion_status, default_agent_completion_path
from ...anti_ai_style import style_lint_gate, style_lint_gate_message
from ...canon_evolver import canon_writeback_status
from ...candidate_promotion import candidate_generation_gate, candidate_review_gate
from ...literary.scene.promotion.historical import validate_historical_promotion
from ...context_broker import context_trace_status
from ...creative_quality import load_creative_quality_profile
from ...draft_text import final_body_from_draft_path
from ...flow_gates import FlowGateError, branch_selection_status, ensure_composition_ready_for_generation
from ...narrative_rhythm import narrative_rhythm_contract
from ...reader_experience import ensure_reader_experience_ready, reader_experience_adherence_for_body
from ...scene_character_assets import scene_character_asset_requirements
from ...semantic_task_contracts import semantic_artifact_errors
from ...continuity_ledger import continuity_ledger_status, continuity_ledger_task_status
from ...scene_handoff import scene_handoff_source_status
from ...task_paths import relative_path as _rel, resolve_project_path as _resolve_project_path
from ...tasking.state_contracts import SCENE_REVISION_STATES
from ...word_budget import ensure_scene_word_budget_ready, word_budget_adherence_for_body
from ...scene_route_support import (
    _file_sha256, _parse_datetime, _read_optional_json, _read_text,
    _static_review_conclusion,
)
from .branch_contract import branch_manifest_gate_errors as _branch_manifest_gate_errors
from .branch_contract import branch_selection_gate as _branch_selection_gate
from .length_repair import target_length_revision_gate_errors
from ..review.canon_gates import (
    canon_patch_apply_gate_errors,
    canon_patch_candidate_gate_errors,
    canon_patch_decision_gate_errors,
)
from ..review.evidence import declared_repair_targets_changed
def _state_gate_validation(root: Path, task: dict[str, object]) -> tuple[list[str], list[str]]:
    """Run current-state-specific gates after expected outputs exist."""

    current_state = str(task.get("current_state") or "")
    scene_id = str(task.get("scene_id") or "")
    errors: list[str] = []
    notes: list[str] = []
    if not current_state:
        return errors, notes

    if current_state in {"context-packet", "context-trace"}:
        errors.extend(_context_trace_gate_errors(root, scene_id))
    if current_state == "roleplay-simulation":
        errors.extend(_roleplay_gate_errors(root, scene_id))
    if current_state == "roleplay-agent-task":
        errors.extend(_roleplay_gate_errors(root, scene_id))
        errors.extend(semantic_artifact_errors(root, current_state, scene_id))
    if current_state in {"branch-manifest", "branch-agent-task"}:
        errors.extend(_branch_manifest_gate_errors(root, scene_id, require_agent_proposals=current_state == "branch-agent-task"))
    if current_state == "branch-selection":
        branch_errors, branch_notes = _branch_selection_gate(root, scene_id)
        errors.extend(branch_errors)
        notes.extend(branch_notes)
    if current_state == "composition-json":
        errors.extend(_composition_prepare_gate_errors(root, scene_id))
    if current_state == "composition-agent-task":
        errors.extend(_composition_gate_errors(root, scene_id))
    if current_state == "composition-agent-task":
        errors.extend(semantic_artifact_errors(root, current_state, scene_id))
    if current_state == "scene-word-budget-contract":
        errors.extend(_word_budget_gate_errors(root, task))
    if current_state == "reader-experience-contract":
        errors.extend(_reader_experience_gate_errors(root, task))
    if current_state == "scene-rhythm-contract":
        errors.extend(_narrative_rhythm_gate_errors(root, scene_id))
    if current_state in {"candidate-generation-provenance", "generation-agent-task"}:
        candidate = _candidate_path_for_task(root, task)
        errors.extend(_candidate_generation_gate_errors(root, task, candidate))
        errors.extend(_candidate_body_gate_errors(root, task, candidate))
    if current_state in SCENE_REVISION_STATES:
        candidate = _candidate_path_for_task(root, task)
        errors.extend(_candidate_generation_gate_errors(root, task, candidate))
        errors.extend(_candidate_body_gate_errors(root, task, candidate))
        errors.extend(_scene_revision_gate_errors(root, task, candidate))
    if current_state in {"candidate-review", "agent-review-task"}:
        candidate = _candidate_path_for_task(root, task)
        errors.extend(_candidate_generation_gate_errors(root, task, candidate))
        errors.extend(_candidate_review_gate_errors(root, task, candidate, require_pass=current_state == "agent-review-task"))
    if current_state in {"promotion-manifest", "promoted-draft"}:
        errors.extend(_promotion_gate_errors(root, task))
    if current_state == "static-review":
        errors.extend(_static_review_gate_errors(root, scene_id, require_pass=False))
    if current_state == "target-length-revision":
        errors.extend(target_length_revision_gate_errors(root, scene_id, candidate))
    if current_state in {"state-patch-json", "state-agent-task"}:
        errors.extend(_state_patch_gate_errors(root, scene_id))
    if current_state == "state-agent-task":
        errors.extend(semantic_artifact_errors(root, current_state, scene_id))
    if current_state in {"state-patch-approval", "state-apply"}:
        from ...character_state_apply import state_patch_writeback_status

        state_status = state_patch_writeback_status(root, scene_id)
        value = str(state_status.get("status") or "")
        if current_state == "state-patch-approval" and value not in {"pending_apply", "pass", "not_required"}:
            errors.append(str(state_status.get("message") or "state patch approval is incomplete"))
        if current_state == "state-apply" and value != "pass":
            errors.append(str(state_status.get("message") or "state apply is incomplete"))
    if current_state == "canon-patch-json":
        errors.extend(_canon_writeback_gate_errors(root, scene_id, require_review=False))
    if current_state == "canon-agent-task":
        errors.extend(_canon_writeback_gate_errors(root, scene_id, require_review=True))
    if current_state == "canon-agent-task":
        errors.extend(semantic_artifact_errors(root, current_state, scene_id))
    if current_state == "canon-patch-revision":
        errors.extend(declared_repair_targets_changed(root, task, "canon-patch revision"))
        errors.extend(canon_patch_candidate_gate_errors(root, task))
    if current_state in {"canon-patch-approval", "canon-patch-deferred"}:
        errors.extend(canon_patch_decision_gate_errors(root, task, require_approve=False))
    if current_state == "canon-patch-apply":
        errors.extend(canon_patch_apply_gate_errors(root, task))
    if current_state in {"continuity-ledger-agent-task", "continuity-ledger-review", "continuity-ledger-apply"}:
        passed, message, _delta = continuity_ledger_status(root, scene_id, require_review=current_state != "continuity-ledger-agent-task")
        if not passed:
            errors.append(message)
    if current_state in {"continuity-ledger-agent-task", "continuity-ledger-review"}:
        passed, message = continuity_ledger_task_status(root, scene_id, review=current_state == "continuity-ledger-review")
        if not passed:
            errors.append(message)
    if current_state == "continuity-ledger-apply" and not (root / "plot" / "ledger_deltas" / f"{scene_id}_apply.json").is_file():
        errors.append("continuity ledger apply receipt is missing")
    if current_state == "scene-handoff":
        passed, message, _payload = scene_handoff_source_status(root, scene_id)
        if not passed:
            errors.append(message)
    return errors, notes


def _context_trace_gate_errors(root: Path, scene_id: str) -> list[str]:
    if not scene_id:
        return ["context task missing scene_id; cannot validate context trace"]
    context = root / "memory" / "context_packets" / f"{scene_id}.md"
    if not context.exists():
        return [f"context packet is missing: {_rel(context, root)}"]
    status = context_trace_status(root, scene_id, context)
    if not status.passed:
        return [status.message]
    return []


def _roleplay_gate_errors(root: Path, scene_id: str) -> list[str]:
    path = root / "branches" / scene_id / "roleplay_simulation.md"
    text = _read_text(path)
    if not text:
        return [f"roleplay simulation is empty or unreadable: {_rel(path, root)}"]
    if "正式 CLI 来源" not in text or "simulate-scene" not in text:
        return [
            "roleplay simulation lacks CLI provenance text from simulate-scene; "
            "manual RP files are exploratory/debug-only for the formal route"
        ]
    return []


def _composition_gate_errors(root: Path, scene_id: str) -> list[str]:
    composition = root / "drafts" / "compositions" / f"{scene_id}_composition.json"
    try:
        payload = ensure_composition_ready_for_generation(root, composition)
    except (FlowGateError, json.JSONDecodeError, OSError, ValueError) as exc:
        return [str(exc)]
    flow_gate = payload.get("flow_gate") if isinstance(payload.get("flow_gate"), dict) else {}
    if flow_gate.get("ready_for_generation") is not True:
        return ["composition ready_for_generation must be true before prose generation"]
    provenance = payload.get("formal_cli_provenance") if isinstance(payload.get("formal_cli_provenance"), dict) else {}
    if provenance.get("agent_tasks_requested") is not True:
        return ["composition was not created with --agent-tasks; composition sidecar is required"]
    return []


def _composition_prepare_gate_errors(root: Path, scene_id: str) -> list[str]:
    """Validate the CLI composition output before its Agent review exists.

    ``composition-json`` is the deterministic preparation state.  Its command
    deliberately creates an *incomplete* semantic-review template for the
    following ``composition-agent-task`` state.  Requiring that review here
    makes the state machine reject its own freshly generated scaffold and
    repeatedly retry the same task.  The full semantic gate stays in
    :func:`_composition_gate_errors`, where it belongs.
    """

    composition = root / "drafts" / "compositions" / f"{scene_id}_composition.json"
    if not composition.is_file():
        return [f"composition JSON is missing: {_rel(composition, root)}"]
    try:
        payload = json.loads(composition.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"composition JSON is unreadable: {exc}"]
    if not isinstance(payload, dict):
        return ["composition JSON must contain an object"]
    provenance = payload.get("formal_cli_provenance")
    provenance = provenance if isinstance(provenance, dict) else {}
    if str(provenance.get("created_by") or "") != "compose-scene":
        return ["composition JSON lacks formal_cli_provenance.created_by=compose-scene"]
    if provenance.get("agent_tasks_requested") is not True:
        return ["composition JSON was not created with --agent-tasks"]
    if str(payload.get("selection_source") or "") != "selection":
        return ["composition JSON must consume a formal branch selection"]
    if not str(payload.get("selected_branch") or "").strip():
        return ["composition JSON is missing selected_branch"]
    return []


def _word_budget_gate_errors(root: Path, task: dict[str, object]) -> list[str]:
    scene_path = _scene_path_for_task(root, task)
    try:
        contract = ensure_scene_word_budget_ready(root, scene_path)
    except (FileNotFoundError, ValueError) as exc:
        return [str(exc)]
    if contract.get("status") == "not_required":
        return []
    errors: list[str] = []
    scene_inventory_task = root / "plot" / "word_budget" / "scene_inventory_expansion.agent_tasks.md"
    if scene_inventory_task.exists():
        completion = agent_task_completion_status(scene_inventory_task, root=root)
        if completion.get("complete") is not True:
            errors.append(f"scene-inventory word-budget sidecar is incomplete: {completion.get('message')}")
    scene_inventory_review = root / "reviews" / "word_budget" / "scene_inventory_review.md"
    if scene_inventory_task.exists() and not scene_inventory_review.exists():
        errors.append("formal longform scene generation requires reviews/word_budget/scene_inventory_review.md")
    return errors


def _reader_experience_gate_errors(root: Path, task: dict[str, object]) -> list[str]:
    scene_path = _scene_path_for_task(root, task)
    try:
        contract = ensure_reader_experience_ready(root, scene_path)
    except (FileNotFoundError, ValueError) as exc:
        return [str(exc)]
    if contract.get("status") == "not_required":
        return []
    return []


def _narrative_rhythm_gate_errors(root: Path, scene_id: str) -> list[str]:
    scene_path = root / "scenes" / f"{scene_id}.yaml"
    if not scene_path.is_file():
        return [f"scene file is missing for narrative rhythm contract: {_rel(scene_path, root)}"]
    contract = narrative_rhythm_contract(root, scene_path)
    if str(contract.get("status") or "") == "pass":
        return []
    return [f"narrative rhythm/bridge contract is not ready: {contract.get('message') or 'missing required fields'}"]


def _candidate_generation_gate_errors(root: Path, task: dict[str, object], candidate: Path) -> list[str]:
    scene_id = str(task.get("scene_id") or candidate.stem.split("-")[0])
    gate = candidate_generation_gate(root, scene_id, candidate)
    if gate.get("status") == "pass":
        return []
    details: list[str] = [str(gate.get("message") or "candidate generation gate failed")]
    missing = gate.get("missing")
    invalid = gate.get("invalid")
    if isinstance(missing, list) and missing:
        details.append("missing=" + ", ".join(str(item) for item in missing))
    if isinstance(invalid, list) and invalid:
        details.append("invalid=" + ", ".join(str(item) for item in invalid))
    return ["; ".join(details)]


def _candidate_body_gate_errors(root: Path, task: dict[str, object], candidate: Path) -> list[str]:
    if not candidate.exists():
        return [f"candidate Markdown is missing: {_rel(candidate, root)}"]
    scene_path = _scene_path_for_task(root, task)
    body = final_body_from_draft_path(candidate)
    errors: list[str] = []
    if not body:
        errors.append(f"candidate has no cleaned deliverable body: {_rel(candidate, root)}")
        return errors
    scene_id = str(task.get("scene_id") or scene_path.stem)
    lint_gate = style_lint_gate(body, profile=load_creative_quality_profile(root), scope=scene_id)
    if lint_gate.get("status") == "blocking":
        errors.append(f"candidate failed Style Lint Gate: {style_lint_gate_message(lint_gate)}")
    budget = word_budget_adherence_for_body(root, scene_path, body)
    if budget.get("status") not in {"pass", "not_required"}:
        errors.append(f"candidate failed scene word-budget gate: {budget.get('message')}")
    reader = reader_experience_adherence_for_body(root, scene_path, body)
    if reader.get("status") not in {"pass", "not_required"}:
        errors.append(f"candidate failed reader-experience gate: {reader.get('message')}")
    return errors


def _candidate_review_gate_errors(
    root: Path,
    task: dict[str, object],
    candidate: Path,
    *,
    require_pass: bool = True,
) -> list[str]:
    scene_id = str(task.get("scene_id") or candidate.stem.split("-")[0])
    gate = candidate_review_gate(root, scene_id, candidate)
    if gate.get("status") == "pass":
        return []
    if not require_pass:
        infrastructure_failures = {
            "schema_failed",
            "semantic_contract_failed",
            "task_incomplete",
            "stale_or_wrong_source",
            "creative_quality_review_stale",
            "word_budget_review_failed",
            "reader_experience_review_failed",
            "narrative_rhythm_review_failed",
            "canon_writeback_review_failed",
            "revision_integrity_review_failed",
            "review_session_independence_failed",
        }
        if str(gate.get("status") or "") not in infrastructure_failures:
            return []
    message = str(gate.get("message") or "candidate review gate failed")
    lint_gate = gate.get("style_lint")
    if isinstance(lint_gate, dict) and lint_gate.get("status") == "blocking":
        message += f"; Style Lint Gate: {style_lint_gate_message(lint_gate)}"
    return [message]


def _scene_revision_gate_errors(root: Path, task: dict[str, object], candidate: Path) -> list[str]:
    errors: list[str] = []
    source_rel = str(task.get("revision_source") or "").strip()
    previous_hash = str(task.get("candidate_sha256_before_revision") or "").strip().lower()
    if not source_rel or not previous_hash:
        errors.append("scene revision task is missing exact source candidate hash provenance")
    source = _resolve_project_path(root, source_rel) if source_rel else root / "__missing_revision_source__"
    if source_rel and source.is_file() and previous_hash and _file_sha256(source) != previous_hash:
        errors.append("scene revision source changed after task issuance; acquire a fresh revision task")
    elif not candidate.is_file():
        errors.append(f"scene revision candidate is missing: {_rel(candidate, root)}")
    elif _file_sha256(candidate) == previous_hash:
        errors.append("scene revision candidate is unchanged from the exact reviewed source")

    scene_id = str(task.get("scene_id") or candidate.stem.split("_revision", 1)[0])
    base = candidate.with_suffix("")
    manifest_path = base.with_suffix(".json")
    report = base.with_name(base.name + "_report.md")
    prompt = base.with_suffix(".prompt.json")
    sidecar = base.with_suffix(".agent_tasks.md")
    completion = default_agent_completion_path(sidecar)
    for path, label in ((report, "revision report"), (prompt, "revision prompt manifest"), (sidecar, "revision sidecar")):
        if not path.is_file():
            errors.append(f"{label} missing: {_rel(path, root)}")
    payload, error = _read_optional_json(manifest_path)
    if error:
        errors.append(error)
    elif source.is_file() and candidate.is_file():
        errors.extend(_revision_manifest_gate_errors(root, scene_id, source_rel, previous_hash, source, candidate, payload))
    completion_state = agent_task_completion_status(sidecar, root=root)
    if completion_state.get("complete") is not True:
        errors.append(f"scene revision sidecar is incomplete: {completion_state.get('message')}")
    return errors


def _revision_manifest_gate_errors(
    root: Path,
    scene_id: str,
    source_rel: str,
    source_sha256: str,
    source: Path,
    candidate: Path,
    payload: dict[str, object],
) -> list[str]:
    from ...literary.scene.promotion.revision_contract import (
        revision_manifest_errors,
        revision_source_requires_anti_evasion_rows,
    )

    profile = load_creative_quality_profile(root)
    return revision_manifest_errors(
        payload,
        scene_id=scene_id,
        source_rel=source_rel,
        source_sha256=source_sha256,
        source_body=final_body_from_draft_path(source),
        candidate_rel=_rel(candidate, root),
        candidate_sha256=_file_sha256(candidate),
        candidate_body=final_body_from_draft_path(candidate),
        anti_evasion_rows_required=revision_source_requires_anti_evasion_rows(
            source, quality_profile=profile, scene_id=scene_id
        ),
    )


def _promotion_gate_errors(root: Path, task: dict[str, object]) -> list[str]:
    scene_id = str(task.get("scene_id") or "")
    manifest_path = root / "drafts" / "promotions" / f"{scene_id}_promotion.json"
    payload, error = _read_optional_json(manifest_path)
    if error:
        return [error]
    if not payload:
        return [f"promotion manifest is missing or empty: {_rel(manifest_path, root)}"]
    errors: list[str] = []
    if payload.get("allow_unreviewed") is True:
        errors.append("promotion manifest uses allow_unreviewed=true; debug review bypass is forbidden for formal Skill hosts")
    if payload.get("allow_review_notes") is True:
        errors.append("promotion manifest uses allow_review_notes=true; pass_with_notes must be revised and re-reviewed")
    candidate_value = str(payload.get("candidate") or "")
    if not candidate_value:
        errors.append("promotion manifest does not record candidate path")
        return errors
    candidate = _resolve_project_path(root, candidate_value)
    governed_candidate = _candidate_path_for_task(root, task)
    if governed_candidate.exists() and governed_candidate.resolve() != candidate.resolve():
        errors.append(
            "promotion manifest candidate does not match the candidate governed "
            "by the current task package"
        )
    historical = validate_historical_promotion(root, scene_id, payload)
    if historical.passed:
        if not historical.current:
            errors.append("historical promotion was superseded by a newer prose candidate")
    else:
        if historical.status != "legacy":
            errors.extend(historical.errors)
        errors.extend(_candidate_generation_gate_errors(root, task, candidate))
        errors.extend(_candidate_review_gate_errors(root, task, candidate))
    draft = root / "drafts" / "scenes" / f"{scene_id}.md"
    if draft.exists() and not final_body_from_draft_path(draft):
        errors.append(f"promoted draft has no cleaned deliverable body: {_rel(draft, root)}")
    return errors


def _static_review_gate_errors(root: Path, scene_id: str, *, require_pass: bool = True) -> list[str]:
    path = root / "reviews" / f"{scene_id}-review.md"
    conclusion = _static_review_conclusion(path)
    allowed = {"pass", "pass_with_notes", "revise_required", "reject"}
    draft = root / "drafts" / "scenes" / f"{scene_id}.md"
    if conclusion not in allowed:
        return [f"static review conclusion must be recorded; got {conclusion or 'missing'} at {_rel(path, root)}"]
    if not _static_review_matches_draft(path, draft):
        return [f"static review is stale for current promoted draft at {_rel(path, root)}"]
    if not require_pass or conclusion == "pass":
        return []
    return [f"static review conclusion must be pass; got {conclusion or 'missing'} at {_rel(path, root)}"]


def _static_review_matches_draft(review: Path, draft: Path) -> bool:
    if not review.is_file() or not draft.is_file():
        return False
    match = re.search(r"(?m)^-\s*审查对象 SHA-256：`([0-9a-fA-F]{64})`\s*$", _read_text(review))
    return bool(match and match.group(1).lower() == _file_sha256(draft))


def _state_patch_gate_errors(root: Path, scene_id: str) -> list[str]:
    path = root / "characters" / "state_patches" / f"{scene_id}_state_patch.json"
    payload, error = _read_optional_json(path)
    if error:
        return [error]
    if not payload:
        return [f"state patch JSON is missing or empty: {_rel(path, root)}"]
    errors: list[str] = []
    if str(payload.get("schema") or "") != "literary-engineering-workbench/character-state-patch/v0.1":
        errors.append("state patch JSON has wrong or missing schema")
    if str(payload.get("scene_id") or "") not in {"", scene_id}:
        errors.append(f"state patch scene_id mismatch: {payload.get('scene_id')}")
    if str(payload.get("status") or "").strip().lower() not in {"pending_human_approval", "candidate", "reviewed", "approved"}:
        errors.append("state patch status must remain candidate/review/approval-scoped")
    return errors


def _canon_writeback_gate_errors(
    root: Path,
    scene_id: str,
    *,
    require_review: bool = True,
) -> list[str]:
    status = canon_writeback_status(root, scene_id, require_review=require_review)
    state = str(status.get("status") or "")
    if state in {"pass", "not_required"}:
        return []
    return [f"canon writeback gate is not complete for {scene_id}: {status.get('message')}"]


def _candidate_path_for_task(root: Path, task: dict[str, object]) -> Path:
    candidates = [
        *[str(item) for item in task.get("submitted_artifacts") or []],
        *[str(item) for item in task.get("expected_outputs") or []],
        *[str(item) for item in task.get("source_paths") or []],
    ]
    for item in candidates:
        normalized = item.replace("\\", "/")
        if not normalized.endswith(".md"):
            continue
        if normalized.endswith(".agent_tasks.md") or normalized.endswith(".prompt.md"):
            continue
        if "/drafts/candidates/" in f"/{normalized}" or "/drafts/revisions/" in f"/{normalized}":
            return _resolve_project_path(root, item)
    scene_id = str(task.get("scene_id") or "scene")
    return root / "drafts" / "candidates" / f"{scene_id}-platform-agent.md"


def _scene_path_for_task(root: Path, task: dict[str, object]) -> Path:
    scene = str(task.get("scene") or "")
    if scene:
        return _resolve_project_path(root, scene)
    scene_id = str(task.get("scene_id") or "scene_0001")
    return root / "scenes" / f"{scene_id}.yaml"
