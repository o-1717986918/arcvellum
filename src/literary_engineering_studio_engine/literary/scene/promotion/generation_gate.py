"""Formal prose-generation provenance gate."""

from __future__ import annotations

from pathlib import Path

from ....agent_tasks import agent_task_completion_status
from ....context_broker import context_trace_status
from ....creative_quality import creative_quality_profile_exists, load_creative_quality_profile
from ....new_character_register import new_character_register_issues
from ....narrative_rhythm import narrative_rhythm_contract
from ....reader_experience import reader_experience_adherence_for_body
from ...style.anti_ai import style_lint_gate
from ...style.punctuation import lint_punctuation
from .gate_support import (
    candidate_body,
    canon_change_value,
    canon_writeback_declaration,
    empty_unresolved,
    is_revision_candidate_path,
    normalize_review_path,
    read_json,
    read_text,
    relative_path,
)
from .style_gate import generation_style_snapshot_errors


def candidate_language_gate(
    body: str,
    *,
    profile: dict[str, object] | None = None,
    scope: str = "",
) -> dict[str, object]:
    """Return the Engine-owned language-quality gate for a prose candidate."""

    punctuation = [
        {
            "rule": issue.rule,
            "severity": issue.severity,
            "message": issue.message,
            "sample": issue.sample,
        }
        for issue in lint_punctuation(body, profile=profile, scope=scope)
        if issue.severity.strip().lower() not in {"", "low"}
    ]
    style = style_lint_gate(body, profile=profile, scope=scope)
    blocking = [
        {"category": "punctuation", **item}
        for item in punctuation
    ]
    style_rows = style.get("blocking")
    if isinstance(style_rows, list):
        blocking.extend(
            {"category": "style", **item}
            for item in style_rows
            if isinstance(item, dict)
        )
    return {
        "status": "blocking" if blocking else "pass",
        "blocking": blocking,
        "punctuation": punctuation,
        "style": style,
    }


def candidate_generation_gate(root: Path, scene_id: str, candidate_path: Path) -> dict[str, object]:
    """Check that a prose candidate came from the formal CLI sidecar handoff."""

    paths = _generation_paths(root, candidate_path)
    completion = agent_task_completion_status(paths["task"], root=root)
    gate: dict[str, object] = {
        "required": True,
        "candidate": paths["candidate_rel"],
        "manifest": relative_path(paths["manifest"], root),
        "prompt_manifest": relative_path(paths["prompt"], root),
        "agent_tasks": relative_path(paths["task"], root),
        "agent_task_completion": completion,
        "status": "missing",
        "message": "candidate generation provenance is missing",
        "missing": [],
        "invalid": [],
        "revision_candidate": is_revision_candidate_path(root, candidate_path),
    }
    missing = _missing_generation_files(root, candidate_path, paths)
    invalid = _generation_envelope_issues(root, scene_id, paths, completion)
    payload = read_json(paths["manifest"])
    if paths["manifest"].exists() and not payload:
        invalid.append("manifest is not valid JSON")
    if payload:
        invalid.extend(_generation_manifest_issues(root, scene_id, candidate_path, gate, payload, paths))
    return _finish_generation_gate(gate, missing, invalid)


def _generation_paths(root: Path, candidate_path: Path) -> dict[str, object]:
    return {
        "candidate_rel": relative_path(candidate_path, root),
        "manifest": candidate_path.with_suffix(".json"),
        "prompt": candidate_path.with_suffix(".prompt.json"),
        "task": candidate_path.with_suffix(".agent_tasks.md"),
    }


def _missing_generation_files(root: Path, candidate_path: Path, paths: dict[str, object]) -> list[str]:
    candidates = (candidate_path, paths["manifest"], paths["prompt"], paths["task"])
    return [relative_path(path, root) for path in candidates if not path.exists()]


def _generation_envelope_issues(
    root: Path,
    scene_id: str,
    paths: dict[str, object],
    completion: dict[str, object],
) -> list[str]:
    issues: list[str] = []
    if paths["task"].exists() and completion.get("complete") is not True:
        issues.append(f"generation agent task incomplete: {completion.get('message')}")
    trace = context_trace_status(root, scene_id)
    if not trace.passed:
        issues.append(f"context trace is stale: {trace.message}")
    return issues


def _generation_manifest_issues(
    root: Path,
    scene_id: str,
    candidate_path: Path,
    gate: dict[str, object],
    payload: dict[str, object],
    paths: dict[str, object],
) -> list[str]:
    issues = _generation_identity_issues(payload, str(paths["candidate_rel"]))
    issues.extend(_generation_contract_issues(root, candidate_path, gate, payload, paths))
    issues.extend(new_character_register_issues(payload, root, mode="generation"))
    prompt = read_json(paths["prompt"])
    standards = prompt.get("generation_standards") if isinstance(prompt.get("generation_standards"), dict) else {}
    issues.extend(generation_style_snapshot_errors(root, scene_id, candidate=payload, prompt=prompt))
    issues.extend(_generation_quality_issues(root, payload, standards))
    issues.extend(_generation_rhythm_reader_issues(root, scene_id, candidate_path, payload, standards))
    return issues


def _generation_identity_issues(payload: dict[str, object], candidate_rel: str) -> list[str]:
    issues: list[str] = []
    generated_by = str(payload.get("generated_by") or "").strip()
    provider = str(payload.get("provider") or "").strip()
    manifest_candidate = str(payload.get("candidate") or "").strip()
    if generated_by != "platform-agent":
        issues.append(f"generated_by={generated_by or 'missing'}")
    if str(payload.get("formal_contract_revision") or "").strip() >= "2026-07-23.3" and not str(payload.get("writer_session_id") or "").strip():
        issues.append("writer_session_id is required for current formal candidate contracts")
    if provider in {"dry-run", "http-chat"}:
        issues.append(f"legacy provider candidate: {provider}")
    if manifest_candidate and normalize_review_path(manifest_candidate) != normalize_review_path(candidate_rel):
        issues.append(f"manifest candidate mismatch: {manifest_candidate}")
    return issues


def _generation_contract_issues(
    root: Path,
    candidate_path: Path,
    gate: dict[str, object],
    payload: dict[str, object],
    paths: dict[str, object],
) -> list[str]:
    if gate["revision_candidate"]:
        return _revision_generation_contract_issues(payload)
    return _standard_generation_contract_issues(root, candidate_path, payload, paths)


def _revision_generation_contract_issues(payload: dict[str, object]) -> list[str]:
    issues = [] if payload.get("anti_evasion_protocol_applied") is True else ["anti_evasion_protocol_applied is not true"]
    if not empty_unresolved(payload.get("evasion_risks_unresolved")):
        issues.append("evasion_risks_unresolved is not clean")
    return issues


def _standard_generation_contract_issues(
    root: Path,
    candidate_path: Path,
    payload: dict[str, object],
    paths: dict[str, object],
) -> list[str]:
    issues: list[str] = []
    for key in ("style_generation_standard_applied", "hard_constraints_applied", "anti_evasion_protocol_applied"):
        if payload.get(key) is not True:
            issues.append(f"{key} is not true")
    if payload.get("narrative_rhythm_standard_applied") is not True:
        issues.append("narrative_rhythm_standard_applied is not true")
    for key in ("word_budget_standard_applied", "pass_with_notes_actions_applied"):
        if key not in payload or not isinstance(payload.get(key), bool):
            issues.append(f"{key} must be a boolean")
    if not str(payload.get("prompt_manifest") or "").strip() and not paths["prompt"].exists():
        issues.append("prompt_manifest is missing")
    canon_decl = canon_writeback_declaration(root, candidate_path)
    canon_change = canon_change_value(canon_decl.get("canon_change"))
    if canon_change is None:
        issues.append("canon_change declaration is missing")
    if canon_change is False and not str(canon_decl.get("no_canon_change_reason") or "").strip():
        issues.append("canon_change=false requires no_canon_change_reason")
    return issues


def _generation_quality_issues(
    root: Path,
    payload: dict[str, object],
    standards: dict[str, object],
) -> list[str]:
    if not creative_quality_profile_exists(root):
        return []
    current = str(load_creative_quality_profile(root).get("digest") or "")
    prompt_digest = str(standards.get("creative_quality_profile_digest") or "")
    candidate_digest = str(payload.get("creative_quality_profile_digest") or "")
    issues: list[str] = []
    if not prompt_digest:
        issues.append("prompt manifest missing creative_quality_profile_digest")
    elif prompt_digest != current:
        issues.append("prompt manifest creative quality profile is stale")
    if not candidate_digest:
        issues.append("candidate manifest missing creative_quality_profile_digest")
    elif candidate_digest != prompt_digest:
        issues.append("candidate manifest creative quality profile digest mismatch")
    return issues


def _generation_rhythm_reader_issues(
    root: Path,
    scene_id: str,
    candidate_path: Path,
    payload: dict[str, object],
    standards: dict[str, object],
) -> list[str]:
    rhythm = standards.get("narrative_rhythm_contract") if isinstance(standards, dict) else {}
    issues = _rhythm_contract_issues(root, scene_id, rhythm)
    issues.extend(_candidate_freshness_issues(root, scene_id, candidate_path))
    issues.extend(_reader_contract_issues(root, scene_id, candidate_path, payload, standards))
    return issues


def _rhythm_contract_issues(root: Path, scene_id: str, rhythm: object) -> list[str]:
    issues: list[str] = []
    if not isinstance(rhythm, dict) or rhythm.get("status") not in {"pass", "defaulted"}:
        issues.append("prompt manifest missing ready generation_standards.narrative_rhythm_contract")
    scene_path = root / "scenes" / f"{scene_id}.yaml"
    current_plan = str(narrative_rhythm_contract(root, scene_path).get("plan_digest") or "")
    prompt_plan = str(rhythm.get("plan_digest") or "") if isinstance(rhythm, dict) else ""
    if current_plan and prompt_plan != current_plan:
        issues.append("prompt manifest narrative rhythm plan is stale")
    return issues


def _candidate_freshness_issues(root: Path, scene_id: str, candidate_path: Path) -> list[str]:
    composition = root / "drafts" / "compositions" / f"{scene_id}_composition.json"
    if composition.is_file() and candidate_path.is_file() and candidate_path.stat().st_mtime_ns < composition.stat().st_mtime_ns:
        return ["candidate predates the current composition packet"]
    return []


def _reader_contract_issues(
    root: Path,
    scene_id: str,
    candidate_path: Path,
    payload: dict[str, object],
    standards: dict[str, object],
) -> list[str]:
    body = candidate_body(read_text(candidate_path)) if candidate_path.exists() else ""
    scene_path = root / "scenes" / f"{scene_id}.yaml"
    reader = reader_experience_adherence_for_body(root, scene_path, body)
    issues: list[str] = []
    if reader.get("status") != "not_required":
        standard = standards.get("reader_experience_contract") if isinstance(standards, dict) else {}
        if not isinstance(standard, dict) or standard.get("status") not in {"pass", "not_required"}:
            issues.append("prompt manifest missing ready generation_standards.reader_experience_contract")
        if not isinstance(payload.get("reader_experience_contract"), dict):
            issues.append("candidate manifest missing reader_experience_contract")
    return issues


def _finish_generation_gate(
    gate: dict[str, object],
    missing: list[str],
    invalid: list[str],
) -> dict[str, object]:
    if missing:
        gate.update(status="missing", message="formal candidate generation files are missing")
    elif invalid:
        gate.update(status="invalid", message="formal candidate generation provenance is invalid")
    else:
        gate.update(status="pass", message="formal candidate generation provenance passed")
    gate.update(missing=missing, invalid=invalid)
    return gate
