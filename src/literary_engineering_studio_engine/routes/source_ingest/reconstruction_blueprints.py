"""Project Archaeology reconstruction and materialization task blueprints."""

from __future__ import annotations

from ...literary.ingest import (
    DOMAIN_REVIEW_SCHEMA,
    IDENTITY_RESOLUTION_SCHEMA,
    RECONSTRUCTION_CANDIDATE_SCHEMA,
    reconstruction_paths,
)
from .support import evidence_path_from_manifest


def resolution_blueprint(
    work_id: str,
    import_dir: str,
    manifest: dict[str, object],
) -> dict[str, object]:
    paths = reconstruction_paths(import_dir)
    aggregate = aggregate_path(manifest, import_dir)
    evidence = evidence_path_from_manifest(manifest)
    return {
        "task_type": "platform-agent-archaeology-resolution",
        "prompt_asset_id": "route.source-ingest.resolve-identities.v1",
        "command": "",
        "source_paths": [
            "project.yaml",
            f"{import_dir}/source_manifest.json",
            evidence,
            aggregate,
            paths["resolution_task"],
        ],
        "agent_source_paths": [
            "project.yaml",
            f"{import_dir}/source_manifest.json",
            evidence,
            aggregate,
        ],
        "expected_outputs": [
            paths["resolution"],
            paths["resolution_report"],
            paths["resolution_completion"],
        ],
        "hard_constraints": [
            "Account for every entity occurrence and aggregate conflict exactly once.",
            "Resolve identity only from evidence; unresolved, partial, and keep_distinct are valid outcomes.",
            "Do not turn any resolution into Canon or an Archive candidate.",
        ],
        "style_constraints": [],
        "validation_gates": [
            "identity resolution matches current aggregate revision",
            "every occurrence and conflict is covered exactly once",
            "identity resolution sidecar completion marker exists",
        ],
        "next_allowed_states": ["archaeology-reconstruction-agent-task"],
        "system_owned_fields": {
            "archaeology_resolution": {
                "schema": IDENTITY_RESOLUTION_SCHEMA,
                "work_id": work_id,
                "status": "complete",
            }
        },
    }


def reconstruction_blueprint(
    work_id: str,
    import_dir: str,
    manifest: dict[str, object],
) -> dict[str, object]:
    paths = reconstruction_paths(import_dir)
    aggregate = aggregate_path(manifest, import_dir)
    mode = str(manifest.get("mode") or "continuation")
    evidence = evidence_path_from_manifest(manifest)
    return {
        "task_type": "platform-agent-archaeology-reconstruction",
        "prompt_asset_id": "route.source-ingest.reconstruct-project.v1",
        "command": "",
        "source_paths": [
            "project.yaml",
            f"{import_dir}/source_manifest.json",
            evidence,
            aggregate,
            paths["resolution"],
            paths["candidate_task"],
        ],
        "agent_source_paths": [
            "project.yaml",
            f"{import_dir}/source_manifest.json",
            evidence,
            aggregate,
            paths["resolution"],
        ],
        "expected_outputs": [
            paths["candidate"],
            paths["candidate_report"],
            paths["candidate_completion"],
        ],
        "hard_constraints": [
            "Reconstruct a candidate project for the declared mode without inventing missing source facts.",
            "Keep character, world, plot, style, and promise observations separate and evidence-bound.",
            "Archive assets must use registered candidate schemas; analysis mode may not recommend promotion.",
        ],
        "style_constraints": [
            "Style observations must describe reusable craft constraints and may not promise exact imitation of protected work."
        ],
        "validation_gates": [
            "reconstruction matches current aggregate and identity resolution",
            "all Archive assets validate against registered schemas",
            "all domain observations cite current evidence",
        ],
        "next_allowed_states": ["archaeology-domain-review-agent-task"],
        "system_owned_fields": {
            "archaeology_reconstruction": {
                "schema": RECONSTRUCTION_CANDIDATE_SCHEMA,
                "work_id": work_id,
                "mode": mode,
                "status": "candidate",
            }
        },
    }


def domain_review_blueprint(
    work_id: str,
    import_dir: str,
    manifest: dict[str, object],
) -> dict[str, object]:
    paths = reconstruction_paths(import_dir)
    mode = str(manifest.get("mode") or "continuation")
    evidence = evidence_path_from_manifest(manifest)
    aggregate = aggregate_path(manifest, import_dir)
    return {
        "task_type": "platform-agent-archaeology-domain-review",
        "prompt_asset_id": "route.source-ingest.review-reconstruction.v1",
        "command": "",
        "source_paths": [
            f"{import_dir}/source_manifest.json",
            evidence,
            aggregate,
            paths["resolution"],
            paths["candidate"],
            paths["review_task"],
        ],
        "agent_source_paths": [
            f"{import_dir}/source_manifest.json",
            evidence,
            aggregate,
            paths["resolution"],
            paths["candidate"],
        ],
        "expected_outputs": [
            paths["review"],
            paths["review_report"],
            paths["review_completion"],
        ],
        "hard_constraints": [
            "Review character, world, plot, style, promise, and every proposed Archive asset.",
            "A pass cannot retain blocking issues; an asset with blockers cannot receive promote.",
            "This is an archaeology evidence review, not Archive promotion approval.",
            "Analysis mode requires analysis_only for every asset decision.",
        ],
        "style_constraints": [],
        "validation_gates": [
            "all archaeology domains receive an independent review",
            "every proposed asset receives exactly one decision",
            "domain review conclusion is pass before materialization",
        ],
        "next_allowed_states": [
            "archaeology-materialize" if mode != "analysis" else "ready"
        ],
        "system_owned_fields": {
            "archaeology_domain_review": {
                "schema": DOMAIN_REVIEW_SCHEMA,
                "work_id": work_id,
                "mode": mode,
            }
        },
    }


def materialization_blueprint(
    work_id: str,
    import_dir: str,
    manifest: dict[str, object],
) -> dict[str, object]:
    paths = reconstruction_paths(import_dir)
    return {
        "task_type": "deterministic-cli",
        "prompt_asset_id": "route.source-ingest.materialize-candidates.v1",
        "command": (
            "python -m literary_engineering_studio_engine archaeology-materialize "
            f"<project> --work-id {work_id}"
        ),
        "source_paths": [
            f"{import_dir}/source_manifest.json",
            aggregate_path(manifest, import_dir),
            paths["resolution"],
            paths["candidate"],
            paths["review"],
        ],
        "expected_outputs": [
            paths["materialization"],
            paths["materialization_report"],
        ],
        "hard_constraints": [
            "Materialize only assets with both promote recommendation and promote domain-review decision.",
            "Write only registered Archive candidate directories and deterministic provenance receipts.",
            "Do not write formal Canon, characters, outline, scenes, drafts, exports, or releases.",
        ],
        "style_constraints": [],
        "validation_gates": [
            "current archaeology evidence and all reconstruction revisions match",
            "analysis mode cannot enter materialization",
            "materialized assets remain Archive candidates requiring independent review and approval",
        ],
        "next_allowed_states": ["ready"],
    }


def aggregate_path(manifest: dict[str, object], import_dir: str) -> str:
    archaeology = manifest.get("archaeology")
    if isinstance(archaeology, dict):
        return str(archaeology.get("aggregate_path") or "")
    return f"{import_dir}/extractions/aggregate.json"
