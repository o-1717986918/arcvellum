"""Compatibility facade for read-only project-library projections."""

from __future__ import annotations

from .projections.library.common import PROJECT_LIBRARY_SCHEMA
from .projections.library.service import build_project_library, find_project_library_item

__all__ = ["PROJECT_LIBRARY_SCHEMA", "build_project_library", "find_project_library_item"]
