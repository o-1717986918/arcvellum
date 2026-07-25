"""Compatibility facade for read-only project-library projections."""

from __future__ import annotations

from .projections.library.common import PROJECT_LIBRARY_SCHEMA
from .projections.library.service import (
    NARRATIVE_EVIDENCE_SCHEMA,
    build_narrative_evidence,
    build_project_library,
    find_project_library_item,
)

__all__ = [
    "NARRATIVE_EVIDENCE_SCHEMA",
    "PROJECT_LIBRARY_SCHEMA",
    "build_narrative_evidence",
    "build_project_library",
    "find_project_library_item",
]
