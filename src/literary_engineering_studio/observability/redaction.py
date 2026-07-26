"""Small user-safe text projections for observability metadata."""

from __future__ import annotations

import re


def redact_preview(value: str, *, limit: int = 320) -> str:
    compact = " ".join(value.replace("\x00", "").split())
    compact = re.sub(
        r"(?i)\b(api[_-]?key|access[_-]?key|password|secret|token)\b\s*[:=]\s*[^\s,;]+",
        r"\1=[REDACTED]",
        compact,
    )
    compact = re.sub(r"\bsk-[A-Za-z0-9_-]{12,}\b", "[REDACTED]", compact)
    return compact[: max(0, int(limit))]
