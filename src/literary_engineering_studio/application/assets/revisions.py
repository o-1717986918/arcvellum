"""Content revisions for Archive optimistic concurrency."""

from __future__ import annotations

import hashlib


def content_revision(content: str) -> str:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
