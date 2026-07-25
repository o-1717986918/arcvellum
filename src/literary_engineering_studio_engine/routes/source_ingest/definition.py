"""Formal task blueprint and Gate logic for the source-ingest route.

This route deliberately owns candidate-only extraction. It never promotes
source-derived claims into canon or project assets itself.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from ...agent_tasks import agent_task_completion_status
from ...literary.ingest import SOURCE_INGEST_SCHEMA_V2, verify_ingest_manifest
from ...task_paths import TASK_SCHEMA, normalize_relative_path, now, read_json, relative_path, resolve_project_path, task_id


SOURCE_INGEST_SCHEMA_V1 = "literary-engineering-workbench/source-ingest/v1"
SOURCE_INGEST_SCHEMAS = {SOURCE_INGEST_SCHEMA_V1, SOURCE_INGEST_SCHEMA_V2}


def build_task_payload(root: Path, route: str, state: dict[str, object]) -> dict[str, object]:
    work_id = str(state.get("work_id") or state.get("target_id") or "")
    current_state = str(state.get("current_step") or "")
    next_action = str(state.get("next_action") or "")
    import_dir = str(state.get("import_dir") or f"sources/imports/{work_id}")
    blueprint = blueprint_for_state(root, work_id, import_dir, current_state, next_action)
    identifier = task_id(route, work_id or "source", current_state)
    expected_outputs = _unique([normalize_relative_path(item) for item in blueprint["expected_outputs"]])
    source_paths = _unique([normalize_relative_path(item) for item in blueprint["source_paths"]])
    payload: dict[str, object] = {
        "schema": TASK_SCHEMA,
        "task_id": identifier,
        "status": "issued",
        "created_at": now(),
        "route": route,
        "scene_id": work_id,
        "target_id": work_id,
        "work_id": work_id,
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
        "submission_command": f"python -m literary_engineering_studio_engine task-submit <project> --task-id {identifier} --from <artifact>",
        "completion_command": f"python -m literary_engineering_studio_engine task-complete <project> --task-id {identifier}",
        "validation_gates": blueprint["validation_gates"],
        "forbidden_shortcuts": [
            "Do not write source-derived material directly into canon, character, plot, draft, export, or release files.",
            "Do not treat extracted claims as confirmed facts without evidence_refs, confidence, unknowns, contradiction notes, review, and approval.",
            "Do not skip extract_project_files.agent_tasks.md after source-ingest creates it.",
            "Do not copy long source passages into extraction reports.",
            "Do not treat this task as complete until task-submit and task-complete have succeeded.",
        ],
        "next_allowed_states": blueprint["next_allowed_states"],
    }
    repair_targets = [str(item) for item in blueprint.get("repair_targets", [])]
    if repair_targets:
        payload["repair_targets"] = repair_targets
        payload["repair_target_sha256_before_revision"] = {
            relative: _file_sha256(resolve_project_path(root, relative))
            for relative in repair_targets
            if resolve_project_path(root, relative).is_file()
        }
    return payload


def blueprint_for_state(root: Path, work_id: str, import_dir: str, current_state: str, next_action: str) -> dict[str, object]:
    manifest_path = root / import_dir / "source_manifest.json"
    manifest = read_json(manifest_path)
    candidate_outputs = candidate_outputs_from_manifest(manifest, work_id)
    task_path = f"{import_dir}/extract_project_files.agent_tasks.md"
    completion = f"{import_dir}/extract_project_files.agent_completion.json"
    report = f"{import_dir}/source_ingest.md"
    chunks = [str(item.get("path") or "") for item in manifest.get("chunks", []) if isinstance(item, dict)]
    evidence_path = evidence_path_from_manifest(manifest)
    extraction_sources = extraction_source_paths(
        import_dir, report, task_path, evidence_path, chunks
    )
    candidate_values = list(candidate_outputs.values())
    review = candidate_outputs.get("review", f"reviews/source_ingest/{work_id}_extraction_review.md")
    table: dict[str, dict[str, object]] = {
        "source-manifest": {
            "task_type": "deterministic-cli-or-repair",
            "prompt_asset_id": "route.source-ingest.import.v1",
            "command": "python -m literary_engineering_studio_engine source-ingest <project> --source <source> --title <title> --work-id <work-id> --rights-declaration <declaration>",
            "source_paths": ["project.yaml"],
            "expected_outputs": [
                f"{import_dir}/source_manifest.json",
                report,
                f"{import_dir}/evidence_index.json",
                task_path,
            ],
            "hard_constraints": [
                "Run source-ingest with explicit source/text/title/work-id when starting a new import.",
                "Record a rights declaration and preserve immutable source bytes, extracted text, ranges, and hashes.",
                "If repairing an invalid manifest, preserve source evidence and candidate output paths.",
            ],
            "style_constraints": [],
            "validation_gates": ["source manifest exists", "source ingest report exists", "extraction sidecar exists", "source_manifest schema is valid"],
            "next_allowed_states": ["extraction-agent-task"],
        },
        "extraction-agent-task": {
            "task_type": "platform-agent-extraction",
            "prompt_asset_id": "route.source-ingest.extract-project-files.v1",
            "command": "",
            "source_paths": extraction_sources,
            "expected_outputs": [*candidate_values, completion],
            "hard_constraints": ["Read extract_project_files.agent_tasks.md and all source chunks before writing extracted candidates.", "Every extracted claim must include evidence_refs, confidence, unknowns, and contradiction notes when relevant.", "Write only candidate assets and source-ingest review; do not overwrite confirmed project files."],
            "style_constraints": ["For style notes from non-public-domain or unauthorized sources, abstract high-level craft features only."],
            "validation_gates": ["extraction sidecar completion marker exists", "all candidate outputs exist"],
            "next_allowed_states": ["extraction-review"],
        },
        "extraction-review": {
            "task_type": "platform-agent-revision",
            "prompt_asset_id": "route.source-ingest.extraction-review.v1",
            "command": "",
            "source_paths": [
                f"{import_dir}/source_manifest.json",
                evidence_path,
                *chunks,
                *[item for item in candidate_values if item != review],
                review,
            ],
            "expected_outputs": [*[item for item in candidate_values if item != review], review],
            "repair_targets": [item for item in candidate_values if item != review],
            "hard_constraints": ["Revise the extracted candidate files against every review finding, then rewrite the review honestly.", "At least one declared extracted candidate must change; editing only the review conclusion is forbidden.", "The extraction review must be a clean pass before source-derived candidates are treated as route-ready.", "pass_with_notes, missing evidence, copied long passages, or direct canon writeback are blocking."],
            "style_constraints": [],
            "validation_gates": ["source-ingest extraction review conclusion is pass"],
            "next_allowed_states": ["ready"],
        },
    }
    return table.get(current_state, {
        "task_type": "manual-route-repair",
        "prompt_asset_id": "route.source-ingest.repair.v1",
        "command": next_action,
        "source_paths": [f"{import_dir}/source_manifest.json", report],
        "expected_outputs": [],
        "hard_constraints": [next_action or "Inspect workflow-state and route-audit, then repair the missing source-ingest gate."],
        "style_constraints": [],
        "validation_gates": ["source-ingest gate resolved"],
        "next_allowed_states": [],
    })


def validate_task(root: Path, task: dict[str, object]) -> tuple[list[str], list[str]]:
    current_state = str(task.get("current_state") or "")
    work_id = str(task.get("work_id") or task.get("target_id") or task.get("scene_id") or "")
    import_dir = import_dir_for_task(root, task)
    errors: list[str] = []
    notes: list[str] = []
    if current_state == "source-manifest":
        errors.extend(manifest_gate_errors(root, import_dir))
    if current_state == "extraction-agent-task":
        errors.extend(manifest_gate_errors(root, import_dir))
        errors.extend(extraction_gate_errors(root, import_dir, work_id, require_review_pass=False))
    if current_state == "extraction-review":
        errors.extend(manifest_gate_errors(root, import_dir))
        errors.extend(extraction_gate_errors(root, import_dir, work_id, require_review_pass=True))
        errors.extend(extraction_revision_gate_errors(root, task))
    if current_state == "extraction-agent-task" and not errors:
        notes.append("source extraction candidates and sidecar completion marker exist")
    if current_state == "extraction-review" and not errors:
        notes.append("source extraction review passed")
    return errors, notes


def manifest_gate_errors(root: Path, import_dir: Path) -> list[str]:
    manifest_path = import_dir / "source_manifest.json"
    report_path = import_dir / "source_ingest.md"
    task_path = import_dir / "extract_project_files.agent_tasks.md"
    errors = [f"missing source-ingest artifact: {relative_path(path, root)}" for path in (manifest_path, report_path, task_path) if not path.exists()]
    payload, error = _read_optional_json(manifest_path)
    if error:
        return [*errors, error]
    if payload.get("schema") not in SOURCE_INGEST_SCHEMAS:
        errors.append("source_manifest.json has wrong or missing schema")
    if payload.get("schema") == SOURCE_INGEST_SCHEMA_V2:
        errors.extend(verify_ingest_manifest(root, payload))
    if not payload.get("work_id"):
        errors.append("source_manifest.json must contain work_id")
    if not isinstance(payload.get("chunks"), list) or not payload.get("chunks"):
        errors.append("source_manifest.json must contain source chunks")
    if not isinstance(payload.get("candidate_outputs"), dict) or not payload.get("candidate_outputs"):
        errors.append("source_manifest.json must contain candidate_outputs")
    return errors


def evidence_path_from_manifest(manifest: dict[str, object]) -> str:
    record = manifest.get("evidence_index")
    if isinstance(record, dict) and str(record.get("path") or "").strip():
        return str(record["path"])
    return ""


def extraction_source_paths(
    import_dir: str,
    report: str,
    task_path: str,
    evidence_path: str,
    chunks: list[str],
) -> list[str]:
    return [
        "project.yaml",
        f"{import_dir}/source_manifest.json",
        report,
        task_path,
        evidence_path,
        *chunks,
    ]


def extraction_gate_errors(root: Path, import_dir: Path, work_id: str, *, require_review_pass: bool) -> list[str]:
    manifest = read_json(import_dir / "source_manifest.json")
    outputs = candidate_outputs_from_manifest(manifest, work_id or import_dir.name)
    task_path = import_dir / "extract_project_files.agent_tasks.md"
    state = agent_task_completion_status(task_path, root=root)
    errors: list[str] = []
    if state.get("complete") is not True:
        errors.append(f"source extraction sidecar is incomplete: {state.get('message')}")
    for key, relative in outputs.items():
        if not (root / relative).exists():
            errors.append(f"source extraction output missing: {key} -> {relative}")
    if require_review_pass:
        review = root / outputs.get("review", f"reviews/source_ingest/{work_id}_extraction_review.md")
        conclusion = _static_review_conclusion(review)
        if conclusion != "pass":
            errors.append(f"source-ingest extraction review conclusion must be pass; got {conclusion or 'missing'} at {relative_path(review, root)}")
    return errors


def extraction_revision_gate_errors(root: Path, task: dict[str, object]) -> list[str]:
    before = task.get("repair_target_sha256_before_revision")
    if not isinstance(before, dict) or not before:
        return ["source extraction revision task is missing repair target hash provenance"]
    for relative, digest in before.items():
        path = resolve_project_path(root, str(relative))
        if path.is_file() and _file_sha256(path) != str(digest).strip().lower():
            return []
    return ["source extraction candidates did not change; rewriting only the review cannot complete revision"]


def import_dir_for_task(root: Path, task: dict[str, object]) -> Path:
    work_id = str(task.get("work_id") or task.get("target_id") or task.get("scene_id") or "")
    for item in [str(value) for value in task.get("source_paths") or []]:
        normalized = item.replace("\\", "/")
        if "/source_manifest.json" in f"/{normalized}":
            return resolve_project_path(root, normalized).parent
    return root / "sources" / "imports" / (work_id or "source")


def candidate_outputs_from_manifest(manifest: dict[str, object], work_id: str) -> dict[str, str]:
    outputs = manifest.get("candidate_outputs") if isinstance(manifest.get("candidate_outputs"), dict) else {}
    if outputs:
        return {str(key): str(value) for key, value in outputs.items() if str(value).strip()}
    return {
        "project_brief": f"sources/imports/{work_id}/extracted/project_brief.md",
        "characters": f"characters/candidates/extracted/{work_id}_characters.md",
        "world": f"canon/candidates/extracted/{work_id}_world.md",
        "outline": f"plot/candidates/extracted/{work_id}_outline.md",
        "timeline": f"plot/candidates/extracted/{work_id}_timeline.md",
        "foreshadowing": f"plot/candidates/extracted/{work_id}_foreshadowing.md",
        "style_notes": f"style/candidates/{work_id}_style_generation_notes.md",
        "review": f"reviews/source_ingest/{work_id}_extraction_review.md",
    }


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_optional_json(path: Path) -> tuple[dict[str, object], str]:
    if not path.exists():
        return {}, f"JSON file missing: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, f"invalid JSON: {path.name} ({exc.msg})"
    except OSError as exc:
        return {}, str(exc)
    return (payload, "") if isinstance(payload, dict) else ({}, f"JSON root is not an object: {path}")


def _static_review_conclusion(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore").strip() if path.exists() else ""
    match = re.search(r"(?m)^-\s*(?:审查)?结论：\s*(?:\*\*)?`?([a-z_]+)`?(?:\*\*)?\s*$", text, re.IGNORECASE)
    return match.group(1).strip().lower() if match else ""


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))
