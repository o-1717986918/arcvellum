"""Compatibility facade for frontend-safe project interaction."""

from __future__ import annotations

from .project_interaction_editing import build_editable_schema, record_ui_note, save_display_field
from .project_interaction_choices import (
    build_current_human_choices, finalize_human_choice, record_human_choice,
)

__all__ = [
    "build_editable_schema", "build_current_human_choices", "finalize_human_choice",
    "record_human_choice", "record_ui_note", "save_display_field",
]
