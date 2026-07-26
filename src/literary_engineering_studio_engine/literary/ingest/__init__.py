"""Deterministic source preservation and evidence contracts."""

from .contracts import (
    EXTRACTOR_VERSION,
    SOURCE_INGEST_SCHEMA_V2,
    SourceChunk,
    SourceDocument,
    SourceEvidenceRef,
    SourceRange,
    SourceSegment,
)
from .evidence import build_evidence_index, import_revision, verify_ingest_manifest
from .entities import (
    CHUNK_EXTRACTION_SCHEMA,
    chunk_extraction_path,
    validate_chunk_extraction,
)
from .importer import (
    StagedSourceImport,
    commit_import,
    recover_interrupted_import,
    stage_source_import,
)
from .readers import SUPPORTED_SOURCE_EXTENSIONS, read_source_documents
from .reconstruction import (
    ARCHAEOLOGY_AGGREGATE_SCHEMA,
    aggregate_chunk_extractions,
    build_chunk_extraction_plan,
    verify_archaeology_aggregate,
    write_archaeology_aggregate,
)
from .segmentation import build_source_chunks, segment_documents

__all__ = [
    "EXTRACTOR_VERSION",
    "ARCHAEOLOGY_AGGREGATE_SCHEMA",
    "CHUNK_EXTRACTION_SCHEMA",
    "SOURCE_INGEST_SCHEMA_V2",
    "SUPPORTED_SOURCE_EXTENSIONS",
    "SourceChunk",
    "SourceDocument",
    "SourceEvidenceRef",
    "SourceRange",
    "SourceSegment",
    "StagedSourceImport",
    "build_evidence_index",
    "build_chunk_extraction_plan",
    "build_source_chunks",
    "commit_import",
    "import_revision",
    "read_source_documents",
    "recover_interrupted_import",
    "segment_documents",
    "stage_source_import",
    "aggregate_chunk_extractions",
    "chunk_extraction_path",
    "validate_chunk_extraction",
    "verify_archaeology_aggregate",
    "verify_ingest_manifest",
    "write_archaeology_aggregate",
]
