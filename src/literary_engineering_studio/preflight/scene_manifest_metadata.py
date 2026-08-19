"""Bind Agent scene judgments to deterministic Studio-owned metadata."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from ..contracts import TaskPackage
from ..sandbox import SandboxManifest
from .style_snapshot import prompt_style_snapshot


ReadObject = Callable[[Path], dict[str, Any] | None]
WriteFields = Callable[[Path, str, dict[str, Any], dict[str, Any], str], list[dict[str, str]]]
SessionIdentity = Callable[[TaskPackage, str], str]


_NON_ANTI_EVASION_ISSUE_CODES = frozenset({"candidate-word-budget-invalid"})
_NON_ANTI_EVASION_ISSUE_MARKERS = (
    "重复谓语",
    "字数",
    "错别字",
    "逗号密度",
    "破折号密度",
    "比喻密度",
    "抽象总结",
)
_ANTI_EVASION_ISSUE_MARKERS = (
    "反规避",
    "机械转折",
    "显式转折",
    "换皮",
    "对照",
    "对比",
    "contrast",
    "evasion",
    "transition",
)


def canonicalize_scene_revision_manifest(
    task: TaskPackage,
    sandbox: SandboxManifest,
    *,
    read_object: ReadObject,
    session_identity: SessionIdentity,
) -> list[dict[str, str]]:
    if task.current_state not in {"candidate-revision", "static-revision"}:
        return []
    candidate_rel, manifest_rel, prompt_rel, report_rel = _revision_paths(task)
    if not candidate_rel or not manifest_rel:
        return []
    candidate_path = sandbox.workspace / Path(candidate_rel)
    manifest_path = sandbox.workspace / Path(manifest_rel)
    payload = read_object(manifest_path)
    if payload is None or not candidate_path.is_file():
        return []
    prompt = read_object(sandbox.workspace / Path(prompt_rel)) or {}
    standards = prompt.get("generation_standards") if isinstance(prompt.get("generation_standards"), dict) else {}
    source_rows = prompt.get("sources") if isinstance(prompt.get("sources"), list) else []
    expected = _revision_machine_fields(
        task,
        sandbox,
        candidate_rel,
        candidate_path,
        prompt_rel,
        report_rel,
        source_rows,
        standards,
        session_identity,
    )
    changes = _canonicalize_revision_payload(payload, expected, standards)
    if not changes:
        return []
    _write_json(manifest_path, payload)
    return [{"path": manifest_rel, **change} for change in changes]


def _canonicalize_revision_payload(
    payload: dict[str, Any],
    expected: dict[str, Any],
    standards: dict[str, Any],
) -> list[dict[str, str]]:
    changes = [
        {"field": field, "reason": "bound deterministic exact-source revision metadata"}
        for field in _apply_fields(payload, expected)
    ]
    removed_rows = _remove_misclassified_anti_evasion_rows(payload)
    if removed_rows:
        changes.append(
            {
                "field": "anti_evasion_rows",
                "reason": "removed deterministic non-anti-evasion repairs from the evidence table",
            }
        )
    if _normalize_anti_evasion_boolean_fields(payload):
        changes.append(
            {
                "field": "anti_evasion_rows",
                "reason": "normalized unambiguous boolean transport values",
            }
        )
    if _ensure_anti_evasion_not_applicable_reason(payload, standards):
        changes.append(
            {
                "field": "anti_evasion_not_applicable_reason",
                "reason": "derived from protected anti-evasion requirement flag",
            }
        )
    return changes


def _normalize_anti_evasion_boolean_fields(payload: dict[str, Any]) -> bool:
    rows = payload.get("anti_evasion_rows")
    if not isinstance(rows, list):
        return False
    changed = False
    for row in rows:
        if not isinstance(row, dict):
            continue
        for field in ("still_uses_explicit_transition", "suspected_rephrase"):
            normalized = _transport_bool(row.get(field))
            if normalized is not None and row.get(field) is not normalized:
                row[field] = normalized
                changed = True
    return changed


def _transport_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().casefold()
    if normalized in {"true", "yes", "y", "1", "是"}:
        return True
    if normalized in {"false", "no", "n", "0", "否"}:
        return False
    return None


def _ensure_anti_evasion_not_applicable_reason(
    payload: dict[str, Any],
    standards: dict[str, Any],
) -> bool:
    rows = payload.get("anti_evasion_rows")
    if rows not in (None, []) or standards.get("anti_evasion_rows_required") is not False:
        return False
    if str(payload.get("anti_evasion_not_applicable_reason") or "").strip():
        return False
    payload["anti_evasion_not_applicable_reason"] = (
        "Protected source lint found no mechanical contrast or evasion row requirement; "
        "no additional semantic transition risk was recorded by the revising Agent."
    )
    return True


def _remove_misclassified_anti_evasion_rows(payload: dict[str, Any]) -> list[str]:
    rows = payload.get("anti_evasion_rows")
    if not isinstance(rows, list):
        return []
    kept: list[object] = []
    removed: list[str] = []
    evidence_pairs: set[tuple[str, str]] = set()
    for row in rows:
        issue = str(row.get("issue") or "").strip() if isinstance(row, dict) else ""
        if _is_non_anti_evasion_issue(issue):
            removed.append(issue)
            continue
        pair = _evidence_pair(row)
        if pair is not None and pair in evidence_pairs:
            removed.append(f"duplicate evidence: {issue}")
            continue
        if pair is not None:
            evidence_pairs.add(pair)
        kept.append(row)
    if removed:
        payload["anti_evasion_rows"] = kept
    return removed


def _is_non_anti_evasion_issue(issue: str) -> bool:
    normalized = issue.casefold()
    if any(marker in normalized for marker in _ANTI_EVASION_ISSUE_MARKERS):
        return False
    has_code = any(
        normalized == code
        or normalized.startswith(f"{code}:")
        or normalized.startswith(f"{code}：")
        or normalized.startswith(f"{code} ")
        for code in _NON_ANTI_EVASION_ISSUE_CODES
    )
    return has_code or any(marker in normalized for marker in _NON_ANTI_EVASION_ISSUE_MARKERS)


def _evidence_pair(row: object) -> tuple[str, str] | None:
    if not isinstance(row, dict):
        return None
    source = str(row.get("source_excerpt") or "").strip()
    revised = str(row.get("revised_excerpt") or "").strip()
    return (source, revised) if source and revised else None


def _revision_paths(task: TaskPackage) -> tuple[str, str, str, str]:
    candidate = _revision_candidate(task)
    manifest = next(
        (item for item in task.expected_outputs if item.endswith("_revision.json")), ""
    )
    prompt = next(
        (item for item in task.expected_outputs if item.endswith("_revision.prompt.json")),
        _sibling_prompt(candidate),
    )
    report = next(
        (item for item in task.expected_outputs if item.endswith("_revision_report.md")), ""
    )
    return candidate, manifest, prompt, report


def _revision_machine_fields(
    task: TaskPackage,
    sandbox: SandboxManifest,
    candidate_rel: str,
    candidate_path: Path,
    prompt_rel: str,
    report_rel: str,
    source_rows: list[object],
    standards: dict[str, Any],
    session_identity: SessionIdentity,
) -> dict[str, Any]:
    return {
        "schema": "literary-engineering-workbench/scene-revision/v0.1",
        "scene_id": str(task.payload.get("scene_id") or task.scene_id or "").strip(),
        "source_candidate": str(task.payload.get("revision_source") or "").replace("\\", "/").strip(),
        "source_candidate_sha256": str(task.payload.get("candidate_sha256_before_revision") or "").strip().lower(),
        "candidate": candidate_rel,
        "candidate_sha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
        "report": report_rel,
        "source_paths": _prompt_source_paths(source_rows),
        "prompt_manifest": prompt_rel,
        "style_mount_snapshot": prompt_style_snapshot(sandbox.workspace / Path(prompt_rel)),
        "creative_quality_profile_digest": str(standards.get("creative_quality_profile_digest") or "").strip(),
        "reader_experience_contract": _dict_value(standards, "reader_experience_contract"),
        "narrative_rhythm_contract": _dict_value(standards, "narrative_rhythm_contract"),
        "anti_evasion_protocol_applied": True,
        "ready_for_review": False,
        "generated_by": "platform-agent",
        "provider": "studio-agent-runtime",
        "formal_contract_revision": str(task.payload.get("task_contract_revision") or "2026-07-24.8"),
        "writer_session_id": session_identity(task, "writer"),
    }


def canonicalize_scene_candidate_manifest(
    task: TaskPackage,
    sandbox: SandboxManifest,
    *,
    write_machine_fields: WriteFields,
    session_identity: SessionIdentity,
) -> list[dict[str, str]]:
    if task.current_state not in {"candidate-generation-provenance", "generation-agent-task"}:
        return []
    candidate_rel = _candidate_path(task)
    if not candidate_rel:
        return []
    manifest_rel = _sibling_json(candidate_rel)
    manifest_path = sandbox.workspace / Path(manifest_rel)
    payload = _read_json(manifest_path)
    if payload is None:
        return []
    scene_id = str(task.payload.get("scene_id") or task.scene_id or "").strip()
    prompt_rel = _sibling_prompt(candidate_rel)
    fields: dict[str, Any] = {
        "schema": "literary-engineering-workbench/scene-candidate/v1",
        "scene_id": scene_id,
        "candidate": candidate_rel,
        "prompt_manifest": prompt_rel,
        "generated_by": "platform-agent",
        "provider": "studio-agent-runtime",
        "formal_contract_revision": str(task.payload.get("task_contract_revision") or "2026-07-24.8"),
        "writer_session_id": session_identity(task, "writer"),
        "style_mount_snapshot": prompt_style_snapshot(sandbox.workspace / Path(prompt_rel)),
        "style_generation_standard_applied": True,
        "hard_constraints_applied": True,
        "anti_evasion_protocol_applied": True,
        "narrative_rhythm_standard_applied": True,
    }
    if not isinstance(payload.get("word_budget_standard_applied"), bool):
        fields["word_budget_standard_applied"] = False
    if not isinstance(payload.get("pass_with_notes_actions_applied"), bool):
        fields["pass_with_notes_actions_applied"] = False
    changes = write_machine_fields(
        manifest_path, manifest_rel, payload, fields, "scene-candidate-manifest"
    )
    changes.extend(_ensure_character_register(task, sandbox, manifest_rel, payload))
    changes.extend(_copy_prompt_standards(sandbox, manifest_rel, prompt_rel, payload))
    if changes:
        _write_json(manifest_path, payload)
    return changes


def _ensure_character_register(
    task: TaskPackage,
    sandbox: SandboxManifest,
    manifest_rel: str,
    payload: dict[str, Any],
) -> list[dict[str, str]]:
    if isinstance(payload.get("new_character_register"), dict):
        return []
    introduced: list[dict[str, object]] = []
    ready = True
    requirements = task.payload.get("scene_character_assets")
    for item in requirements if isinstance(requirements, list) else []:
        if not isinstance(item, dict):
            continue
        candidate_path = str(item.get("candidate_path") or "").replace("\\", "/").strip()
        if candidate_path and not (sandbox.workspace / Path(candidate_path)).is_file():
            ready = False
        introduced.append(_character_row(item, candidate_path))
    payload["new_character_register"] = {
        "schema": "literary-engineering-workbench/new-character-register/v0.1",
        "status": "candidates_ready" if introduced and ready else ("needs_candidate" if introduced else "none"),
        "introduced": introduced,
        "ephemeral_waivers": [],
        "blocking_issues": [] if ready else ["declared scene character candidate is missing"],
    }
    return [{"path": manifest_rel, "field": "new_character_register", "reason": "normalized deterministic scene-character contract"}]


def _copy_prompt_standards(
    sandbox: SandboxManifest,
    manifest_rel: str,
    prompt_rel: str,
    payload: dict[str, Any],
) -> list[dict[str, str]]:
    prompt = _read_json(sandbox.workspace / Path(prompt_rel)) or {}
    standards = prompt.get("generation_standards") if isinstance(prompt.get("generation_standards"), dict) else {}
    sources = {
        "creative_quality_profile_digest": standards.get("creative_quality_profile_digest"),
        "reader_experience_contract": standards.get("reader_experience_contract"),
        "narrative_rhythm_contract": standards.get("narrative_rhythm_contract"),
    }
    expected = {
        field: value
        for field, value in sources.items()
        if value is not None and value != "" and isinstance(value, (str, dict))
    }
    return [
        {"path": manifest_rel, "field": field, "reason": "copied from protected prompt manifest"}
        for field in _apply_fields(payload, expected)
    ]


def _revision_candidate(task: TaskPackage) -> str:
    candidate = str(task.payload.get("candidate") or "").replace("\\", "/").strip()
    return candidate or next(
        (item for item in task.expected_outputs if item.endswith("_revision.md") and "report" not in item), ""
    )


def _candidate_path(task: TaskPackage) -> str:
    candidate = str(task.payload.get("candidate") or "").replace("\\", "/").strip()
    return candidate or next(
        (
            item for item in task.expected_outputs
            if item.endswith(".md") and "agent_tasks" not in item and "prompt" not in item
        ),
        "",
    )


def _prompt_source_paths(rows: list[object]) -> list[str]:
    return [
        str(item.get("path") or "").replace("\\", "/").strip()
        for item in rows if isinstance(item, dict) and str(item.get("path") or "").strip()
    ]


def _character_row(item: dict[str, Any], candidate_path: str) -> dict[str, object]:
    return {
        "name": str(item.get("name") or item.get("candidate_id") or "").strip(),
        "character_id": str(item.get("candidate_id") or "").strip(),
        "scene_function": "declared scene participant",
        "persistence": "named",
        "already_in_characters": False,
        "formal_character_path": str(item.get("formal_character_path") or "").strip(),
        "candidate_path": candidate_path,
        "review_path": "",
        "approval_run_id": "",
        "promotion_manifest": "",
        "waiver_reason": "",
    }


def _dict_value(value: dict[str, Any], key: str) -> dict[str, Any]:
    nested = value.get(key)
    return nested if isinstance(nested, dict) else {}


def _apply_fields(payload: dict[str, Any], fields: dict[str, Any]) -> list[str]:
    changed = []
    for field, value in fields.items():
        if payload.get(field) != value:
            payload[field] = value
            changed.append(field)
    return changed


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sibling_json(candidate: str) -> str:
    return candidate[:-3] + ".json" if candidate.endswith(".md") else candidate + ".json"


def _sibling_prompt(candidate: str) -> str:
    return candidate[:-3] + ".prompt.json" if candidate.endswith(".md") else candidate + ".prompt.json"


__all__ = ["canonicalize_scene_candidate_manifest", "canonicalize_scene_revision_manifest"]
