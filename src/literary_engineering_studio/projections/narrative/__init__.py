"""Contracts and pure helpers for the living narrative read model."""

from .contracts import NarrativeFocusLevel, NarrativeFocusScope
from .focus import resolve_narrative_focus_scope

__all__ = [
    "NarrativeFocusLevel",
    "NarrativeFocusScope",
    "resolve_narrative_focus_scope",
]
