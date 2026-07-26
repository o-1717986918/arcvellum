"""Registered candidate asset identities shared by creation and ingestion."""

from __future__ import annotations

from pathlib import Path


ASSET_SCHEMA_NAMES = {
    "character": "character_profile.v1",
    "background-story": "background_story.v1",
    "relationship": "relationship_graph.v1",
    "world": "world_rules.v1",
    "location": "location.v1",
    "organization": "organization.v1",
    "outline": "plot_outline.v1",
    "chapter-plan": "plot_outline.v1",
    "scene-list": "plot_outline.v1",
}

ASSET_CANDIDATE_DIRS = {
    "character": Path("characters/candidates"),
    "background-story": Path("characters/candidates/background_stories"),
    "relationship": Path("plot/candidates/relationships"),
    "world": Path("canon/candidates/world_rules"),
    "location": Path("canon/candidates/locations"),
    "organization": Path("canon/candidates/organizations"),
    "outline": Path("plot/candidates/outlines"),
    "chapter-plan": Path("plot/candidates/outlines"),
    "scene-list": Path("plot/candidates/outlines"),
}

PROMOTABLE_GROUPS = {
    "character": {"character", "background-story", "relationship"},
    "world": {"world", "location", "organization"},
    "outline": {"outline", "chapter-plan", "scene-list"},
}

ASSET_TYPES = tuple(ASSET_SCHEMA_NAMES)
