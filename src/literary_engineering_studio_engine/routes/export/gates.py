"""Deterministic delivery and approval Gates for export and release."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ...release_fingerprint import release_candidate_fingerprint
from ...literary.scene.promotion.historical_readiness import historical_scene_readiness
from ...task_paths import relative_path as _rel
from .evidence import approval_record_for_run, delivery_trace_hits, read_optional_json, to_int


ChapterGate = Callable[[Path, str], list[str]]


def export_release_state_gate_validation(
    root: Path,
    task: dict[str, object],
) -> tuple[list[str], list[str]]:
    current_state = str(task.get("current_state") or "")
    chapter_id = str(task.get("chapter_id") or task.get("target_id") or task.get("scene_id") or "chapter_0001")
    errors = _run_gates(root, chapter_id, GATES_BY_STATE.get(current_state, ()))
    notes: list[str] = []
    if current_state == "export-package" and not errors:
        notes.append("export package ready with no skipped scenes")
    if current_state == "publish-release" and not errors:
        notes.append("chapter published through approved release gate")
    return errors, notes


def _run_gates(root: Path, chapter_id: str, gates: tuple[ChapterGate, ...]) -> list[str]:
    errors: list[str] = []
    for gate in gates:
        errors.extend(gate(root, chapter_id))
    return errors


def chapter_workspace_gate_errors(root: Path, chapter_id: str) -> list[str]:
    json_path = root / "plot" / "chapters" / f"{chapter_id}.json"
    report_path = root / "drafts" / "chapters" / f"{chapter_id}.md"
    errors = [
        f"chapter workspace artifact missing: {_rel(path, root)}"
        for path in (json_path, report_path)
        if not path.exists()
    ]
    payload, error = read_optional_json(json_path)
    if error:
        errors.append(error)
        return errors
    _validate_workspace_summary(payload, errors)
    for scene in payload.get("scenes", []) if isinstance(payload.get("scenes"), list) else []:
        if isinstance(scene, dict):
            errors.extend(_workspace_scene_errors(root, scene))
    return errors


def _validate_workspace_summary(payload: dict[str, object], errors: list[str]) -> None:
    if payload.get("schema") != "literary-engineering-workbench/chapter-workspace/v0.1":
        errors.append("chapter workspace JSON has wrong or missing schema")
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    if to_int(summary.get("ready_count")) <= 0:
        errors.append("chapter workspace ready_count must be positive")
    if to_int(summary.get("blocked_count")) != 0:
        errors.append(f"chapter workspace blocked_count must be 0; got {summary.get('blocked_count')}")


def _workspace_scene_errors(root: Path, scene: dict[str, object]) -> list[str]:
    scene_id = str(scene.get("scene_id") or "") or "unknown"
    errors: list[str] = []
    historical = historical_scene_readiness(root, scene_id)
    if historical is not None:
        historical_status, historical_issues = historical
        if historical_status != "ready":
            errors.append(
                f"historically promoted chapter scene is not ready: {scene_id}: "
                + "; ".join(historical_issues)
            )
        if scene.get("status") != historical_status:
            errors.append(
                f"chapter workspace status does not match sealed promotion: {scene_id}"
            )
        return errors
    if scene.get("status") != "ready":
        errors.append(f"chapter scene must be ready: {scene_id}")
    if scene.get("agent_review_conclusion") != "pass" or scene.get("agent_review_schema_status") != "pass":
        errors.append(f"chapter scene lacks clean platform AgentReview: {scene_id}")
    if scene.get("agent_review_source_match") is not True:
        errors.append(f"chapter scene AgentReview does not cite exact draft/candidate: {scene_id}")
    if scene.get("agent_review_unresolved_notes"):
        errors.append(f"chapter scene has unresolved AgentReview notes: {scene_id}")
    if scene.get("flow_gate_issues") or scene.get("readiness_issues"):
        errors.append(f"chapter scene has unresolved flow/readiness gate issues: {scene_id}")
    return errors


def export_package_gate_errors(root: Path, chapter_id: str) -> list[str]:
    manifest_path = root / "exports" / chapter_id / "export_manifest.json"
    payload, error = read_optional_json(manifest_path)
    if error:
        return [error]
    errors = _export_manifest_errors(payload)
    outputs = payload.get("outputs") if isinstance(payload.get("outputs"), dict) else {}
    errors.extend(_delivery_output_errors(root, outputs))
    errors.extend(_docx_output_errors(root, outputs))
    return errors


def _export_manifest_errors(payload: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema") != "literary-engineering-workbench/export-package/v0.1":
        errors.append("export_manifest.json has wrong or missing schema")
    if payload.get("include_blocked") is True:
        errors.append("export package must not use include_blocked for formal delivery")
    requested = {str(item).strip().lower() for item in payload.get("requested_formats", []) if str(item).strip()}
    if not {"md", "docx"}.issubset(requested):
        errors.append("formal export package must include requested_formats md and docx")
    skipped = payload.get("skipped_scenes") if isinstance(payload.get("skipped_scenes"), list) else []
    if skipped:
        errors.append(f"export package skipped_scenes must be empty; got {len(skipped)}")
    return errors


def _delivery_output_errors(root: Path, outputs: dict[str, object]) -> list[str]:
    errors: list[str] = []
    for key in ("novel", "screenplay", "video_prompt_pack"):
        rel = str(outputs.get(key) or "")
        if not rel:
            errors.append(f"export output missing from manifest: {key}")
        elif not (root / rel).exists():
            errors.append(f"export output file missing: {rel}")
        else:
            hits = delivery_trace_hits(root / rel)
            if hits:
                errors.append(f"export output contains workbench traces in {rel}: {', '.join(hits[:5])}")
    return errors


def _docx_output_errors(root: Path, outputs: dict[str, object]) -> list[str]:
    groups = (
        ("DOCX", outputs.get("docx")),
        ("DOCX layout", outputs.get("docx_layout_plans")),
        ("DOCX inspection", outputs.get("docx_inspections")),
    )
    errors: list[str] = []
    for key in ("novel", "screenplay", "video_prompt_pack"):
        for label, raw_values in groups:
            values = raw_values if isinstance(raw_values, dict) else {}
            rel = str(values.get(key) or "")
            if not rel or not (root / rel).is_file():
                errors.append(f"{label} output missing: {key} -> {rel or 'missing'}")
    return errors


def release_approval_gate_errors(root: Path, chapter_id: str) -> list[str]:
    run_id = f"release-{chapter_id}"
    approval = approval_record_for_run(root, run_id)
    fingerprint = release_candidate_fingerprint(root, chapter_id)
    if (
        str(approval.get("decision") or "") == "approve"
        and fingerprint
        and str(approval.get("subject_sha256") or "").lower() == fingerprint
    ):
        return []
    return [f"release approval missing, stale, or not approve for current export manifest and run_id {run_id}"]


def publish_release_gate_errors(root: Path, chapter_id: str) -> list[str]:
    release_dir = root / "releases" / chapter_id / "formal-release"
    manifest = release_dir / "publish_manifest.json"
    latest = root / "releases" / chapter_id / "latest.json"
    payload, error = read_optional_json(manifest)
    if error:
        return [error]
    errors = _publish_manifest_errors(payload)
    errors.extend(_published_output_errors(root, payload))
    latest_payload, latest_error = read_optional_json(latest)
    if latest_error:
        errors.append(latest_error)
    elif latest_payload.get("manifest") != _rel(manifest, root):
        errors.append("latest.json does not point to formal-release publish_manifest.json")
    return errors


def _publish_manifest_errors(payload: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema") != "literary-engineering-workbench/publish-chapter/v0.1":
        errors.append("publish_manifest.json has wrong or missing schema")
    if payload.get("status") != "published":
        errors.append(f"publish status must be published; got {payload.get('status') or 'missing'}")
    approval = payload.get("approval") if isinstance(payload.get("approval"), dict) else {}
    if approval.get("decision") != "approve":
        errors.append("publish manifest approval must be an approve record")
    fingerprint = str(payload.get("approved_export_fingerprint") or "").strip().lower()
    if not fingerprint or str(approval.get("subject_sha256") or "").strip().lower() != fingerprint:
        errors.append("publish manifest approval does not match the approved export fingerprint")
    return errors


def _published_output_errors(root: Path, payload: dict[str, object]) -> list[str]:
    outputs = payload.get("published_outputs") if isinstance(payload.get("published_outputs"), dict) else {}
    errors = [] if outputs else ["publish manifest must contain published_outputs"]
    for key, rel in outputs.items():
        if not (root / str(rel)).exists():
            errors.append(f"published output missing: {key} -> {rel}")
    return errors


GATES_BY_STATE: dict[str, tuple[ChapterGate, ...]] = {
    "chapter-workspace": (chapter_workspace_gate_errors,),
    "export-package": (chapter_workspace_gate_errors, export_package_gate_errors),
    "release-approval": (
        chapter_workspace_gate_errors,
        export_package_gate_errors,
        release_approval_gate_errors,
    ),
    "publish-release": (
        chapter_workspace_gate_errors,
        export_package_gate_errors,
        release_approval_gate_errors,
        publish_release_gate_errors,
    ),
}


__all__ = [
    "chapter_workspace_gate_errors",
    "export_package_gate_errors",
    "export_release_state_gate_validation",
    "publish_release_gate_errors",
    "release_approval_gate_errors",
]
