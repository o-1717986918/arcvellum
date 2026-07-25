"""Derived state for the source-ingest route."""
from __future__ import annotations

from pathlib import Path

from ..agent_tasks import agent_task_completion_status
from ..literary.ingest import SOURCE_INGEST_SCHEMA_V2, verify_ingest_manifest
from .state_common import _longform_review_step, _read_json, _rel


SOURCE_INGEST_SCHEMA_V1 = "literary-engineering-workbench/source-ingest/v1"
SOURCE_INGEST_SCHEMAS = {SOURCE_INGEST_SCHEMA_V1, SOURCE_INGEST_SCHEMA_V2}


def _source_ingest_states(root: Path) -> list[dict[str, object]]:
    imports = root / "sources" / "imports"
    if not imports.exists():
        return []
    states: list[dict[str, object]] = []
    for manifest in sorted(imports.glob("*/source_manifest.json")):
        states.append(_source_ingest_state(root, manifest.parent))
    return states


def _source_ingest_state(root: Path, import_dir: Path) -> dict[str, object]:
    manifest_path = import_dir / "source_manifest.json"
    report_path = import_dir / "source_ingest.md"
    task_path = import_dir / "extract_project_files.agent_tasks.md"
    manifest = _read_json(manifest_path)
    work_id = str(manifest.get("work_id") or import_dir.name)
    candidate_outputs = _source_candidate_outputs(manifest)
    review_path = root / str(candidate_outputs.get("review") or f"reviews/source_ingest/{work_id}_extraction_review.md")
    candidate_paths = [root / rel for key, rel in candidate_outputs.items() if key != "review"]
    steps = [
        _source_manifest_step(root, manifest_path, report_path, task_path),
        _source_extraction_step(root, task_path, candidate_paths, review_path),
        _longform_review_step(
            "extraction-review",
            review_path,
            "write source-ingest extraction review with conclusion: pass",
        ),
    ]
    first_open = next((step for step in steps if step["status"] != "pass"), None)
    return {
        "target_id": work_id,
        "work_id": work_id,
        "import_dir": _rel(import_dir, root),
        "status": "ready" if first_open is None else "blocked",
        "current_step": first_open["key"] if first_open else "ready",
        "next_action": first_open["next_action"] if first_open else "",
        "steps": steps,
    }


def _source_manifest_step(root: Path, manifest_path: Path, report_path: Path, task_path: Path) -> dict[str, object]:
    missing = [_rel(path, root) for path in (manifest_path, report_path, task_path) if not path.exists()]
    if missing:
        return {
            "key": "source-manifest",
            "status": "missing",
            "path": _rel(manifest_path, root),
            "message": "missing " + ", ".join(missing),
            "next_action": "run source-ingest with source/text/title/work-id to create manifest, report, and extraction sidecar",
        }
    payload = _read_json(manifest_path)
    schema = payload.get("schema")
    validation_errors = (
        verify_ingest_manifest(root, payload)
        if schema == SOURCE_INGEST_SCHEMA_V2
        else []
    )
    if schema not in SOURCE_INGEST_SCHEMAS or validation_errors:
        return {
            "key": "source-manifest",
            "status": "invalid",
            "path": _rel(manifest_path, root),
            "message": (
                "; ".join(validation_errors)
                if validation_errors
                else "source_manifest.json is invalid or has wrong schema"
            ),
            "next_action": "rerun source-ingest or repair the manifest from source evidence",
        }
    return {
        "key": "source-manifest",
        "status": "pass",
        "path": _rel(manifest_path, root),
        "message": (
            f"source manifest exists; schema={schema}; "
            f"segments={payload.get('segment_count', 0)}; "
            f"chunks={payload.get('chunk_count', 0)}"
        ),
        "next_action": "",
    }


def _source_extraction_step(root: Path, task_path: Path, candidate_paths: list[Path], review_path: Path) -> dict[str, object]:
    state = agent_task_completion_status(task_path, root=root)
    required = [*candidate_paths, review_path]
    missing = [_rel(path, root) for path in required if not path.exists()]
    complete = state.get("complete") is True and not missing
    message = str(state.get("message") or "")
    if missing:
        message = (message + "; " if message else "") + "missing " + ", ".join(missing)
    return {
        "key": "extraction-agent-task",
        "status": "pass" if complete else str(state.get("status") or "pending"),
        "path": _rel(task_path, root),
        "completion": state.get("completion", ""),
        "message": message,
        "next_action": "" if complete else "complete source extraction sidecar, extracted candidates, review report, and completion marker",
    }


def _source_candidate_outputs(manifest: dict[str, object]) -> dict[str, str]:
    outputs = manifest.get("candidate_outputs") if isinstance(manifest.get("candidate_outputs"), dict) else {}
    return {str(key): str(value) for key, value in outputs.items() if str(value).strip()}
