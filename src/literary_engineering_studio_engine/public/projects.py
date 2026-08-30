"""Stable project and project-filesystem operations used by Studio."""

from ..foundation.atomic_io import atomic_write_batch, atomic_write_text
from ..foundation.resources import engine_root
from ..literary.ingest.authorized import DistributionScope
from ..projects.init import InitOptions, init_work_project
from ..projects.source_ingest import (
    INGEST_MODES,
    TEXT_EXTENSIONS,
    ingest_existing_work,
)
from ..projects.authorized_demo import (
    AUTHORIZED_DEMO_PROJECT_SCHEMA,
    AuthorizedDemoProjectResult,
    build_authorized_demo_project,
    is_authorized_demo_reference,
    load_authorized_work_manifest,
    seal_authorized_demo_project,
)

__all__ = [
    "INGEST_MODES",
    "AUTHORIZED_DEMO_PROJECT_SCHEMA",
    "TEXT_EXTENSIONS",
    "AuthorizedDemoProjectResult",
    "DistributionScope",
    "InitOptions",
    "atomic_write_batch",
    "atomic_write_text",
    "build_authorized_demo_project",
    "engine_root",
    "ingest_existing_work",
    "init_work_project",
    "is_authorized_demo_reference",
    "load_authorized_work_manifest",
    "seal_authorized_demo_project",
]
