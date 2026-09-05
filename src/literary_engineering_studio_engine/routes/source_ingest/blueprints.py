"""Formal task blueprints for candidate-only source ingestion."""

from __future__ import annotations

from pathlib import Path

from ...task_paths import (
    TASK_SCHEMA,
    normalize_relative_path,
    now,
    read_json,
    resolve_project_path,
    task_id,
)
from .support import (
    SOURCE_INGEST_FORBIDDEN_SHORTCUTS,
    SOURCE_INGEST_REQUIRED_READING,
    active_chunk_plan,
    candidate_outputs_from_manifest,
    evidence_path_from_manifest,
    extraction_source_paths,
    file_sha256,
    source_ingest_contract_language,
    unique,
)
from .reconstruction_blueprints import (
    aggregate_path as _aggregate_path,
    domain_review_blueprint as _domain_review_blueprint,
    materialization_blueprint as _materialization_blueprint,
    reconstruction_blueprint as _reconstruction_blueprint,
    resolution_blueprint as _resolution_blueprint,
)


def build_task_payload(
    root: Path,
    route: str,
    state: dict[str, object],
) -> dict[str, object]:
    work_id = str(state.get("work_id") or state.get("target_id") or "")
    current_state = str(state.get("current_step") or "")
    import_dir = str(state.get("import_dir") or f"sources/imports/{work_id}")
    blueprint = blueprint_for_state(
        root,
        work_id,
        import_dir,
        current_state,
        str(state.get("next_action") or ""),
        state=state,
    )
    chunk_id = str(state.get("chunk_id") or "")
    identity = f"{work_id}--{chunk_id}" if chunk_id else work_id
    identifier = task_id(route, identity or "source", current_state)
    payload = _task_envelope(
        route=route,
        work_id=work_id,
        chunk_id=chunk_id,
        current_state=current_state,
        identifier=identifier,
        blueprint=blueprint,
    )
    _attach_optional_contract(root, payload, blueprint)
    return payload


def _task_envelope(
    *,
    route: str,
    work_id: str,
    chunk_id: str,
    current_state: str,
    identifier: str,
    blueprint: dict[str, object],
) -> dict[str, object]:
    expected = unique(
        [normalize_relative_path(item) for item in blueprint["expected_outputs"]]
    )
    sources = unique(
        [normalize_relative_path(item) for item in blueprint["source_paths"]]
    )
    return {
        "schema": TASK_SCHEMA,
        "task_id": identifier,
        "status": "issued",
        "created_at": now(),
        "route": route,
        "scene_id": work_id,
        "target_id": work_id,
        "work_id": work_id,
        "chunk_id": chunk_id,
        "current_state": current_state,
        "task_type": blueprint["task_type"],
        "prompt_asset_id": blueprint["prompt_asset_id"],
        "command": blueprint["command"],
        "required_reading": blueprint.get("required_reading", SOURCE_INGEST_REQUIRED_READING),
        "source_paths": sources,
        "context_trace": blueprint.get("context_trace", ""),
        "hard_constraints": blueprint["hard_constraints"],
        "style_constraints": blueprint["style_constraints"],
        "word_count_target": 0,
        "word_count_min": 0,
        "word_count_max": 0,
        "expected_outputs": expected,
        "submission_command": (
            "python -m literary_engineering_studio_engine task-submit "
            f"<project> --task-id {identifier} --from <artifact>"
        ),
        "completion_command": (
            "python -m literary_engineering_studio_engine task-complete "
            f"<project> --task-id {identifier}"
        ),
        "validation_gates": blueprint["validation_gates"],
        "forbidden_shortcuts": SOURCE_INGEST_FORBIDDEN_SHORTCUTS,
        "next_allowed_states": blueprint["next_allowed_states"],
    }


def _attach_optional_contract(
    root: Path,
    payload: dict[str, object],
    blueprint: dict[str, object],
) -> None:
    owned = blueprint.get("system_owned_fields")
    if isinstance(owned, dict):
        payload["system_owned_fields"] = owned
    agent_sources = blueprint.get("agent_source_paths")
    if isinstance(agent_sources, list):
        payload["agent_source_paths"] = unique(
            [normalize_relative_path(item) for item in agent_sources]
        )
    repair_targets = [str(item) for item in blueprint.get("repair_targets", [])]
    if not repair_targets:
        return
    payload["repair_targets"] = repair_targets
    payload["repair_target_sha256_before_revision"] = {
        relative: file_sha256(resolve_project_path(root, relative))
        for relative in repair_targets
        if resolve_project_path(root, relative).is_file()
    }


def blueprint_for_state(
    root: Path,
    work_id: str,
    import_dir: str,
    current_state: str,
    next_action: str,
    *,
    state: dict[str, object] | None = None,
) -> dict[str, object]:
    manifest = read_json(root / import_dir / "source_manifest.json")
    context = _blueprint_context(manifest, work_id, import_dir)
    table = {
        "source-manifest": _source_manifest_blueprint(import_dir, context),
        "chunk-extraction-agent-task": _chunk_extraction_blueprint(
            root,
            work_id,
            import_dir,
            manifest,
            state or {},
        ),
        "archaeology-fan-in": _fan_in_blueprint(work_id, import_dir, manifest),
        "archaeology-resolution-agent-task": _resolution_blueprint(
            work_id,
            import_dir,
            manifest,
        ),
        "archaeology-reconstruction-agent-task": _reconstruction_blueprint(
            work_id,
            import_dir,
            manifest,
        ),
        "archaeology-domain-review-agent-task": _domain_review_blueprint(
            work_id,
            import_dir,
            manifest,
        ),
        "archaeology-materialize": _materialization_blueprint(
            work_id,
            import_dir,
            manifest,
        ),
        "extraction-agent-task": _whole_book_extraction_blueprint(context),
        "extraction-review": _extraction_review_blueprint(context),
    }
    if isinstance(manifest.get("archaeology"), dict):
        table["source-manifest"]["next_allowed_states"] = [
            "chunk-extraction-agent-task"
        ]
    return table.get(
        current_state,
        _repair_blueprint(import_dir, context["report"], next_action),
    )


def _blueprint_context(
    manifest: dict[str, object],
    work_id: str,
    import_dir: str,
) -> dict[str, object]:
    outputs = candidate_outputs_from_manifest(manifest, work_id)
    archaeology = manifest.get("archaeology")
    aggregate = (
        str(archaeology.get("aggregate_path") or "")
        if isinstance(archaeology, dict)
        else ""
    )
    task_path = f"{import_dir}/extract_project_files.agent_tasks.md"
    report = f"{import_dir}/source_ingest.md"
    evidence = evidence_path_from_manifest(manifest)
    chunks = [
        str(item.get("path") or "")
        for item in manifest.get("chunks", [])
        if isinstance(item, dict)
    ]
    return {
        "schema": str(manifest.get("schema") or ""),
        "outputs": outputs,
        "values": list(outputs.values()),
        "review": outputs.get(
            "review",
            f"reviews/source_ingest/{work_id}_extraction_review.md",
        ),
        "task_path": task_path,
        "completion": f"{import_dir}/extract_project_files.agent_completion.json",
        "report": report,
        "evidence": evidence,
        "chunks": chunks,
        "aggregate": aggregate,
        "sources": extraction_source_paths(
            import_dir,
            report,
            task_path,
            evidence,
            chunks,
            aggregate_path=aggregate,
        ),
    }


def _source_manifest_blueprint(
    import_dir: str,
    context: dict[str, object],
) -> dict[str, object]:
    return {
        "task_type": "deterministic-cli-or-repair",
        "prompt_asset_id": "route.source-ingest.import.v1",
        "command": (
            "python -m literary_engineering_studio_engine source-ingest "
            "<project> --source <source> --title <title> --work-id <work-id> "
            "--rights-declaration <declaration>"
        ),
        "source_paths": ["project.yaml"],
        "expected_outputs": [
            f"{import_dir}/source_manifest.json",
            context["report"],
            f"{import_dir}/evidence_index.json",
            context["task_path"],
        ],
        "hard_constraints": [
            "Run source-ingest with explicit source/text/title/work-id when starting a new import.",
            "Record a rights declaration and preserve immutable source bytes, extracted text, ranges, and hashes.",
            "If repairing an invalid manifest, preserve source evidence and candidate output paths.",
        ],
        "style_constraints": [],
        "validation_gates": [
            "source manifest exists",
            "source ingest report exists",
            "extraction sidecar exists",
            "source_manifest schema is valid",
        ],
        "next_allowed_states": ["extraction-agent-task"],
    }


def _whole_book_extraction_blueprint(
    context: dict[str, object],
) -> dict[str, object]:
    source_instruction, compatibility_constraint, _ = source_ingest_contract_language(
        str(context["schema"])
    )
    return {
        "task_type": "platform-agent-extraction",
        "prompt_asset_id": "route.source-ingest.extract-project-files.v1",
        "command": "",
        "source_paths": context["sources"],
        "expected_outputs": [*context["values"], context["completion"]],
        "hard_constraints": [
            source_instruction,
            compatibility_constraint,
            "Preserve every unresolved alias, claim, and timeline alternative; do not silently choose a majority interpretation.",
            "Every extracted claim must include evidence_refs, confidence, unknowns, and contradiction notes when relevant.",
            "Write only candidate assets and source-ingest review; do not overwrite confirmed project files.",
        ],
        "style_constraints": [
            "For style notes from non-public-domain or unauthorized sources, abstract high-level craft features only."
        ],
        "validation_gates": [
            "extraction sidecar completion marker exists",
            "all candidate outputs exist",
        ],
        "next_allowed_states": ["extraction-review"],
    }


def _extraction_review_blueprint(
    context: dict[str, object],
) -> dict[str, object]:
    review = str(context["review"])
    candidate_values = [str(item) for item in context["values"]]
    candidates = [item for item in candidate_values if item != review]
    _, _, compatibility_constraint = source_ingest_contract_language(
        str(context["schema"])
    )
    return {
        "task_type": "platform-agent-revision",
        "prompt_asset_id": "route.source-ingest.extraction-review.v1",
        "command": "",
        "source_paths": [
            str(context["sources"][1]),
            str(context["evidence"]),
            *[str(item) for item in context["chunks"]],
            *candidates,
            review,
        ],
        "expected_outputs": [*candidates, review],
        "repair_targets": candidates,
        "hard_constraints": [
            compatibility_constraint,
            "Revise the extracted candidate files against every review finding, then rewrite the review honestly.",
            "At least one declared extracted candidate must change; editing only the review conclusion is forbidden.",
            "The extraction review must be a clean pass before source-derived candidates are treated as route-ready.",
            "pass_with_notes, missing evidence, copied long passages, or direct canon writeback are blocking.",
        ],
        "style_constraints": [],
        "validation_gates": [
            "source-ingest extraction review conclusion is pass"
        ],
        "next_allowed_states": ["ready"],
    }


def _chunk_extraction_blueprint(
    root: Path,
    work_id: str,
    import_dir: str,
    manifest: dict[str, object],
    state: dict[str, object],
) -> dict[str, object]:
    item = active_chunk_plan(manifest, str(state.get("chunk_id") or ""))
    chunk_path = str(item.get("source_chunk_path") or "")
    task_path = str(item.get("task_path") or "")
    evidence_path = evidence_path_from_manifest(manifest)
    identity = _chunk_identity(root, work_id, manifest, item)
    agent_sources = [
        "project.yaml",
        f"{import_dir}/source_manifest.json",
        evidence_path,
        chunk_path,
    ]
    return {
        "task_type": "platform-agent-extraction",
        "prompt_asset_id": "route.source-ingest.chunk-extraction.v1",
        "command": "",
        "source_paths": [*agent_sources, task_path],
        "agent_source_paths": agent_sources,
        "expected_outputs": [
            str(item.get("expected_output") or ""),
            str(item.get("completion_path") or ""),
        ],
        "hard_constraints": [
            "Analyze only the declared source chunk and its evidence ids.",
            "Write entities, events, relations, and claims as evidence-bound candidates.",
            "Do not merge same-name observations or invent cross-chunk identity.",
            "Preserve unknowns and contradiction notes.",
        ],
        "style_constraints": [],
        "validation_gates": [
            "chunk extraction JSON matches the exact chunk and evidence revision",
            "chunk extraction sidecar completion marker exists",
        ],
        "next_allowed_states": [
            "chunk-extraction-agent-task",
            "archaeology-fan-in",
        ],
        "system_owned_fields": {"archaeology": identity},
    }


def _chunk_identity(
    root: Path,
    work_id: str,
    manifest: dict[str, object],
    item: dict[str, object],
) -> dict[str, str]:
    chunk_path = str(item.get("source_chunk_path") or "")
    source = resolve_project_path(root, chunk_path) if chunk_path else None
    evidence = manifest.get("evidence_index")
    return {
        "schema": "arcvellum/project-archaeology-chunk-extraction/v1",
        "work_id": work_id,
        "chunk_id": str(item.get("chunk_id") or ""),
        "source_chunk_path": chunk_path,
        "source_chunk_sha256": (
            file_sha256(source) if source is not None and source.is_file() else ""
        ),
        "evidence_revision": (
            str(evidence.get("revision") or "") if isinstance(evidence, dict) else ""
        ),
        "status": "complete",
    }


def _fan_in_blueprint(
    work_id: str,
    import_dir: str,
    manifest: dict[str, object],
) -> dict[str, object]:
    archaeology = manifest.get("archaeology")
    plan = archaeology.get("chunk_tasks") if isinstance(archaeology, dict) else []
    aggregate = (
        str(archaeology.get("aggregate_path") or "")
        if isinstance(archaeology, dict)
        else f"{import_dir}/extractions/aggregate.json"
    )
    sources = [
        f"{import_dir}/source_manifest.json",
        evidence_path_from_manifest(manifest),
        *_fan_in_sources(plan),
    ]
    return {
        "task_type": "deterministic-cli",
        "prompt_asset_id": "route.source-ingest.aggregate.v1",
        "command": (
            "python -m literary_engineering_studio_engine archaeology-aggregate "
            f"<project> --work-id {work_id}"
        ),
        "source_paths": sources,
        "expected_outputs": [aggregate],
        "hard_constraints": [
            "Run only after every chunk extraction and completion receipt passes.",
            "Do not edit the deterministic aggregate by hand.",
            "Do not merge aliases or suppress conflicting alternatives.",
        ],
        "style_constraints": [],
        "validation_gates": [
            "all declared chunk extraction tasks are complete",
            "archaeology aggregate exactly matches current chunk outputs",
            "fan-in status is ready",
        ],
        "next_allowed_states": ["archaeology-resolution-agent-task"],
    }


def _fan_in_sources(plan: object) -> list[str]:
    sources: list[str] = []
    for item in plan if isinstance(plan, list) else []:
        if isinstance(item, dict):
            sources.extend(
                [
                    str(item.get("source_chunk_path") or ""),
                    str(item.get("expected_output") or ""),
                    str(item.get("completion_path") or ""),
                ]
            )
    return sources


def _repair_blueprint(
    import_dir: str,
    report: object,
    next_action: str,
) -> dict[str, object]:
    return {
        "task_type": "route-diagnostic-boundary",
        "prompt_asset_id": "route.source-ingest.repair.v1",
        "command": next_action,
        "source_paths": [f"{import_dir}/source_manifest.json", str(report)],
        "expected_outputs": [],
        "hard_constraints": [
            next_action
            or "Inspect workflow-state and route-audit, then repair the missing source-ingest gate."
        ],
        "style_constraints": [],
        "validation_gates": ["source-ingest gate resolved"],
        "next_allowed_states": [],
    }
