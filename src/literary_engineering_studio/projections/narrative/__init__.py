"""Contracts and pure helpers for the living narrative read model."""

from .contracts import (
    NarrativeFocusLevel,
    NarrativeFocusScope,
    RelationFamily,
    RelationFocusState,
    RelationLodMode,
    RelationVisibilityProfile,
)
from .characters import (
    CharacterReference,
    CharacterReferenceResolution,
    augment_character_graph,
    build_character_references,
)
from .focus import resolve_narrative_focus_scope

__all__ = [
    "CharacterReference",
    "CharacterReferenceResolution",
    "NarrativeFocusLevel",
    "NarrativeFocusScope",
    "RelationFamily",
    "RelationFocusState",
    "RelationLodMode",
    "RelationVisibilityProfile",
    "augment_character_graph",
    "build_character_references",
    "resolve_narrative_focus_scope",
]
