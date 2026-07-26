"""Built-in capability handler registry."""

from __future__ import annotations

from ..contracts import CapabilityId
from ..registry import CapabilityRegistry
from .diff import asset_diff
from .project import project_query, schema_inspect
from .text import citation_lookup, reference_search, text_statistics
from .web import research_web


def build_default_registry() -> CapabilityRegistry:
    registry = CapabilityRegistry()
    registry.register(CapabilityId.PROJECT_QUERY, project_query)
    registry.register(CapabilityId.SCHEMA_INSPECT, schema_inspect)
    registry.register(CapabilityId.TEXT_STATISTICS, text_statistics)
    registry.register(CapabilityId.CITATION_LOOKUP, citation_lookup)
    registry.register(CapabilityId.REFERENCE_SEARCH, reference_search)
    registry.register(CapabilityId.RESEARCH_WEB, research_web)
    registry.register(CapabilityId.ASSET_DIFF, asset_diff)
    return registry


__all__ = ["build_default_registry"]
