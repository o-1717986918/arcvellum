"""Stable source-ingest route surface.

Blueprint construction, Gate validation, and path helpers remain separate so
Project Archaeology can evolve without turning the route into a second
workflow engine.
"""

from .blueprints import build_task_payload, blueprint_for_state
from .gates import (
    archaeology_fan_in_gate_errors,
    chunk_extraction_gate_errors,
    extraction_gate_errors,
    extraction_revision_gate_errors,
    manifest_gate_errors,
    validate_task,
)
from .support import (
    SOURCE_INGEST_SCHEMA_V1,
    SOURCE_INGEST_SCHEMA_V2,
    SOURCE_INGEST_SCHEMAS,
    candidate_outputs_from_manifest,
    evidence_path_from_manifest,
    extraction_source_paths,
    import_dir_for_task,
)


__all__ = [
    "SOURCE_INGEST_SCHEMA_V1",
    "SOURCE_INGEST_SCHEMA_V2",
    "SOURCE_INGEST_SCHEMAS",
    "archaeology_fan_in_gate_errors",
    "blueprint_for_state",
    "build_task_payload",
    "candidate_outputs_from_manifest",
    "chunk_extraction_gate_errors",
    "evidence_path_from_manifest",
    "extraction_gate_errors",
    "extraction_revision_gate_errors",
    "extraction_source_paths",
    "import_dir_for_task",
    "manifest_gate_errors",
    "validate_task",
]
