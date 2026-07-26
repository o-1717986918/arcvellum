"""Authoritative Gate checks for source-ingest route states."""

from __future__ import annotations

from pathlib import Path

from ...agent_tasks import agent_task_completion_status
from ...literary.ingest import (
    archaeology_materialization_errors,
    read_chunk_extraction,
    reconstruction_paths,
    validate_domain_review,
    validate_identity_resolution,
    validate_reconstruction_candidate,
    validate_chunk_extraction,
    verify_archaeology_aggregate,
    verify_archaeology_plan,
    verify_ingest_manifest,
)
from ...task_paths import read_json, relative_path, resolve_project_path
from .support import (
    SOURCE_INGEST_SCHEMA_V2,
    SOURCE_INGEST_SCHEMAS,
    active_chunk_plan,
    candidate_outputs_from_manifest,
    file_sha256,
    import_dir_for_task,
    read_optional_json,
    static_review_conclusion,
)


def validate_task(
    root: Path,
    task: dict[str, object],
) -> tuple[list[str], list[str]]:
    state = str(task.get("current_state") or "")
    import_dir = import_dir_for_task(root, task)
    work_id = str(
        task.get("work_id")
        or task.get("target_id")
        or task.get("scene_id")
        or ""
    )
    validator = _STATE_GATES.get(state)
    errors = validator(root, import_dir, work_id, task) if validator else []
    notes = [_PASS_NOTES[state]] if state in _PASS_NOTES and not errors else []
    return errors, notes


def _manifest_state_gate(
    root: Path,
    import_dir: Path,
    _work_id: str,
    _task: dict[str, object],
) -> list[str]:
    return manifest_gate_errors(root, import_dir)


def _chunk_state_gate(
    root: Path,
    import_dir: Path,
    _work_id: str,
    task: dict[str, object],
) -> list[str]:
    return [
        *manifest_gate_errors(root, import_dir),
        *chunk_extraction_gate_errors(root, import_dir, task),
    ]


def _fan_in_state_gate(
    root: Path,
    import_dir: Path,
    _work_id: str,
    _task: dict[str, object],
) -> list[str]:
    return [
        *manifest_gate_errors(root, import_dir),
        *archaeology_fan_in_gate_errors(root, import_dir),
    ]


def _extraction_state_gate(
    root: Path,
    import_dir: Path,
    work_id: str,
    _task: dict[str, object],
) -> list[str]:
    return [
        *manifest_gate_errors(root, import_dir),
        *archaeology_fan_in_gate_errors(root, import_dir),
        *extraction_gate_errors(
            root,
            import_dir,
            work_id,
            require_review_pass=False,
        ),
    ]


def _review_state_gate(
    root: Path,
    import_dir: Path,
    work_id: str,
    task: dict[str, object],
) -> list[str]:
    return [
        *manifest_gate_errors(root, import_dir),
        *archaeology_fan_in_gate_errors(root, import_dir),
        *extraction_gate_errors(
            root,
            import_dir,
            work_id,
            require_review_pass=True,
        ),
        *extraction_revision_gate_errors(root, task),
    ]


def _resolution_state_gate(
    root: Path,
    import_dir: Path,
    _work_id: str,
    _task: dict[str, object],
) -> list[str]:
    manifest, aggregate, paths = _archaeology_inputs(root, import_dir)
    payload = read_json(root / paths["resolution"])
    return [
        *manifest_gate_errors(root, import_dir),
        *archaeology_fan_in_gate_errors(root, import_dir),
        *_completion_errors(root, root / paths["resolution_task"], "archaeology identity resolution"),
        *validate_identity_resolution(payload, manifest=manifest, aggregate=aggregate),
        *_required_paths(root, paths["resolution_report"]),
    ]


def _reconstruction_state_gate(
    root: Path,
    import_dir: Path,
    _work_id: str,
    _task: dict[str, object],
) -> list[str]:
    manifest, aggregate, paths = _archaeology_inputs(root, import_dir)
    resolution = read_json(root / paths["resolution"])
    payload = read_json(root / paths["candidate"])
    return [
        *manifest_gate_errors(root, import_dir),
        *archaeology_fan_in_gate_errors(root, import_dir),
        *validate_identity_resolution(resolution, manifest=manifest, aggregate=aggregate),
        *_completion_errors(root, root / paths["candidate_task"], "archaeology reconstruction"),
        *validate_reconstruction_candidate(
            payload,
            manifest=manifest,
            aggregate=aggregate,
            resolution=resolution,
        ),
        *_required_paths(root, paths["candidate_report"]),
    ]


def _domain_review_state_gate(
    root: Path,
    import_dir: Path,
    _work_id: str,
    _task: dict[str, object],
) -> list[str]:
    manifest, aggregate, paths = _archaeology_inputs(root, import_dir)
    resolution = read_json(root / paths["resolution"])
    candidate = read_json(root / paths["candidate"])
    review = read_json(root / paths["review"])
    errors = [
        *manifest_gate_errors(root, import_dir),
        *archaeology_fan_in_gate_errors(root, import_dir),
        *validate_identity_resolution(resolution, manifest=manifest, aggregate=aggregate),
        *validate_reconstruction_candidate(
            candidate,
            manifest=manifest,
            aggregate=aggregate,
            resolution=resolution,
        ),
        *_completion_errors(root, root / paths["review_task"], "archaeology domain review"),
        *validate_domain_review(review, manifest=manifest, candidate=candidate),
        *_required_paths(root, paths["review_report"]),
    ]
    if str(review.get("status") or "") != "pass":
        errors.append("archaeology domain review must pass before materialization")
    return errors


def _materialization_state_gate(
    root: Path,
    import_dir: Path,
    _work_id: str,
    _task: dict[str, object],
) -> list[str]:
    return [
        *manifest_gate_errors(root, import_dir),
        *archaeology_fan_in_gate_errors(root, import_dir),
        *archaeology_materialization_errors(root, import_dir),
    ]


_STATE_GATES = {
    "source-manifest": _manifest_state_gate,
    "chunk-extraction-agent-task": _chunk_state_gate,
    "archaeology-fan-in": _fan_in_state_gate,
    "archaeology-resolution-agent-task": _resolution_state_gate,
    "archaeology-reconstruction-agent-task": _reconstruction_state_gate,
    "archaeology-domain-review-agent-task": _domain_review_state_gate,
    "archaeology-materialize": _materialization_state_gate,
    "extraction-agent-task": _extraction_state_gate,
    "extraction-review": _review_state_gate,
}

_PASS_NOTES = {
    "chunk-extraction-agent-task": "evidence-bound source chunk extraction passed",
    "archaeology-fan-in": "source extraction fan-in passed",
    "archaeology-resolution-agent-task": "archaeology identity and conflict resolution passed",
    "archaeology-reconstruction-agent-task": "evidence-bound candidate project passed",
    "archaeology-domain-review-agent-task": "archaeology domain review passed",
    "archaeology-materialize": "reviewed reconstruction entered the Archive candidate queue",
    "extraction-agent-task": "source extraction candidates and sidecar completion marker exist",
    "extraction-review": "source extraction review passed",
}


def manifest_gate_errors(root: Path, import_dir: Path) -> list[str]:
    manifest_path = import_dir / "source_manifest.json"
    required = [
        manifest_path,
        import_dir / "source_ingest.md",
        import_dir / "extract_project_files.agent_tasks.md",
    ]
    errors = [
        f"missing source-ingest artifact: {relative_path(path, root)}"
        for path in required
        if not path.exists()
    ]
    payload, error = read_optional_json(manifest_path)
    if error:
        return [*errors, error]
    schema = payload.get("schema")
    if schema not in SOURCE_INGEST_SCHEMAS:
        errors.append("source_manifest.json has wrong or missing schema")
    if schema == SOURCE_INGEST_SCHEMA_V2:
        errors.extend(verify_ingest_manifest(root, payload))
        errors.extend(
            verify_archaeology_plan(
                payload,
                import_dir=import_dir.relative_to(root),
            )
        )
    errors.extend(_manifest_shape_errors(payload))
    return errors


def _manifest_shape_errors(payload: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if not payload.get("work_id"):
        errors.append("source_manifest.json must contain work_id")
    if not isinstance(payload.get("chunks"), list) or not payload.get("chunks"):
        errors.append("source_manifest.json must contain source chunks")
    outputs = payload.get("candidate_outputs")
    if not isinstance(outputs, dict) or not outputs:
        errors.append("source_manifest.json must contain candidate_outputs")
    return errors


def chunk_extraction_gate_errors(
    root: Path,
    import_dir: Path,
    task: dict[str, object],
) -> list[str]:
    manifest = read_json(import_dir / "source_manifest.json")
    chunk_id = str(task.get("chunk_id") or "")
    item = active_chunk_plan(manifest, chunk_id)
    if not item:
        return [
            f"source chunk extraction plan is missing chunk_id: {chunk_id or 'missing'}"
        ]
    errors = _completion_errors(
        root,
        resolve_project_path(root, str(item.get("task_path") or "")),
        "source chunk extraction",
    )
    payload, read_errors = read_chunk_extraction(
        resolve_project_path(root, str(item.get("expected_output") or ""))
    )
    errors.extend(read_errors)
    if payload:
        errors.extend(
            _chunk_payload_errors(
                root,
                manifest,
                chunk_id,
                payload,
                import_dir,
            )
        )
    return errors


def _chunk_payload_errors(
    root: Path,
    manifest: dict[str, object],
    chunk_id: str,
    payload: dict[str, object],
    import_dir: Path,
) -> list[str]:
    chunks = {
        str(record.get("chunk_id") or ""): record
        for record in manifest.get("chunks") or []
        if isinstance(record, dict)
    }
    evidence = manifest.get("evidence_index")
    revision = (
        str(evidence.get("revision") or "") if isinstance(evidence, dict) else ""
    )
    return validate_chunk_extraction(
        payload,
        work_id=str(manifest.get("work_id") or import_dir.name),
        chunk=chunks.get(chunk_id, {}),
        evidence_revision=revision,
        root=root,
    )


def archaeology_fan_in_gate_errors(
    root: Path,
    import_dir: Path,
) -> list[str]:
    manifest = read_json(import_dir / "source_manifest.json")
    archaeology = manifest.get("archaeology")
    if not isinstance(archaeology, dict):
        return []
    aggregate_path = resolve_project_path(
        root,
        str(archaeology.get("aggregate_path") or ""),
    )
    aggregate = read_json(aggregate_path)
    if not aggregate:
        return [
            f"archaeology aggregate missing: {relative_path(aggregate_path, root)}"
        ]
    return verify_archaeology_aggregate(
        root,
        manifest,
        aggregate,
        import_dir=import_dir.relative_to(root),
    )


def extraction_gate_errors(
    root: Path,
    import_dir: Path,
    work_id: str,
    *,
    require_review_pass: bool,
) -> list[str]:
    manifest = read_json(import_dir / "source_manifest.json")
    outputs = candidate_outputs_from_manifest(manifest, work_id or import_dir.name)
    errors = _completion_errors(
        root,
        import_dir / "extract_project_files.agent_tasks.md",
        "source extraction",
    )
    for key, relative in outputs.items():
        if not (root / relative).exists():
            errors.append(f"source extraction output missing: {key} -> {relative}")
    if require_review_pass:
        review = root / outputs.get(
            "review",
            f"reviews/source_ingest/{work_id}_extraction_review.md",
        )
        conclusion = static_review_conclusion(review)
        if conclusion != "pass":
            errors.append(
                "source-ingest extraction review conclusion must be pass; "
                f"got {conclusion or 'missing'} at {relative_path(review, root)}"
            )
    return errors


def _completion_errors(
    root: Path,
    task_path: Path,
    label: str,
) -> list[str]:
    state = agent_task_completion_status(task_path, root=root)
    if state.get("complete") is True:
        return []
    return [f"{label} sidecar is incomplete: {state.get('message')}"]


def extraction_revision_gate_errors(
    root: Path,
    task: dict[str, object],
) -> list[str]:
    before = task.get("repair_target_sha256_before_revision")
    if not isinstance(before, dict) or not before:
        return [
            "source extraction revision task is missing repair target hash provenance"
        ]
    changed = any(
        path.is_file() and file_sha256(path) != str(digest).strip().lower()
        for relative, digest in before.items()
        for path in [resolve_project_path(root, str(relative))]
    )
    return [] if changed else [
        "source extraction candidates did not change; rewriting only the review cannot complete revision"
    ]


def _archaeology_inputs(
    root: Path,
    import_dir: Path,
) -> tuple[dict[str, object], dict[str, object], dict[str, str]]:
    manifest = read_json(import_dir / "source_manifest.json")
    archaeology = manifest.get("archaeology")
    aggregate_rel = (
        str(archaeology.get("aggregate_path") or "")
        if isinstance(archaeology, dict)
        else ""
    )
    return (
        manifest,
        read_json(root / aggregate_rel),
        reconstruction_paths(import_dir.relative_to(root)),
    )


def _required_paths(root: Path, *relative_paths: str) -> list[str]:
    return [
        f"archaeology output missing: {relative}"
        for relative in relative_paths
        if not (root / relative).is_file()
    ]
