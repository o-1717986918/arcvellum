"""Stable project and project-filesystem operations used by Studio."""

from ..foundation.atomic_io import atomic_write_batch, atomic_write_text
from ..foundation.resources import engine_root
from ..projects.init import InitOptions, init_work_project
from ..projects.source_ingest import (
    INGEST_MODES,
    TEXT_EXTENSIONS,
    ingest_existing_work,
)

__all__ = [
    "INGEST_MODES",
    "TEXT_EXTENSIONS",
    "InitOptions",
    "atomic_write_batch",
    "atomic_write_text",
    "engine_root",
    "ingest_existing_work",
    "init_work_project",
]
