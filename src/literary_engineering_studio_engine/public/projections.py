"""Stable reader-facing text and display projection API."""

from ..foundation.display_cleaner import (
    display_counts,
    markdown_to_display_text,
    scalar_from_yaml_text,
)
from ..foundation.draft_text import (
    count_delivery_chars,
    count_delivery_chinese_content_chars,
    final_body_from_workbench_text,
)
from ..literary.ingest.authorized import (
    load_authorized_reader_units,
    read_authorized_reader_body,
)
from ..projections.interaction.choices import (
    build_current_human_choices,
    finalize_human_choice,
    record_human_choice,
)
from ..projections.interaction.editing import record_ui_note, save_display_field
from ..projections.library.service import build_narrative_evidence, build_project_library

__all__ = [
    "build_current_human_choices",
    "build_narrative_evidence",
    "build_project_library",
    "count_delivery_chars",
    "count_delivery_chinese_content_chars",
    "display_counts",
    "final_body_from_workbench_text",
    "finalize_human_choice",
    "load_authorized_reader_units",
    "markdown_to_display_text",
    "read_authorized_reader_body",
    "record_human_choice",
    "record_ui_note",
    "save_display_field",
    "scalar_from_yaml_text",
]
