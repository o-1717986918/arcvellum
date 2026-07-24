"""Formal task blueprint and Gate logic for chapter export and release.

This route only publishes delivery artifacts after a reviewed chapter workspace,
a clean export package, and a digest-bound release approval are present.
"""

from __future__ import annotations

import json
from pathlib import Path
import re

from ...release_fingerprint import release_candidate_fingerprint
from ...task_paths import (
    TASK_SCHEMA,
    normalize_relative_path as _normalize_rel,
    now as _now,
    relative_path as _rel,
    task_id as _task_id,
)
def _build_export_release_task_payload(root: Path, route: str, state: dict[str, object]) -> dict[str, object]:
    chapter_id = str(state.get("chapter_id") or state.get("target_id") or "chapter_0001")
    current_state = str(state.get("current_step") or "")
    next_action = str(state.get("next_action") or "")
    blueprint = _export_release_blueprint_for_state(root, chapter_id, current_state, next_action)
    task_id = _task_id(route, chapter_id, current_state)
    expected_outputs = _unique([_normalize_rel(item) for item in blueprint["expected_outputs"]])
    source_paths = _unique([_normalize_rel(item) for item in blueprint["source_paths"]])
    now = _now()
    return {
        "schema": TASK_SCHEMA,
        "task_id": task_id,
        "status": "issued",
        "created_at": now,
        "route": route,
        "scene_id": chapter_id,
        "target_id": chapter_id,
        "chapter_id": chapter_id,
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
                "references/file-format-export.md",
                "docs/implementation/phase7-chapter-pipeline.md",
                "docs/implementation/phase9-export-package.md",
                "docs/implementation/phase21-publish-chain.md",
            ],
        ),
        "source_paths": source_paths,
        "context_trace": blueprint.get("context_trace", ""),
        "hard_constraints": blueprint["hard_constraints"],
        "style_constraints": blueprint["style_constraints"],
        "word_count_target": blueprint.get("word_count_target", 0),
        "word_count_min": 0,
        "word_count_max": 0,
        "expected_outputs": expected_outputs,
        "submission_command": f"python -m literary_engineering_studio_engine task-submit <project> --task-id {task_id} --from <artifact>",
        "completion_command": f"python -m literary_engineering_studio_engine task-complete <project> --task-id {task_id}",
        "validation_gates": blueprint["validation_gates"],
        "forbidden_shortcuts": [
            "Do not use --include-blocked, --allow-unapproved, or custom export scripts for formal delivery.",
            "Do not export chapters with non-ready scenes, unresolved review notes, pending sidecars, skipped scenes, or workflow traces.",
            "Do not include scene ids, canon notes, review text, state patches, AGENT_TASK markers, or writeback candidates in final delivery files.",
            "Do not publish without a human approve record matching the release run id.",
            "Do not treat this task as complete until task-submit and task-complete have succeeded.",
        ],
        "next_allowed_states": blueprint["next_allowed_states"],
    }

def _export_release_blueprint_for_state(root: Path, chapter_id: str, current_state: str, next_action: str) -> dict[str, object]:
    _ = root
    approval_run_id = f"release-{chapter_id}"
    release_dir = f"releases/{chapter_id}/formal-release"
    table: dict[str, dict[str, object]] = {
        "chapter-workspace": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.export-release.chapter-workspace.v1",
            "command": f"python -m literary_engineering_studio_engine chapter-workspace <project> --chapter-id {chapter_id}",
            "source_paths": ["scenes", "drafts/scenes", "reviews", "reviews/agent", "branches", "drafts/compositions", "characters/state_patches"],
            "expected_outputs": [f"drafts/chapters/{chapter_id}.md", f"plot/chapters/{chapter_id}.json"],
            "hard_constraints": [
                "Rebuild or verify chapter workspace immediately before export.",
                "Every scene must be ready with formal flow gates, static review pass, exact-candidate AgentReview pass, and no unresolved notes.",
            ],
            "style_constraints": ["Final body extraction must exclude workflow traces, canon notes, state patches, review notes, and scene ids."],
            "validation_gates": ["chapter workspace exists", "blocked_count is 0", "ready_count > 0"],
            "next_allowed_states": ["export-package"],
        },
        "export-package": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.export-release.package.v1",
            "command": f"python -m literary_engineering_studio_engine export-package <project> --chapter-id {chapter_id} --formats md,docx",
            "source_paths": [f"plot/chapters/{chapter_id}.json", f"drafts/chapters/{chapter_id}.md", "drafts/scenes", "reviews/agent"],
            "expected_outputs": [
                f"exports/{chapter_id}/export_manifest.json",
                f"exports/{chapter_id}/{chapter_id}_novel.md",
                f"exports/{chapter_id}/{chapter_id}_screenplay.md",
                f"exports/{chapter_id}/{chapter_id}_video_prompt_pack.md",
                f"exports/{chapter_id}/{chapter_id}_novel.docx",
                f"exports/{chapter_id}/{chapter_id}_novel.layout.json",
                f"exports/{chapter_id}/{chapter_id}_novel.inspection.json",
                f"exports/{chapter_id}/{chapter_id}_screenplay.docx",
                f"exports/{chapter_id}/{chapter_id}_screenplay.layout.json",
                f"exports/{chapter_id}/{chapter_id}_screenplay.inspection.json",
                f"exports/{chapter_id}/{chapter_id}_video_prompt_pack.docx",
                f"exports/{chapter_id}/{chapter_id}_video_prompt_pack.layout.json",
                f"exports/{chapter_id}/{chapter_id}_video_prompt_pack.inspection.json",
            ],
            "hard_constraints": [
                "Do not use --include-blocked in formal Skill-host work.",
                "Export manifest must have zero skipped scenes and include_blocked=false.",
                "Final outputs must filter scene ids, canon notes, review notes, state patches, AGENT_TASK markers, and writeback candidates.",
            ],
            "style_constraints": ["Normalize punctuation for delivery; maintain Chinese quote standard and no raw workbench traces."],
            "validation_gates": ["export manifest exists", "skipped_scenes is empty", "include_blocked is false", "delivery outputs exist"],
            "next_allowed_states": ["release-approval"],
        },
        "release-approval": {
            "task_type": "human-approval-boundary",
            "prompt_asset_id": "route.export-release.approval.v1",
            "command": f"Ask the user whether to approve chapter `{chapter_id}` for release; record approve decision with run_id `{approval_run_id}`.",
            "source_paths": [f"exports/{chapter_id}/export_manifest.json", f"exports/{chapter_id}/{chapter_id}_novel.md", "workflow/approvals/index.jsonl"],
            "expected_outputs": ["workflow/approvals/index.jsonl"],
            "hard_constraints": [
                "The executing Worker must not self-approve release publication. Approval may come from the user or a separately identified Creative Steward when the active DelegationPolicy explicitly delegates release.",
                "If the user requests revision or rejection, record that decision and return to the relevant review/export task.",
                f"Approval run_id must be `{approval_run_id}` so publish-chapter can verify it.",
            ],
            "style_constraints": [],
            "validation_gates": [f"approve record exists for {approval_run_id}"],
            "next_allowed_states": ["publish-release"],
        },
        "release-revision-required": {
            "task_type": "human-approval-boundary",
            "prompt_asset_id": "route.export-release.approval.v1",
            "command": f"Release `{chapter_id}` was rejected or returned for revision. Select the affected scene-development work before rebuilding export.",
            "source_paths": [f"exports/{chapter_id}/export_manifest.json", f"drafts/chapters/{chapter_id}.md", "workflow/approvals/index.jsonl", "reviews/agent"],
            "expected_outputs": ["workflow/approvals/index.jsonl"],
            "hard_constraints": [
                "Do not regenerate the same export and ask for the same approval again.",
                "Return requested prose changes through scene revision, exact-candidate AgentReview, promotion, and chapter workspace before a fresh export.",
                "A new release decision must bind to the rebuilt export fingerprint.",
            ],
            "style_constraints": [],
            "validation_gates": ["affected scene revisions are explicitly selected before workflow resumes"],
            "next_allowed_states": ["chapter-workspace"],
        },
        "publish-release": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.export-release.publish.v1",
            "command": f"python -m literary_engineering_studio_engine publish-chapter <project> --chapter-id {chapter_id} --release-id formal-release --approval-run-id {approval_run_id} --export-formats md,docx",
            "source_paths": [f"exports/{chapter_id}/export_manifest.json", "workflow/approvals/index.jsonl", "reviews/canon_lint.json", f"plot/chapters/{chapter_id}.json"],
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
                "If the release directory already exists, do not overwrite casually; inspect latest and ask the user before replacing.",
            ],
            "style_constraints": [],
            "validation_gates": ["publish manifest exists", "status is published", "latest.json points to release", "no approval bypass"],
            "next_allowed_states": ["ready"],
        },
    }
    default = {
        "task_type": "manual-route-repair",
        "prompt_asset_id": "route.export-release.repair.v1",
        "command": next_action,
        "source_paths": [f"plot/chapters/{chapter_id}.json", f"exports/{chapter_id}", f"releases/{chapter_id}"],
        "expected_outputs": [],
        "hard_constraints": [next_action or "Inspect workflow-state and route-audit, then repair the missing export-and-release gate."],
        "style_constraints": [],
        "validation_gates": ["export-and-release gate resolved"],
        "next_allowed_states": [],
    }
    return table.get(current_state, default)

def _export_release_state_gate_validation(root: Path, task: dict[str, object]) -> tuple[list[str], list[str]]:
    current_state = str(task.get("current_state") or "")
    chapter_id = str(task.get("chapter_id") or task.get("target_id") or task.get("scene_id") or "chapter_0001")
    errors: list[str] = []
    notes: list[str] = []
    if current_state == "chapter-workspace":
        errors.extend(_chapter_workspace_gate_errors(root, chapter_id))
    if current_state == "export-package":
        errors.extend(_chapter_workspace_gate_errors(root, chapter_id))
        errors.extend(_export_package_gate_errors(root, chapter_id))
    if current_state == "release-approval":
        errors.extend(_chapter_workspace_gate_errors(root, chapter_id))
        errors.extend(_export_package_gate_errors(root, chapter_id))
        errors.extend(_release_approval_gate_errors(root, chapter_id))
    if current_state == "publish-release":
        errors.extend(_chapter_workspace_gate_errors(root, chapter_id))
        errors.extend(_export_package_gate_errors(root, chapter_id))
        errors.extend(_release_approval_gate_errors(root, chapter_id))
        errors.extend(_publish_release_gate_errors(root, chapter_id))
    if current_state == "export-package" and not errors:
        notes.append("export package ready with no skipped scenes")
    if current_state == "publish-release" and not errors:
        notes.append("chapter published through approved release gate")
    return errors, notes

def _chapter_workspace_gate_errors(root: Path, chapter_id: str) -> list[str]:
    json_path = root / "plot" / "chapters" / f"{chapter_id}.json"
    report_path = root / "drafts" / "chapters" / f"{chapter_id}.md"
    errors: list[str] = []
    for path in (json_path, report_path):
        if not path.exists():
            errors.append(f"chapter workspace artifact missing: {_rel(path, root)}")
    payload, error = _read_optional_json(json_path)
    if error:
        errors.append(error)
        return errors
    if payload.get("schema") != "literary-engineering-workbench/chapter-workspace/v0.1":
        errors.append("chapter workspace JSON has wrong or missing schema")
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    if _to_int(summary.get("ready_count")) <= 0:
        errors.append("chapter workspace ready_count must be positive")
    if _to_int(summary.get("blocked_count")) != 0:
        errors.append(f"chapter workspace blocked_count must be 0; got {summary.get('blocked_count')}")
    for scene in payload.get("scenes", []) if isinstance(payload.get("scenes"), list) else []:
        if not isinstance(scene, dict):
            continue
        scene_id = str(scene.get("scene_id") or "")
        if scene.get("status") != "ready":
            errors.append(f"chapter scene must be ready: {scene_id or 'unknown'}")
        if scene.get("agent_review_conclusion") != "pass" or scene.get("agent_review_schema_status") != "pass":
            errors.append(f"chapter scene lacks clean platform AgentReview: {scene_id or 'unknown'}")
        if scene.get("agent_review_source_match") is not True:
            errors.append(f"chapter scene AgentReview does not cite exact draft/candidate: {scene_id or 'unknown'}")
        if scene.get("agent_review_unresolved_notes"):
            errors.append(f"chapter scene has unresolved AgentReview notes: {scene_id or 'unknown'}")
        if scene.get("flow_gate_issues") or scene.get("readiness_issues"):
            errors.append(f"chapter scene has unresolved flow/readiness gate issues: {scene_id or 'unknown'}")
    return errors


def _to_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _export_package_gate_errors(root: Path, chapter_id: str) -> list[str]:
    manifest_path = root / "exports" / chapter_id / "export_manifest.json"
    errors: list[str] = []
    payload, error = _read_optional_json(manifest_path)
    if error:
        errors.append(error)
        return errors
    if payload.get("schema") != "literary-engineering-workbench/export-package/v0.1":
        errors.append("export_manifest.json has wrong or missing schema")
    if payload.get("include_blocked") is True:
        errors.append("export package must not use include_blocked for formal delivery")
    requested_formats = {str(item).strip().lower() for item in payload.get("requested_formats", []) if str(item).strip()}
    if not {"md", "docx"}.issubset(requested_formats):
        errors.append("formal export package must include requested_formats md and docx")
    skipped = payload.get("skipped_scenes") if isinstance(payload.get("skipped_scenes"), list) else []
    if skipped:
        errors.append(f"export package skipped_scenes must be empty; got {len(skipped)}")
    outputs = payload.get("outputs") if isinstance(payload.get("outputs"), dict) else {}
    for key in ("novel", "screenplay", "video_prompt_pack"):
        rel = str(outputs.get(key) or "")
        if not rel:
            errors.append(f"export output missing from manifest: {key}")
            continue
        path = root / rel
        if not path.exists():
            errors.append(f"export output file missing: {rel}")
            continue
        hits = _delivery_trace_hits(path)
        if hits:
            errors.append(f"export output contains workbench traces in {rel}: {', '.join(hits[:5])}")
    docx_outputs = outputs.get("docx") if isinstance(outputs.get("docx"), dict) else {}
    layouts = outputs.get("docx_layout_plans") if isinstance(outputs.get("docx_layout_plans"), dict) else {}
    inspections = outputs.get("docx_inspections") if isinstance(outputs.get("docx_inspections"), dict) else {}
    for key in ("novel", "screenplay", "video_prompt_pack"):
        for label, values in (("DOCX", docx_outputs), ("DOCX layout", layouts), ("DOCX inspection", inspections)):
            rel = str(values.get(key) or "")
            if not rel or not (root / rel).is_file():
                errors.append(f"{label} output missing: {key} -> {rel or 'missing'}")
    return errors


def _release_approval_gate_errors(root: Path, chapter_id: str) -> list[str]:
    run_id = f"release-{chapter_id}"
    approval = _approval_record_for_run(root, run_id)
    fingerprint = release_candidate_fingerprint(root, chapter_id)
    if str(approval.get("decision") or "") == "approve" and fingerprint and str(approval.get("subject_sha256") or "").lower() == fingerprint:
        return []
    return [f"release approval missing, stale, or not approve for current export manifest and run_id {run_id}"]


def _publish_release_gate_errors(root: Path, chapter_id: str) -> list[str]:
    release_dir = root / "releases" / chapter_id / "formal-release"
    manifest = release_dir / "publish_manifest.json"
    latest = root / "releases" / chapter_id / "latest.json"
    errors: list[str] = []
    payload, error = _read_optional_json(manifest)
    if error:
        errors.append(error)
        return errors
    if payload.get("schema") != "literary-engineering-workbench/publish-chapter/v0.1":
        errors.append("publish_manifest.json has wrong or missing schema")
    if payload.get("status") != "published":
        errors.append(f"publish status must be published; got {payload.get('status') or 'missing'}")
    approval = payload.get("approval") if isinstance(payload.get("approval"), dict) else {}
    if approval.get("decision") != "approve":
        errors.append("publish manifest approval must be an approve record")
    approved_fingerprint = str(payload.get("approved_export_fingerprint") or "").strip().lower()
    if not approved_fingerprint or str(approval.get("subject_sha256") or "").strip().lower() != approved_fingerprint:
        errors.append("publish manifest approval does not match the approved export fingerprint")
    outputs = payload.get("published_outputs") if isinstance(payload.get("published_outputs"), dict) else {}
    if not outputs:
        errors.append("publish manifest must contain published_outputs")
    for key, rel in outputs.items():
        if not (root / str(rel)).exists():
            errors.append(f"published output missing: {key} -> {rel}")
    latest_payload, latest_error = _read_optional_json(latest)
    if latest_error:
        errors.append(latest_error)
    elif latest_payload.get("manifest") != _rel(manifest, root):
        errors.append("latest.json does not point to formal-release publish_manifest.json")
    return errors


def _delivery_trace_hits(path: Path) -> list[str]:
    text = _read_text(path)
    patterns = {
        "scene-id": r"\bscene_\d{4}\b",
        "agent-task": r"\[AGENT_TASK:",
        "canon-note-heading": r"(?m)^#{1,4}\s*(新增事实候选|人物状态变化|关系变化|伏笔变化|需要人工确认|世界状态变化|状态变化候选)\s*$",
        "review-heading": r"(?m)^#{1,4}\s*(审查|AgentReview|Route Audit|平台 Agent 任务|门禁问题汇总)\b",
        "workflow-path": r"\b(workflow/tasks|reviews/agent|characters/state_patches|drafts/promotions|branch_manifest|roleplay_simulation)\b",
    }
    hits = []
    for label, pattern in patterns.items():
        if re.search(pattern, text):
            hits.append(label)
    return hits
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


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result


build_task_payload = _build_export_release_task_payload
validate_task = _export_release_state_gate_validation
