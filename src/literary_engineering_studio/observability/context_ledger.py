"""Immutable metadata proving what an Agent context actually contained."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Literal


CONTEXT_LEDGER_SCHEMA = "arcvellum/context-ledger/v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TRUTH_PARTITIONS = {
    "historical_truth",
    "current_state",
    "stable_knowledge",
    "future_intent",
    "evidence_and_opinion",
}


@dataclass(frozen=True)
class ContextLedgerEntry:
    source_ref: str
    title: str
    purpose: str
    partition: str
    byte_count: int
    character_count: int
    sha256: str
    included: bool
    truncated: bool
    limit: int | None
    unit: Literal["bytes", "characters", "tokens"]
    preview: str
    note: str = ""

    def __post_init__(self) -> None:
        if not self.source_ref.strip() or not self.title.strip() or not self.purpose.strip():
            raise ValueError("context ledger source_ref, title, and purpose are required")
        if self.byte_count < 0 or self.character_count < 0:
            raise ValueError("context ledger counts cannot be negative")
        if not _SHA256.fullmatch(self.sha256):
            raise ValueError("context ledger entry sha256 is invalid")
        if self.partition not in _TRUTH_PARTITIONS:
            raise ValueError(f"unsupported context truth partition: {self.partition}")
        if self.limit is not None and self.limit < 0:
            raise ValueError("context ledger limit cannot be negative")
        if len(self.preview) > 320:
            raise ValueError("context ledger preview exceeds the safe metadata limit")
        if self.truncated and not self.included:
            raise ValueError("an excluded context source cannot be marked truncated")

    def as_dict(self) -> dict[str, object]:
        return {
            "source_ref": self.source_ref,
            "title": self.title,
            "purpose": self.purpose,
            "partition": self.partition,
            "byte_count": self.byte_count,
            "character_count": self.character_count,
            "sha256": self.sha256,
            "included": self.included,
            "truncated": self.truncated,
            "limit": self.limit,
            "unit": self.unit,
            "preview": self.preview,
            "note": self.note,
        }


@dataclass(frozen=True)
class ContextLedger:
    ledger_id: str
    project_root_hash: str
    session_id: str
    operation_id: str
    plan_id: str
    entries: tuple[ContextLedgerEntry, ...]
    assembled_sha256: str

    def __post_init__(self) -> None:
        for field_name, value in (
            ("ledger_id", self.ledger_id),
            ("project_root_hash", self.project_root_hash),
            ("session_id", self.session_id),
            ("operation_id", self.operation_id),
        ):
            if not value.strip():
                raise ValueError(f"context ledger {field_name} is required")
        if not _SHA256.fullmatch(self.assembled_sha256):
            raise ValueError("context ledger assembled_sha256 is invalid")
        if len({entry.source_ref for entry in self.entries}) != len(self.entries):
            raise ValueError("context ledger contains duplicate source refs")

    @property
    def digest(self) -> str:
        return _digest(self._body())

    def _body(self) -> dict[str, object]:
        return {
            "schema": CONTEXT_LEDGER_SCHEMA,
            "ledger_id": self.ledger_id,
            "project_root_hash": self.project_root_hash,
            "session_id": self.session_id,
            "operation_id": self.operation_id,
            "plan_id": self.plan_id,
            "entries": [entry.as_dict() for entry in self.entries],
            "assembled_sha256": self.assembled_sha256,
        }

    def as_dict(self) -> dict[str, object]:
        return {**self._body(), "digest": self.digest}


def context_ledger_id(
    *,
    project_root_hash: str,
    session_id: str,
    operation_id: str,
    assembled_sha256: str,
) -> str:
    suffix = _digest(
        {
            "project_root_hash": project_root_hash,
            "session_id": session_id,
            "operation_id": operation_id,
            "assembled_sha256": assembled_sha256,
        }
    )[:24]
    return f"context-{suffix}"


def _digest(value: object) -> str:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
