"""Promote a generated scene candidate into the reviewed draft lane."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .agent_schema import validate_payload
from .agent_tasks import agent_task_completion_status
from .anti_ai_style import style_lint_gate, style_lint_gate_message
from .flow_gates import FlowGateError
from .new_character_register import new_character_register_issues
from .reader_experience import reader_experience_adherence_for_body
from .word_budget import word_budget_adherence_for_body


@dataclass(frozen=True)
class CandidatePromotionResult:
    project_root: Path
    candidate_path: Path
    draft_path: Path
    manifest_path: Path
    report_path: Path
    scene_id: str
    chars: int
    approval_run_id: str


def promote_scene_candidate(
    project_root: Path,
    scene: Path | None = None,
    candidate: Path | None = None,
    output: Path | None = None,
    overwrite: bool = False,
    approval_run_id: str = "",
    selection_note: str = "",
    allow_unreviewed: bool = False,
    allow_review_notes: bool = False,
) -> CandidatePromotionResult:
    """Convert a provider candidate into a standard scene draft workspace."""

    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")

    scene_path = root / "scenes" / "scene_0001.yaml" if scene is None else _resolve(root, scene)
    if not scene_path.exists():
        raise FileNotFoundError(f"scene file not found: {scene_path}")
    scene_id = scene_path.stem or "scene"
    candidate_path = _resolve_candidate(root, scene_id, candidate)
    candidate_text = _read(candidate_path)
    if not candidate_text:
        raise FileNotFoundError(f"candidate not found or empty: {candidate_path}")

    draft_path = _resolve(root, output, root / "drafts" / "scenes" / f"{scene_id}.md")
    if draft_path.exists() and not overwrite:
        raise FileExistsError(f"draft already exists: {draft_path}. pass overwrite=True to replace it")
    draft_path.parent.mkdir(parents=True, exist_ok=True)

    body = _candidate_body(candidate_text)
    if not body:
        raise ValueError(f"candidate has no usable body: {candidate_path}")
    generation_gate = candidate_generation_gate(root, scene_id, candidate_path)
    if not allow_unreviewed:
        _ensure_candidate_generation_provenance(generation_gate)
    review_gate = candidate_review_gate(root, scene_id, candidate_path)
    if not allow_unreviewed:
        _ensure_candidate_reviewed(review_gate, allow_review_notes=allow_review_notes)
    sections = {
        "new_facts": _candidate_bullets(candidate_text, "新增事实候选"),
        "character_changes": _candidate_bullets(candidate_text, "人物状态变化"),
        "relationship_changes": _candidate_bullets(candidate_text, "关系变化"),
        "foreshadowing_changes": _candidate_bullets(candidate_text, "伏笔变化"),
        "approval_items": _candidate_bullets(candidate_text, "需要人工确认"),
    }
    generated_at = _now()
    draft = _render_draft(
        scene_id=scene_id,
        scene_path=_rel(scene_path, root),
        candidate_path=_rel(candidate_path, root),
        generated_at=generated_at,
        body=body,
        sections=sections,
    )
    draft_path.write_text(draft, encoding="utf-8")

    manifest_path = root / "drafts" / "promotions" / f"{scene_id}_promotion.json"
    report_path = root / "drafts" / "promotions" / f"{scene_id}_promotion.md"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": "literary-engineering-workbench/candidate-promotion/v0.1",
        "promoted_at": generated_at,
        "scene_id": scene_id,
        "scene": _rel(scene_path, root),
        "candidate": _rel(candidate_path, root),
        "draft": _rel(draft_path, root),
        "approval_run_id": approval_run_id,
        "selection_note": selection_note,
        "candidate_review": review_gate,
        "candidate_generation": generation_gate,
        "style_lint_gate": review_gate.get("style_lint", {}),
        "allow_unreviewed": allow_unreviewed,
        "allow_review_notes": allow_review_notes,
        "chars": len(draft),
        "writeback_sections": sections,
        "canon_writeback": _canon_writeback_declaration(root, candidate_path),
        "guardrails": [
            "本命令只把候选稿转入草稿审查通道，不确认 canon。",
            "默认必须先完成针对该候选稿的正式平台 Agent 场景审查。",
            "默认必须先完成正式生成 provenance：CLI prompt manifest、.agent_tasks.md 和平台 Agent candidate manifest。",
            "候选正文必须通过 Style Lint Gate：机械对照句式和 medium+ AI 腔风险阻塞 promotion，low 风险进入审查 notes。",
            "转正后的草稿仍必须运行 review-scene 和后续平台 Agent 场景审查。",
            "人物、关系和 canon 写回仍必须走单独审批链路。",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(_render_report(manifest), encoding="utf-8")
    return CandidatePromotionResult(
        project_root=root,
        candidate_path=candidate_path,
        draft_path=draft_path,
        manifest_path=manifest_path,
        report_path=report_path,
        scene_id=scene_id,
        chars=len(draft),
        approval_run_id=approval_run_id,
    )


def _resolve_candidate(root: Path, scene_id: str, candidate: Path | None) -> Path:
    if candidate is not None:
        return _resolve(root, candidate)
    candidates = sorted(
        (root / "drafts" / "candidates").glob(f"{scene_id}-*.md"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"no candidate found for scene: {scene_id}")
    return candidates[0]


def candidate_generation_gate(root: Path, scene_id: str, candidate_path: Path) -> dict[str, object]:
    """Check that a prose candidate came from the formal CLI sidecar handoff."""

    rel_candidate = _rel(candidate_path, root)
    manifest_path = candidate_path.with_suffix(".json")
    prompt_manifest_path = candidate_path.with_suffix(".prompt.json")
    task_path = candidate_path.with_suffix(".agent_tasks.md")
    gate: dict[str, object] = {
        "required": True,
        "candidate": rel_candidate,
        "manifest": _rel(manifest_path, root),
        "prompt_manifest": _rel(prompt_manifest_path, root),
        "agent_tasks": _rel(task_path, root),
        "agent_task_completion": agent_task_completion_status(task_path, root=root),
        "status": "missing",
        "message": "candidate generation provenance is missing",
        "missing": [],
        "invalid": [],
        "revision_candidate": _is_revision_candidate_path(root, candidate_path),
    }
    missing: list[str] = []
    invalid: list[str] = []
    if not candidate_path.exists():
        missing.append(rel_candidate)
    if not manifest_path.exists():
        missing.append(_rel(manifest_path, root))
    if not prompt_manifest_path.exists():
        missing.append(_rel(prompt_manifest_path, root))
    if not task_path.exists():
        missing.append(_rel(task_path, root))
    completion = agent_task_completion_status(task_path, root=root)
    if task_path.exists() and completion.get("complete") is not True:
        invalid.append(f"generation agent task incomplete: {completion.get('message')}")
    payload = _read_json(manifest_path)
    if manifest_path.exists() and not payload:
        invalid.append("manifest is not valid JSON")
    if payload:
        generated_by = str(payload.get("generated_by") or "").strip()
        provider = str(payload.get("provider") or "").strip()
        manifest_candidate = str(payload.get("candidate") or "").strip()
        if generated_by != "platform-agent":
            invalid.append(f"generated_by={generated_by or 'missing'}")
        if provider in {"dry-run", "http-chat"}:
            invalid.append(f"legacy provider candidate: {provider}")
        if manifest_candidate and _normalize_review_path(manifest_candidate) != _normalize_review_path(rel_candidate):
            invalid.append(f"manifest candidate mismatch: {manifest_candidate}")
        if gate["revision_candidate"]:
            if payload.get("anti_evasion_protocol_applied") is not True:
                invalid.append("anti_evasion_protocol_applied is not true")
            unresolved = payload.get("evasion_risks_unresolved")
            if not _empty_unresolved(unresolved):
                invalid.append("evasion_risks_unresolved is not clean")
        else:
            for key in ("style_generation_standard_applied", "hard_constraints_applied", "anti_evasion_protocol_applied"):
                if payload.get(key) is not True:
                    invalid.append(f"{key} is not true")
            if payload.get("narrative_rhythm_standard_applied") is not True:
                invalid.append("narrative_rhythm_standard_applied is not true")
            for key in ("word_budget_standard_applied", "pass_with_notes_actions_applied"):
                if key not in payload or not isinstance(payload.get(key), bool):
                    invalid.append(f"{key} must be a boolean")
            if not str(payload.get("prompt_manifest") or "").strip() and not prompt_manifest_path.exists():
                invalid.append("prompt_manifest is missing")
            canon_decl = _canon_writeback_declaration(root, candidate_path)
            canon_change = _canon_change_value(canon_decl.get("canon_change"))
            if canon_change is None:
                invalid.append("canon_change declaration is missing")
            if canon_change is False and not str(canon_decl.get("no_canon_change_reason") or "").strip():
                invalid.append("canon_change=false requires no_canon_change_reason")
        invalid.extend(new_character_register_issues(payload, root, mode="generation"))
        prompt_payload = _read_json(prompt_manifest_path)
        standards = prompt_payload.get("generation_standards") if isinstance(prompt_payload.get("generation_standards"), dict) else {}
        rhythm_standard = standards.get("narrative_rhythm_contract") if isinstance(standards, dict) else {}
        if not isinstance(rhythm_standard, dict) or rhythm_standard.get("status") not in {"pass", "defaulted"}:
            invalid.append("prompt manifest missing ready generation_standards.narrative_rhythm_contract")
        scene_path = root / "scenes" / f"{scene_id}.yaml"
        candidate_body = _candidate_body(_read(candidate_path)) if candidate_path.exists() else ""
        reader = reader_experience_adherence_for_body(root, scene_path, candidate_body)
        if reader.get("status") != "not_required":
            reader_standard = standards.get("reader_experience_contract") if isinstance(standards, dict) else {}
            if not isinstance(reader_standard, dict) or reader_standard.get("status") not in {"pass", "not_required"}:
                invalid.append("prompt manifest missing ready generation_standards.reader_experience_contract")
            if not isinstance(payload.get("reader_experience_contract"), dict):
                invalid.append("candidate manifest missing reader_experience_contract")
    if missing:
        gate.update({"status": "missing", "missing": missing, "invalid": invalid, "message": "formal candidate generation files are missing"})
    elif invalid:
        gate.update({"status": "invalid", "missing": missing, "invalid": invalid, "message": "formal candidate generation provenance is invalid"})
    else:
        gate.update({"status": "pass", "missing": [], "invalid": [], "message": "formal candidate generation provenance passed"})
    return gate


def _canon_writeback_declaration(root: Path, candidate_path: Path) -> dict[str, object]:
    payload = _read_json(candidate_path.with_suffix(".json"))
    nested = payload.get("canon_writeback") if isinstance(payload.get("canon_writeback"), dict) else {}
    canon_change = nested.get("canon_change") if isinstance(nested, dict) and "canon_change" in nested else payload.get("canon_change")
    no_change_reason = (
        str(nested.get("no_canon_change_reason") or "").strip()
        if isinstance(nested, dict)
        else ""
    ) or str(payload.get("no_canon_change_reason") or "").strip()
    return {
        "canon_change": canon_change,
        "no_canon_change_reason": no_change_reason,
        "candidate_patch": str(nested.get("candidate_patch") or "") if isinstance(nested, dict) else "",
        "source": _rel(candidate_path.with_suffix(".json"), root),
        "note": "promotion carries declaration only; canon-evolve creates/applies no canon automatically.",
    }


def candidate_review_gate(root: Path, scene_id: str, candidate_path: Path) -> dict[str, object]:
    review_path = root / "reviews" / "agent" / f"{scene_id}_scene_review.json"
    review_task = review_path.with_suffix(".agent_tasks.md")
    scene_path = root / "scenes" / f"{scene_id}.yaml"
    rel_candidate = _rel(candidate_path, root)
    candidate_text = _read(candidate_path)
    candidate_body = _candidate_body(candidate_text) or candidate_text
    lint_gate = style_lint_gate(candidate_body)
    word_budget = word_budget_adherence_for_body(root, scene_path, candidate_body)
    reader_experience = reader_experience_adherence_for_body(root, scene_path, candidate_body)
    review_completion = agent_task_completion_status(review_task, root=root)
    gate: dict[str, object] = {
        "required": True,
        "review": _rel(review_path, root),
        "agent_tasks": _rel(review_task, root),
        "agent_task_completion": review_completion,
        "candidate": rel_candidate,
        "style_lint": lint_gate,
        "word_budget_adherence": word_budget,
        "reader_experience_adherence": reader_experience,
        "mounted_style_required": _mounted_style_exists(root),
        "status": "missing",
        "conclusion": "",
        "style_adherence": "",
        "word_budget_status": str(word_budget.get("status") or ""),
        "reader_experience_status": str(reader_experience.get("status") or ""),
        "schema_errors": [],
        "unresolved_notes": [],
        "source_match": False,
        "message": "candidate review is missing",
    }
    if not review_path.exists():
        return gate
    payload = _read_json(review_path)
    errors, _warnings = validate_payload(payload, "scene_review.v1") if payload else ([{"path": "review", "message": "invalid json", "actual": ""}], [])
    conclusion = str(payload.get("conclusion") or "").strip().lower()
    style = payload.get("style_adherence") if isinstance(payload.get("style_adherence"), dict) else {}
    style_status = str(style.get("status") or "").strip().lower() if isinstance(style, dict) else ""
    source_match = _review_mentions_candidate(payload, rel_candidate, candidate_path)
    unresolved = _unresolved_review_notes(payload)
    new_character_issues = new_character_register_issues(payload, root, mode="review") if payload else ["new_character_register is missing"]
    style_required = _mounted_style_exists(root)
    style_passed = not style_required or style_status in {"pass", "pass_with_notes"}
    style_lint_passed = lint_gate.get("status") != "blocking"
    review_budget = payload.get("word_budget_adherence") if isinstance(payload.get("word_budget_adherence"), dict) else {}
    review_budget_status = str(review_budget.get("status") or "").strip().lower()
    review_reader = payload.get("reader_experience_adherence") if isinstance(payload.get("reader_experience_adherence"), dict) else {}
    review_reader_status = str(review_reader.get("status") or "").strip().lower()
    review_rhythm = payload.get("narrative_rhythm_adherence") if isinstance(payload.get("narrative_rhythm_adherence"), dict) else {}
    review_rhythm_status = str(review_rhythm.get("status") or "").strip().lower()
    review_canon = payload.get("canon_writeback") if isinstance(payload.get("canon_writeback"), dict) else {}
    canon_review_ok, canon_review_status, canon_review_message = _canon_writeback_review_gate(review_canon)
    revision_integrity_ok, revision_integrity_status, revision_integrity_message = _revision_integrity_review_gate(
        payload.get("revision_integrity") if isinstance(payload.get("revision_integrity"), dict) else {}
    )
    budget_status = str(word_budget.get("status") or "").strip().lower()
    reader_status = str(reader_experience.get("status") or "").strip().lower()
    budget_passed = budget_status in {"pass", "not_required"}
    review_budget_passed = review_budget_status in {"pass", "not_required"} and review_budget.get("narrative_load_satisfied") is not False
    reader_required = reader_status != "not_required"
    reader_passed = reader_status in {"pass", "not_required"}
    review_reader_passed = (not reader_required) or (
        review_reader_status in {"pass", "not_required"} and review_reader.get("reader_promise_satisfied") is not False
    )
    review_rhythm_passed = review_rhythm_status in {"pass", "not_applicable"} and review_rhythm.get("rhythm_executed") is not False and review_rhythm.get("bridge_executed") is not False
    task_completed = review_completion.get("complete") is True
    passed = (
        not errors
        and task_completed
        and source_match
        and conclusion == "pass"
        and style_passed
        and not unresolved
        and style_lint_passed
        and budget_passed
        and review_budget_passed
        and reader_passed
        and review_reader_passed
        and review_rhythm_passed
        and canon_review_ok
        and revision_integrity_ok
        and not new_character_issues
    )
    if passed:
        status = "pass"
        message = "candidate review passed"
    elif errors:
        status = "schema_failed"
        message = "candidate review JSON does not satisfy scene_review.v1"
    elif not task_completed:
        status = "task_incomplete"
        message = f"scene review agent task is incomplete: {review_completion.get('message')}"
    elif not source_match:
        status = "stale_or_wrong_source"
        message = "scene review does not cite this candidate in source_paths/candidate"
    elif conclusion not in {"pass", "pass_with_notes"}:
        status = "failed"
        message = f"candidate review conclusion is {conclusion or 'missing'}"
    elif not style_passed:
        status = "style_failed"
        message = f"mounted style review did not pass for this candidate: style_adherence.status={style_status or 'missing'}"
    elif not style_lint_passed:
        status = "style_lint_failed"
        message = f"candidate failed Style Lint Gate: {style_lint_gate_message(lint_gate)}"
    elif not budget_passed:
        status = "word_budget_failed"
        message = f"candidate failed scene word-budget gate: {word_budget.get('message')}"
    elif not review_budget_passed:
        status = "word_budget_review_failed"
        message = f"AgentReview did not pass word_budget_adherence: {review_budget_status or 'missing'}"
    elif not reader_passed:
        status = "reader_experience_failed"
        message = f"candidate failed reader-experience gate: {reader_experience.get('message')}"
    elif not review_reader_passed:
        status = "reader_experience_review_failed"
        message = f"AgentReview did not pass reader_experience_adherence: {review_reader_status or 'missing'}"
    elif not review_rhythm_passed:
        status = "narrative_rhythm_review_failed"
        message = f"AgentReview did not pass narrative_rhythm_adherence: {review_rhythm_status or 'missing'}"
    elif not canon_review_ok:
        status = "canon_writeback_review_failed"
        message = f"AgentReview did not resolve canon_writeback declaration: {canon_review_message}"
    elif not revision_integrity_ok:
        status = "revision_integrity_review_failed"
        message = f"AgentReview did not pass revision_integrity: {revision_integrity_message}"
    elif new_character_issues:
        status = "new_character_unresolved"
        message = "AgentReview did not resolve new_character_register: " + "; ".join(new_character_issues)
    elif unresolved:
        status = "notes_unresolved"
        message = "candidate review has pass_with_notes/warnings/revision/style notes that must be revised or explicitly waived"
    else:
        status = "failed"
        message = "candidate review did not pass"
    gate.update(
        {
            "status": status,
            "conclusion": conclusion,
            "style_adherence": style_status,
            "word_budget_status": budget_status,
            "reader_experience_status": reader_status,
            "narrative_rhythm_status": review_rhythm_status,
            "canon_writeback_review_status": canon_review_status,
            "revision_integrity_status": revision_integrity_status,
            "schema_errors": errors,
            "unresolved_notes": unresolved,
            "new_character_register_issues": new_character_issues,
            "source_match": source_match,
            "message": message,
        }
    )
    return gate


def _ensure_candidate_generation_provenance(gate: dict[str, object]) -> None:
    if gate.get("status") == "pass":
        return
    candidate = str(gate.get("candidate") or "")
    missing = gate.get("missing")
    invalid = gate.get("invalid")
    details: list[str] = []
    if isinstance(missing, list) and missing:
        details.append("missing=" + ", ".join(str(item) for item in missing))
    if isinstance(invalid, list) and invalid:
        details.append("invalid=" + ", ".join(str(item) for item in invalid))
    suffix = (" " + "; ".join(details) + ".") if details else ""
    raise FlowGateError(
        "formal CLI generation provenance required before promote-candidate: "
        f"{candidate} is not a formal platform-agent candidate.{suffix} "
        "Run generate-scene to create the prompt manifest and .agent_tasks.md, have the main platform agent write the candidate Markdown and manifest JSON with constraint flags, "
        "then run agent-review-scene on that exact candidate. Manual files are exploratory/debug-only; --allow-unreviewed is maintainer/debug-only."
    )


def _ensure_candidate_reviewed(gate: dict[str, object], *, allow_review_notes: bool) -> None:
    if gate.get("status") == "pass":
        return
    if allow_review_notes and gate.get("status") == "notes_unresolved":
        return
    message = str(gate.get("message") or "candidate review gate failed")
    review = str(gate.get("review") or "")
    candidate = str(gate.get("candidate") or "")
    lint_gate = gate.get("style_lint")
    lint_hint = ""
    if isinstance(lint_gate, dict) and lint_gate.get("status") == "blocking":
        lint_hint = f" Style Lint Gate: {style_lint_gate_message(lint_gate)}."
    raise FlowGateError(
        "formal candidate review required before promote-candidate: "
        f"{message}.{lint_hint} Run agent-review-scene with --draft {candidate}, have the platform agent write {review}, "
        "and promote only after conclusion=pass with this candidate listed in source_paths. "
        "Formal Skill hosts must not use --allow-unreviewed to bypass this gate; that flag is maintainer/debug-only."
    )


def _review_mentions_candidate(payload: dict[str, object], rel_candidate: str, candidate_path: Path) -> bool:
    expected = _normalize_review_path(rel_candidate)
    absolute = _normalize_review_path(str(candidate_path.resolve()))
    direct_values = [
        payload.get("candidate"),
        payload.get("reviewed_candidate"),
        payload.get("draft"),
        payload.get("source_candidate"),
    ]
    source_paths = payload.get("source_paths")
    if isinstance(source_paths, list):
        direct_values.extend(source_paths)
    for value in direct_values:
        normalized = _normalize_review_path(str(value or ""))
        if normalized in {expected, absolute}:
            return True
    return False


def _unresolved_review_notes(payload: dict[str, object]) -> list[str]:
    notes: list[str] = []
    conclusion = str(payload.get("conclusion") or "").strip().lower()
    if conclusion in {"pass_with_notes", "revise_required", "reject"}:
        notes.append(f"conclusion={conclusion}")
    for key in ("blocking_issues", "warnings", "revision_actions", "style_notes"):
        value = payload.get(key)
        if isinstance(value, list) and value:
            notes.append(key)
    style = payload.get("style_adherence")
    if isinstance(style, dict):
        style_status = str(style.get("status") or "").strip().lower()
        if style_status in {"pass_with_notes", "revise_required", "reject"}:
            notes.append(f"style_adherence.status={style_status}")
        for key in ("deviations", "revision_actions"):
            value = style.get(key)
            if isinstance(value, list) and value:
                notes.append(f"style_adherence.{key}")
    budget = payload.get("word_budget_adherence")
    if isinstance(budget, dict):
        budget_status = str(budget.get("status") or "").strip().lower()
        if budget_status not in {"", "pass", "not_required"}:
            notes.append(f"word_budget_adherence.status={budget_status}")
        if budget_status in {"pass", "not_required"} and budget.get("narrative_load_satisfied") is False:
            notes.append("word_budget_adherence.narrative_load_satisfied=false")
    reader = payload.get("reader_experience_adherence")
    if isinstance(reader, dict):
        reader_status = str(reader.get("status") or "").strip().lower()
        if reader_status not in {"", "pass", "not_required"}:
            notes.append(f"reader_experience_adherence.status={reader_status}")
        if reader_status in {"pass", "not_required"} and reader.get("reader_promise_satisfied") is False:
            notes.append("reader_experience_adherence.reader_promise_satisfied=false")
    rhythm = payload.get("narrative_rhythm_adherence")
    if isinstance(rhythm, dict):
        rhythm_status = str(rhythm.get("status") or "").strip().lower()
        if rhythm_status not in {"", "pass", "not_applicable"}:
            notes.append(f"narrative_rhythm_adherence.status={rhythm_status}")
        if rhythm_status in {"pass", "not_applicable"} and rhythm.get("rhythm_executed") is False:
            notes.append("narrative_rhythm_adherence.rhythm_executed=false")
        if rhythm_status in {"pass", "not_applicable"} and rhythm.get("bridge_executed") is False:
            notes.append("narrative_rhythm_adherence.bridge_executed=false")
    canon_ok, canon_status, canon_message = _canon_writeback_review_gate(
        payload.get("canon_writeback") if isinstance(payload.get("canon_writeback"), dict) else {}
    )
    if not canon_ok:
        notes.append(f"canon_writeback.{canon_status}:{canon_message}")
    revision_ok, revision_status, revision_message = _revision_integrity_review_gate(
        payload.get("revision_integrity") if isinstance(payload.get("revision_integrity"), dict) else {}
    )
    if not revision_ok:
        notes.append(f"revision_integrity.{revision_status}:{revision_message}")
    return notes


def _revision_integrity_review_gate(value: dict[str, object]) -> tuple[bool, str, str]:
    if not value:
        return False, "missing", "revision_integrity object is missing"
    status = str(value.get("status") or "").strip().lower()
    if status not in {"pass", "not_applicable"}:
        return False, status or "missing_status", f"status={status or 'missing'}"
    if value.get("anti_evasion_checked") is not True:
        return False, "unchecked", "anti_evasion_checked must be true"
    unresolved = value.get("evasion_risks_unresolved")
    if not _empty_unresolved(unresolved):
        return False, "unresolved", "evasion_risks_unresolved must be empty/false"
    return True, status, "revision integrity reviewed"


def _canon_writeback_review_gate(value: dict[str, object]) -> tuple[bool, str, str]:
    if not value:
        return False, "missing", "canon_writeback object is missing"
    status = str(value.get("status") or "").strip().lower()
    change = _canon_change_value(value.get("canon_change"))
    if status not in {"pass", "not_required", "pending_canon_evolve", "unknown"}:
        return False, status or "missing_status", f"status={status or 'missing'}"
    if change is False:
        reason = str(value.get("no_canon_change_reason") or "").strip()
        if not reason:
            return False, "missing_reason", "canon_change=false requires no_canon_change_reason"
        return True, "no_change", "canon no-change declaration is explicit"
    if change in {True, "unknown"}:
        return True, "needs_canon_evolve" if change is True else "unknown", "canon writeback requires canon-evolve route gate"
    return False, "missing_change", "canon_change must be true, false, or unknown"


def _canon_change_value(value: object) -> bool | str | None:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"true", "yes", "1", "changed", "change"}:
        return True
    if text in {"false", "no", "0", "none", "no_change", "not_required"}:
        return False
    if text in {"unknown", "pending", "todo", "needs_review"}:
        return "unknown"
    return None


def _normalize_review_path(value: str) -> str:
    return value.replace("\\", "/").strip().strip("`").lstrip("./")


def _is_revision_candidate_path(root: Path, candidate_path: Path) -> bool:
    try:
        rel = candidate_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = str(candidate_path)
    return rel.startswith("drafts/revisions/") or candidate_path.name.endswith("_revision.md")


def _empty_unresolved(value: object) -> bool:
    if isinstance(value, bool):
        return not value
    if isinstance(value, list):
        return len(value) == 0
    if isinstance(value, str):
        return value.strip().lower() in {"", "false", "none", "no", "[]", "无"}
    return value in (None, 0)


def _mounted_style_exists(root: Path) -> bool:
    active = root / "style" / "active_style_skill.json"
    if active.exists():
        return True
    mounted = root / "style" / "mounted"
    return mounted.exists() and any(mounted.iterdir())


def _candidate_body(text: str) -> str:
    body = _section(text, "正文候选", stop_heading="状态变化候选")
    if body:
        return body
    body = _section(text, "修订正文候选", stop_heading="状态变化候选")
    if body:
        return body
    return _section(text, "正文草稿", stop_heading="状态变化")


def _candidate_bullets(text: str, heading: str) -> list[str]:
    section = _section(text, heading, level=3)
    items = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        item = stripped.lstrip("-").strip()
        if item and item not in {"无。", "待真实 provider 补全。"}:
            items.append(item)
    return items or ["无。"]


def _section(text: str, heading: str, level: int = 2, stop_heading: str = "") -> str:
    marks = "#" * level
    if stop_heading:
        pattern = rf"(?ms)^{marks}\s*{re.escape(heading)}\s*\n(.*?)(?=^{marks}\s*{re.escape(stop_heading)}\s*$|\Z)"
    else:
        pattern = rf"(?ms)^{marks}\s*{re.escape(heading)}\s*\n(.*?)(?=^###\s+|^##\s+|\Z)"
    match = re.search(pattern, text)
    if not match:
        return ""
    return match.group(1).strip()


def _render_draft(
    scene_id: str,
    scene_path: str,
    candidate_path: str,
    generated_at: str,
    body: str,
    sections: dict[str, list[str]],
) -> str:
    return f"""# 场景草稿工作台：{scene_id}

生成时间：{generated_at}

来源候选：`{candidate_path}`
场景文件：`{scene_path}`

## 使用规则

- 本文件由模型候选转入草稿通道，不是最终正稿。
- 写作时必须遵守上下文包中的硬 canon、人物状态和风格约束。
- 审查未通过前，不得把正文移动到正稿。
- 新事实、人物状态、关系和伏笔变化只列为候选，等待人工确认。

## 正文草稿

{body.strip()}

## 状态变化

### 新增事实候选

{_md_list(sections["new_facts"])}

### 人物状态变化

{_md_list(sections["character_changes"])}

### 关系变化

{_md_list(sections["relationship_changes"])}

### 伏笔变化

{_md_list(sections["foreshadowing_changes"])}

### 需要人工确认

{_md_list(sections["approval_items"])}

## 自检

- [ ] 未违背硬 canon。
- [ ] 人物行动符合当前 BDI。
- [ ] 背景故事没有被直白交代，只转化为行为和潜台词。
- [ ] 场景有明确冲突和输出状态。
- [ ] 文风约束被执行。
- [ ] 新事实已列入候选而非直接确认为 canon。
"""


def _render_report(manifest: dict[str, object]) -> str:
    lines = [
        f"# Candidate Promotion：{manifest['scene_id']}",
        "",
        f"- 候选：`{manifest['candidate']}`",
        f"- 草稿：`{manifest['draft']}`",
        f"- 时间：{manifest['promoted_at']}",
        f"- 审批 run：`{manifest.get('approval_run_id') or 'n/a'}`",
        "",
        "## 边界",
        "",
        _md_list(list(manifest["guardrails"])),
    ]
    note = str(manifest.get("selection_note") or "").strip()
    if note:
        lines.extend(["", "## 选择说明", "", note])
    return "\n".join(lines) + "\n"


def _md_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- 无。"


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _resolve(root: Path, value: Path | None, default: Path | None = None) -> Path:
    if value is None:
        if default is None:
            raise ValueError("default path is required when value is None")
        return default
    return value if value.is_absolute() else root / value


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
