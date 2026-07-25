"""Stable revision metadata for the composite project workspace read model."""

from __future__ import annotations

import hashlib
import json
from typing import Any


WORKSPACE_SECTION_NAMES = (
    "dashboard",
    "library",
    "delivery",
    "reader_manifest",
    "project_progress",
    "autopilot_status",
    "agent_observability",
)


def build_workspace_revisions(sections: dict[str, Any]) -> tuple[dict[str, str], str]:
    """Return per-section and aggregate revisions without changing section data."""

    revisions = {
        name: _section_revision(name, sections.get(name))
        for name in WORKSPACE_SECTION_NAMES
    }
    return revisions, _digest(revisions)


def _section_revision(name: str, value: Any) -> str:
    payload = value if isinstance(value, dict) else {}
    if name == "reader_manifest":
        explicit = payload.get("project_revision")
    else:
        explicit = payload.get("revision")
    return str(explicit or _digest(payload))


def _digest(value: Any) -> str:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20]
