"""Default clock and identity implementations for SQLite persistence."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class UuidIdGenerator:
    def new_id(self, prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:16]}"


def utc_now(clock) -> datetime:
    value = clock.now()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def iso_now(clock) -> str:
    return utc_now(clock).isoformat()


__all__ = ["SystemClock", "UuidIdGenerator", "iso_now", "utc_now"]
