"""Canonical style source text normalization and content digest."""

from __future__ import annotations

import hashlib


def normalize_source_text(text: str) -> str:
    """Normalize stored source text without changing its wording.

    Line breaks inside a paragraph are collapsed; blank-line-separated
    paragraphs are joined with a single blank line.  This is the exact text
    that is written to the normalized source file.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in text.splitlines()]
    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines:
        if not line:
            if current:
                paragraphs.append("".join(current))
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append("".join(current))
    return "\n\n".join(paragraphs)


def source_content_digest(text: str) -> str:
    """Canonical SHA-256 of normalized style source content."""
    return hashlib.sha256(
        normalize_source_text(text).encode("utf-8")
    ).hexdigest()
