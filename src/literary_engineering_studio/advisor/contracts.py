"""Stable answer protocol constants for the project advisor."""

ANSWER_SCHEMA = "arcvellum/advisor-answer/v0.2"
METADATA_MARKER = "<<<ARCVELLUM_META>>>"
METADATA_END = "<<<END_ARCVELLUM_META>>>"
ALLOWED_ACTIONS = {
    "open_view",
    "record_direction",
    "run_next_task",
    "prepare_next_task",
    "start_autopilot",
    "pause_autopilot",
    "resume_autopilot",
    "request_revision",
}


__all__ = ["ALLOWED_ACTIONS", "ANSWER_SCHEMA", "METADATA_END", "METADATA_MARKER"]
