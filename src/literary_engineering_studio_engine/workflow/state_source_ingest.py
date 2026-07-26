"""Derived state for the source-ingest route."""
from __future__ import annotations

from pathlib import Path

from ..agent_tasks import agent_task_completion_status
from ..literary.ingest import (
    SOURCE_INGEST_SCHEMA_V2,
    read_chunk_extraction,
    validate_chunk_extraction,
    verify_archaeology_aggregate,
    verify_archaeology_plan,
    verify_ingest_manifest,
)
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
    steps = [_source_manifest_step(root, manifest_path, report_path, task_path)]
    if isinstance(manifest.get("archaeology"), dict):
        steps.extend(
            [
                _source_chunk_extraction_step(root, import_dir, manifest),
                _source_fan_in_step(root, import_dir, manifest),
            ]
        )
    steps.extend(
        [
            _source_extraction_step(root, task_path, candidate_paths, review_path),
            _longform_review_step(
                "extraction-review",
                review_path,
                "write source-ingest extraction review with conclusion: pass",
            ),
        ]
    )
    first_open = next((step for step in steps if step["status"] != "pass"), None)
    state = {
        "target_id": work_id,
        "work_id": work_id,
        "import_dir": _rel(import_dir, root),
        "status": "ready" if first_open is None else "blocked",
        "current_step": first_open["key"] if first_open else "ready",
        "next_action": first_open["next_action"] if first_open else "",
        "steps": steps,
    }
    if first_open:
        for field in (
            "chunk_id",
            "chunk_task_path",
            "chunk_output_path",
            "source_chunk_path",
            "aggregate_path",
        ):
            if first_open.get(field):
                state[field] = first_open[field]
    return state


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
        [
            *verify_ingest_manifest(root, payload),
            *verify_archaeology_plan(
                payload,
                import_dir=manifest_path.parent.relative_to(root),
            ),
        ]
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


def _source_chunk_extraction_step(
    root: Path,
    import_dir: Path,
    manifest: dict[str, object],
) -> dict[str, object]:
    archaeology = manifest.get("archaeology")
    plan = archaeology.get("chunk_tasks") if isinstance(archaeology, dict) else []
    chunks = {
        str(item.get("chunk_id") or ""): item
        for item in manifest.get("chunks") or []
        if isinstance(item, dict)
    }
    evidence = manifest.get("evidence_index")
    evidence_revision = (
        str(evidence.get("revision") or "") if isinstance(evidence, dict) else ""
    )
    for item in plan if isinstance(plan, list) else []:
        if not isinstance(item, dict):
            continue
        step = _chunk_step(
            root,
            item,
            chunk=chunks.get(str(item.get("chunk_id") or ""), {}),
            work_id=str(manifest.get("work_id") or import_dir.name),
            evidence_revision=evidence_revision,
        )
        if step["status"] != "pass":
            return step
    count = len(plan) if isinstance(plan, list) else 0
    return {
        "key": "chunk-extraction-agent-task",
        "status": "pass",
        "path": _rel(import_dir / "extractions" / "tasks", root),
        "message": f"all {count} source chunk extraction tasks passed",
        "next_action": "",
    }


def _chunk_step(
    root: Path,
    item: dict[str, object],
    *,
    chunk: dict[str, object],
    work_id: str,
    evidence_revision: str,
) -> dict[str, object]:
    task_path = root / str(item.get("task_path") or "")
    output_path = root / str(item.get("expected_output") or "")
    completion = agent_task_completion_status(task_path, root=root)
    payload, read_errors = read_chunk_extraction(output_path)
    errors = list(read_errors)
    if payload:
        errors.extend(
            validate_chunk_extraction(
                payload,
                work_id=work_id,
                chunk=chunk,
                evidence_revision=evidence_revision,
                root=root,
            )
        )
    complete = completion.get("complete") is True and not errors
    message = str(completion.get("message") or "")
    if errors:
        message = (message + "; " if message else "") + "; ".join(errors[:6])
    return {
        "key": "chunk-extraction-agent-task",
        "status": "pass" if complete else "invalid" if errors else str(completion.get("status") or "pending"),
        "path": _rel(task_path, root),
        "chunk_id": str(item.get("chunk_id") or ""),
        "chunk_task_path": _rel(task_path, root),
        "chunk_output_path": _rel(output_path, root),
        "source_chunk_path": str(item.get("source_chunk_path") or ""),
        "completion": completion.get("completion", ""),
        "message": message,
        "next_action": "" if complete else "complete the current evidence-bound source chunk extraction task",
    }


def _source_fan_in_step(
    root: Path,
    import_dir: Path,
    manifest: dict[str, object],
) -> dict[str, object]:
    archaeology = manifest.get("archaeology")
    aggregate_rel = (
        str(archaeology.get("aggregate_path") or "")
        if isinstance(archaeology, dict)
        else ""
    )
    aggregate_path = root / aggregate_rel
    aggregate = _read_json(aggregate_path)
    errors = (
        verify_archaeology_aggregate(
            root,
            manifest,
            aggregate,
            import_dir=import_dir.relative_to(root),
        )
        if aggregate
        else [f"archaeology aggregate missing: {aggregate_rel}"]
    )
    return {
        "key": "archaeology-fan-in",
        "status": "pass" if not errors else "missing" if not aggregate else "invalid",
        "path": aggregate_rel,
        "aggregate_path": aggregate_rel,
        "message": "archaeology fan-in is ready" if not errors else "; ".join(errors[:8]),
        "next_action": "" if not errors else f"run archaeology-aggregate for {import_dir.name}",
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
