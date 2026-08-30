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

__all__ = [
    "count_delivery_chars",
    "count_delivery_chinese_content_chars",
    "display_counts",
    "final_body_from_workbench_text",
    "load_authorized_reader_units",
    "markdown_to_display_text",
    "read_authorized_reader_body",
    "scalar_from_yaml_text",
]
