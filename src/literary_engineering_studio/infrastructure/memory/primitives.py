"""Injectable clock and identity primitives for memory adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import itertools
import uuid


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class UuidIdGenerator:
    def new_id(self, prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:16]}"


@dataclass
class FrozenClock:
    value: datetime

    def now(self) -> datetime:
        return self.value


class SequenceIdGenerator:
    def __init__(self, start: int = 1):
        self._values = itertools.count(max(1, int(start)))

    def new_id(self, prefix: str) -> str:
        return f"{prefix}-{next(self._values):016d}"


def iso_now(clock) -> str:
    value = clock.now()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


__all__ = [
    "FrozenClock",
    "SequenceIdGenerator",
    "SystemClock",
    "UuidIdGenerator",
    "iso_now",
]
