"""Exact-candidate AgentReview gate and ordered failure diagnosis."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

from ....agent_schema import validate_payload
from ....agent_tasks import agent_task_completion_status
from ....anti_ai_style import style_lint_gate, style_lint_gate_message
from ....context_broker import context_trace_status
from ....creative_quality import creative_quality_profile_exists, load_creative_quality_profile
from ....new_character_register import new_character_register_issues
from ....reader_experience import reader_experience_adherence_for_body
from ....word_budget import word_budget_adherence_for_body
from .gate_support import (
    candidate_body,
    canon_change_value,
    empty_unresolved,
    mounted_style_exists,
    normalize_review_path,
    read_json,
    read_text,
    relative_path,
)
from .style_gate import review_style_snapshot_projection, review_style_state


@dataclass(frozen=True)
class GateCheck:
    passed: bool
    status: str
    message: str


def candidate_review_gate(root: Path, scene_id: str, candidate_path: Path) -> dict[str, object]:
    foundation = _review_foundation(root, scene_id, candidate_path)
    gate = _review_gate_base(foundation)
    review_path = foundation["review_path"]
    if not review_path.exists():
        return gate
    payload = read_json(review_path)
    assessment = _review_assessment(root, candidate_path, payload, foundation)
    decision = _review_decision(assessment)
    gate.update(_review_projection(assessment, decision))
    return gate


def _review_foundation(root: Path, scene_id: str, candidate_path: Path) -> dict[str, object]:
    review_path = root / "reviews" / "agent" / f"{scene_id}_scene_review.json"
    review_task = review_path.with_suffix(".agent_tasks.md")
    scene_path = root / "scenes" / f"{scene_id}.yaml"
    text = read_text(candidate_path)
    body = candidate_body(text) or text
    quality = load_creative_quality_profile(root)
    return {
        "root": root,
        "review_path": review_path,
        "review_task": review_task,
        "scene_path": scene_path,
        "candidate_path": candidate_path,
        "candidate_rel": relative_path(candidate_path, root),
        "candidate_body": body,
        "quality_profile": quality,
        "quality_required": creative_quality_profile_exists(root),
        "style_required": mounted_style_exists(root),
        "lint_gate": style_lint_gate(body, profile=quality, scope=scene_id),
        "word_budget": word_budget_adherence_for_body(root, scene_path, body, materialization_scope="scene"),
        "reader_experience": reader_experience_adherence_for_body(root, scene_path, body),
        "review_completion": agent_task_completion_status(review_task, root=root),
        "context_trace": context_trace_status(root, scene_id),
    }


def _review_gate_base(f: dict[str, object]) -> dict[str, object]:
    word_budget = f["word_budget"]
    reader = f["reader_experience"]
    trace = f["context_trace"]
    quality = f["quality_profile"]
    return {
        "required": True,
        "review": relative_path(f["review_path"], f["root"]),
        "agent_tasks": relative_path(f["review_task"], f["root"]),
        "agent_task_completion": f["review_completion"],
        "candidate": f["candidate_rel"],
        "style_lint": f["lint_gate"],
        "word_budget_adherence": word_budget,
        "reader_experience_adherence": reader,
        "context_trace": {"status": trace.status, "message": trace.message},
        "creative_quality_profile": {
            "required": f["quality_required"],
            "revision": quality.get("revision"),
            "digest": quality.get("digest"),
            "name": quality.get("name"),
        },
        "mounted_style_required": f["style_required"],
        "status": "missing",
        "conclusion": "",
        "style_adherence": "",
        "word_budget_status": str(word_budget.get("status") or ""),
        "reader_experience_status": str(reader.get("status") or ""),
        "schema_errors": [],
        "unresolved_notes": [],
        "human_decision_notes": [],
        "source_match": False,
        "message": "candidate review is missing",
    }


def _review_assessment(
    root: Path,
    candidate_path: Path,
    payload: dict[str, object],
    f: dict[str, object],
) -> dict[str, object]:
    errors, _warnings = validate_payload(payload, "scene_review.v1") if payload else ([{"path": "review", "message": "invalid json", "actual": ""}], [])
    conclusion = str(payload.get("conclusion") or "").strip().lower()
    style = payload.get("style_adherence") if isinstance(payload.get("style_adherence"), dict) else {}
    style_status = str(style.get("status") or "").strip().lower()
    style_gate, _style_errors, style_failure, _style_passed = review_style_state(
        root,
        candidate_path,
        payload,
        style_required=bool(f["style_required"]),
        style_status=style_status,
    )
    budget = f["word_budget"]
    reader = f["reader_experience"]
    review_budget = _mapping(payload, "word_budget_adherence")
    review_reader = _mapping(payload, "reader_experience_adherence")
    review_rhythm = _mapping(payload, "narrative_rhythm_adherence")
    review_quality = _mapping(payload, "creative_quality_profile")
    canon_ok, canon_status, canon_message = _canon_writeback_review_gate(_mapping(payload, "canon_writeback"))
    revision_ok, revision_status, revision_message = _revision_integrity_review_gate(_mapping(payload, "revision_integrity"))
    session_ok, session_message = _review_session_independence(root, candidate_path, payload)
    return {
        "payload": payload,
        "errors": errors,
        "conclusion": conclusion,
        "style_status": style_status,
        "style_gate": style_gate,
        "style_failure": style_failure,
        "style_lint_passed": f["lint_gate"].get("status") != "blocking",
        "source_match": _review_mentions_candidate(payload, str(f["candidate_rel"]), candidate_path),
        "content_match": _candidate_review_content_match(payload, candidate_path),
        "unresolved": _unresolved_review_notes(payload),
        "human_decision_notes": _human_decision_notes(payload),
        "new_character_issues": new_character_register_issues(payload, root, mode="review") if payload else ["new_character_register is missing"],
        "task_completed": f["review_completion"].get("complete") is True,
        "task_message": f["review_completion"].get("message"),
        "context_trace": f["context_trace"],
        "review_fresh": f["review_path"].stat().st_mtime_ns >= candidate_path.stat().st_mtime_ns,
        "budget": budget,
        "budget_status": _status(budget),
        "budget_passed": _status(budget) in {"pass", "not_required"},
        "review_budget": review_budget,
        "review_budget_status": _status(review_budget),
        "reader": reader,
        "reader_status": _status(reader),
        "review_reader": review_reader,
        "review_reader_status": _status(review_reader),
        "review_rhythm": review_rhythm,
        "review_rhythm_status": _status(review_rhythm),
        "review_quality_passed": (not f["quality_required"]) or str(review_quality.get("digest") or "") == str(f["quality_profile"].get("digest") or ""),
        "canon_ok": canon_ok,
        "canon_status": canon_status,
        "canon_message": canon_message,
        "revision_ok": revision_ok,
        "revision_status": revision_status,
        "revision_message": revision_message,
        "session_ok": session_ok,
        "session_message": session_message,
        "lint_gate": f["lint_gate"],
    }


def _review_decision(a: dict[str, object]) -> GateCheck:
    checks = [
        *_review_identity_checks(a),
        *_review_literary_checks(a),
        *_review_resolution_checks(a),
    ]
    return next((check for check in checks if not check.passed), GateCheck(True, "pass", "candidate review passed"))


def _review_identity_checks(a: dict[str, object]) -> list[GateCheck]:
    conclusion = str(a["conclusion"])
    trace = a["context_trace"]
    return [
        GateCheck(not a["errors"], "schema_failed", "candidate review JSON does not satisfy scene_review.v1"),
        GateCheck(bool(a["task_completed"]), "task_incomplete", f"scene review agent task is incomplete: {a['task_message']}"),
        GateCheck(trace.passed, "context_trace_stale", f"candidate must be regenerated from a fresh context trace: {trace.message}"),
        GateCheck(bool(a["review_fresh"]), "stale_or_wrong_source", "scene review predates the current candidate; rerun independent AgentReview"),
        GateCheck(bool(a["source_match"]), "stale_or_wrong_source", "scene review does not cite this candidate in source_paths/candidate"),
        GateCheck(bool(a["content_match"]), "stale_or_wrong_source", "scene review candidate_sha256 does not match the current candidate content"),
        GateCheck(conclusion in {"pass", "pass_with_notes"}, "failed", f"candidate review conclusion is {conclusion or 'missing'}"),
    ]


def _review_literary_checks(a: dict[str, object]) -> list[GateCheck]:
    style_failure = a["style_failure"]
    style_check = GateCheck(True, "pass", "") if not style_failure else GateCheck(False, style_failure[0], style_failure[1])
    reader_required = a["reader_status"] != "not_required"
    review_budget_ok = a["review_budget_status"] in {"pass", "not_required"} and a["review_budget"].get("narrative_load_satisfied") is not False
    review_reader_ok = (not reader_required) or (a["review_reader_status"] in {"pass", "not_required"} and a["review_reader"].get("reader_promise_satisfied") is not False)
    rhythm_ok = a["review_rhythm_status"] in {"pass", "not_applicable"} and a["review_rhythm"].get("rhythm_executed") is not False and a["review_rhythm"].get("bridge_executed") is not False
    return [
        style_check,
        GateCheck(bool(a["style_lint_passed"]), "style_lint_failed", f"candidate failed Style Lint Gate: {style_lint_gate_message(a['lint_gate'])}"),
        GateCheck(bool(a["budget_passed"]), "word_budget_failed", f"candidate failed scene word-budget gate: {a['budget'].get('message')}"),
        GateCheck(review_budget_ok, "word_budget_review_failed", f"AgentReview did not pass word_budget_adherence: {a['review_budget_status'] or 'missing'}"),
        GateCheck(a["reader_status"] in {"pass", "not_required"}, "reader_experience_failed", f"candidate failed reader-experience gate: {a['reader'].get('message')}"),
        GateCheck(review_reader_ok, "reader_experience_review_failed", f"AgentReview did not pass reader_experience_adherence: {a['review_reader_status'] or 'missing'}"),
        GateCheck(rhythm_ok, "narrative_rhythm_review_failed", f"AgentReview did not pass narrative_rhythm_adherence: {a['review_rhythm_status'] or 'missing'}"),
        GateCheck(bool(a["review_quality_passed"]), "creative_quality_review_stale", "AgentReview was produced with a different creative quality profile; run formal review again"),
        GateCheck(bool(a["canon_ok"]), "canon_writeback_review_failed", f"AgentReview did not resolve canon_writeback declaration: {a['canon_message']}"),
        GateCheck(bool(a["revision_ok"]), "revision_integrity_review_failed", f"AgentReview did not pass revision_integrity: {a['revision_message']}"),
        GateCheck(bool(a["session_ok"]), "review_session_independence_failed", str(a["session_message"])),
    ]


def _review_resolution_checks(a: dict[str, object]) -> list[GateCheck]:
    human = a["human_decision_notes"]
    characters = a["new_character_issues"]
    unresolved = a["unresolved"]
    return [
        GateCheck(not human, "human_decision_required", "candidate review requires a recorded human or delegated decision before prose can be revised: " + "; ".join(human)),
        GateCheck(not characters, "new_character_unresolved", "AgentReview did not resolve new_character_register: " + "; ".join(characters)),
        GateCheck(not unresolved, "notes_unresolved", "candidate review has pass_with_notes/warnings/revision/style notes that must be revised or explicitly waived"),
    ]


def _review_projection(a: dict[str, object], decision: GateCheck) -> dict[str, object]:
    payload = a["payload"]
    return {
        "status": decision.status,
        "conclusion": a["conclusion"],
        "style_adherence": a["style_status"],
        **review_style_snapshot_projection(a["style_gate"]),
        "word_budget_status": a["budget_status"],
        "reader_experience_status": a["reader_status"],
        "narrative_rhythm_status": a["review_rhythm_status"],
        "canon_writeback_review_status": a["canon_status"],
        "revision_integrity_status": a["revision_status"],
        "review_session_independent": a["session_ok"],
        "review_session_message": a["session_message"],
        "schema_errors": a["errors"],
        "unresolved_notes": a["unresolved"],
        "human_decision_notes": a["human_decision_notes"],
        "candidate_sha256": str(payload.get("candidate_sha256") or "").strip().lower(),
        "new_character_register_issues": a["new_character_issues"],
        "source_match": a["source_match"],
        "message": decision.message,
    }


def _mapping(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def _status(value: dict[str, object]) -> str:
    return str(value.get("status") or "").strip().lower()


def _review_session_independence(root: Path, candidate_path: Path, review: dict[str, object]) -> tuple[bool, str]:
    candidate_manifest = read_json(candidate_path.with_suffix(".json"))
    revision = str(candidate_manifest.get("formal_contract_revision") or "").strip()
    if revision < "2026-07-23.3":
        return True, "legacy candidate contract has no session identity requirement"
    writer = str(candidate_manifest.get("writer_session_id") or "").strip()
    reviewer = str(review.get("reviewer_session_id") or "").strip()
    if not writer:
        return False, "current formal candidate manifest is missing writer_session_id"
    if not reviewer:
        return False, "scene_review.v1 is missing reviewer_session_id for the current formal contract"
    if writer == reviewer:
        return False, "reviewer_session_id must differ from the candidate writer_session_id"
    return True, "writer and reviewer session identities are independent"


def _candidate_review_content_match(payload: dict[str, object], candidate_path: Path) -> bool:
    if not candidate_path.is_file():
        return False
    actual = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
    recorded = str(payload.get("candidate_sha256") or "").strip().lower()
    return bool(recorded) and recorded == actual


def _review_mentions_candidate(payload: dict[str, object], rel_candidate: str, candidate_path: Path) -> bool:
    expected = normalize_review_path(rel_candidate)
    absolute = normalize_review_path(str(candidate_path.resolve()))
    values = [payload.get(key) for key in ("candidate", "reviewed_candidate", "draft", "source_candidate")]
    source_paths = payload.get("source_paths")
    if isinstance(source_paths, list):
        values.extend(source_paths)
    return any(normalize_review_path(str(value or "")) in {expected, absolute} for value in values)


def _unresolved_review_notes(payload: dict[str, object]) -> list[str]:
    notes: list[str] = []
    conclusion = str(payload.get("conclusion") or "").strip().lower()
    if conclusion in {"pass_with_notes", "revise_required", "reject"}:
        notes.append(f"conclusion={conclusion}")
    for key in ("blocking_issues", "revision_actions"):
        if isinstance(payload.get(key), list) and payload.get(key):
            notes.append(key)
    warnings = payload.get("warnings")
    if isinstance(warnings, list) and any(_warning_requires_followup(item) for item in warnings):
        notes.append("warnings")
    _append_style_notes(notes, payload)
    _append_literary_contract_notes(notes, payload)
    return notes


def _append_style_notes(notes: list[str], payload: dict[str, object]) -> None:
    style = _mapping(payload, "style_adherence")
    status = _status(style)
    if status in {"pass_with_notes", "revise_required", "reject"}:
        notes.append(f"style_adherence.status={status}")
    for key in ("deviations", "revision_actions"):
        if isinstance(style.get(key), list) and style.get(key):
            notes.append(f"style_adherence.{key}")


def _append_literary_contract_notes(notes: list[str], payload: dict[str, object]) -> None:
    contracts = (
        ("word_budget_adherence", {"pass", "not_required"}, "narrative_load_satisfied"),
        ("reader_experience_adherence", {"pass", "not_required"}, "reader_promise_satisfied"),
        ("narrative_rhythm_adherence", {"pass", "not_applicable"}, "rhythm_executed"),
    )
    for key, accepted, flag in contracts:
        value = _mapping(payload, key)
        status = _status(value)
        if status not in {"", *accepted}:
            notes.append(f"{key}.status={status}")
        if status in accepted and value.get(flag) is False:
            notes.append(f"{key}.{flag}=false")
    rhythm = _mapping(payload, "narrative_rhythm_adherence")
    if _status(rhythm) in {"pass", "not_applicable"} and rhythm.get("bridge_executed") is False:
        notes.append("narrative_rhythm_adherence.bridge_executed=false")
    canon_ok, canon_status, canon_message = _canon_writeback_review_gate(_mapping(payload, "canon_writeback"))
    if not canon_ok:
        notes.append(f"canon_writeback.{canon_status}:{canon_message}")
    revision_ok, revision_status, revision_message = _revision_integrity_review_gate(_mapping(payload, "revision_integrity"))
    if not revision_ok:
        notes.append(f"revision_integrity.{revision_status}:{revision_message}")


def _warning_requires_followup(value: object) -> bool:
    if not isinstance(value, dict):
        return True
    if value.get("blocks_pass") is False:
        return False
    severity = str(value.get("severity") or "").strip().lower()
    resolution = str(value.get("resolution") or "").strip().lower()
    if severity not in {"info", "low", "note"}:
        return True
    if resolution in {"noted_below_threshold", "waived", "not_required", "non_blocking", "non-blocking"}:
        return False
    text = " ".join(str(value.get(key) or "") for key in ("message", "detail", "description")).lower()
    markers = ("不作为阻塞", "不阻塞", "低于阈值", "已登记豁免", "not blocking", "below threshold", "waived")
    return not any(marker in text for marker in markers)


def _human_decision_notes(payload: dict[str, object]) -> list[str]:
    notes: list[str] = []
    for key in ("blocking_issues", "warnings", "revision_actions", "style_notes"):
        value = payload.get(key)
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict):
                continue
            resolution = str(item.get("resolution") or item.get("status") or "").strip().lower()
            if resolution in {"needs_human_review", "human_decision_required", "pending_user_decision"} or (item.get("blocks_pass") is True and "human" in resolution):
                item_id = str(item.get("id") or key)
                description = str(item.get("description") or item.get("note") or "requires a formal decision")
                notes.append(f"{item_id}: {description}")
    return notes


def _revision_integrity_review_gate(value: dict[str, object]) -> tuple[bool, str, str]:
    if not value:
        return False, "missing", "revision_integrity object is missing"
    status = _status(value)
    if status not in {"pass", "not_applicable"}:
        return False, status or "missing_status", f"status={status or 'missing'}"
    if value.get("anti_evasion_checked") is not True:
        return False, "unchecked", "anti_evasion_checked must be true"
    if not empty_unresolved(value.get("evasion_risks_unresolved")):
        return False, "unresolved", "evasion_risks_unresolved must be empty/false"
    return True, status, "revision integrity reviewed"


def _canon_writeback_review_gate(value: dict[str, object]) -> tuple[bool, str, str]:
    if not value:
        return False, "missing", "canon_writeback object is missing"
    status = _status(value)
    change = canon_change_value(value.get("canon_change"))
    if status not in {"pass", "not_required", "pending_canon_evolve", "unknown"}:
        return False, status or "missing_status", f"status={status or 'missing'}"
    if change is False:
        reason = str(value.get("no_canon_change_reason") or "").strip()
        if not reason:
            return False, "missing_reason", "canon_change=false requires no_canon_change_reason"
        return True, "no_change", "canon no-change declaration is explicit"
    if change in {True, "unknown"}:
        status = "needs_canon_evolve" if change is True else "unknown"
        return True, status, "canon writeback requires canon-evolve route gate"
    return False, "missing_change", "canon_change must be true, false, or unknown"
