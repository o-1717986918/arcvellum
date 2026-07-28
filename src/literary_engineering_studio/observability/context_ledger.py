"""Immutable metadata proving what an Agent context actually contained."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Literal


CONTEXT_LEDGER_SCHEMA = "arcvellum/context-ledger/v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TRUTH_PARTITIONS = {
    "historical_truth",
    "current_state",
    "stable_knowledge",
    "future_intent",
    "evidence_and_opinion",
}
_VISIBILITY_TIERS = {
    "must_inline",
    "exact_on_demand",
    "summary_reference",
    "excluded",
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
    visibility_tier: str = ""

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
        if self.visibility_tier and self.visibility_tier not in _VISIBILITY_TIERS:
            raise ValueError(
                f"unsupported context visibility tier: {self.visibility_tier}"
            )

    def as_dict(self) -> dict[str, object]:
        payload = {
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
        if self.visibility_tier:
            payload["visibility_tier"] = self.visibility_tier
        return payload


@dataclass(frozen=True)
class ContextLedger:
    ledger_id: str
    project_root_hash: str
    session_id: str
    operation_id: str
    plan_id: str
    entries: tuple[ContextLedgerEntry, ...]
    assembled_sha256: str
    execution_context_digest: str = ""

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
        if (
            self.execution_context_digest
            and not _SHA256.fullmatch(self.execution_context_digest)
        ):
            raise ValueError("context ledger execution_context_digest is invalid")
        if len({entry.source_ref for entry in self.entries}) != len(self.entries):
            raise ValueError("context ledger contains duplicate source refs")

    @property
    def digest(self) -> str:
        return _digest(self._body())

    def _body(self) -> dict[str, object]:
        payload = {
            "schema": CONTEXT_LEDGER_SCHEMA,
            "ledger_id": self.ledger_id,
            "project_root_hash": self.project_root_hash,
            "session_id": self.session_id,
            "operation_id": self.operation_id,
            "plan_id": self.plan_id,
            "entries": [entry.as_dict() for entry in self.entries],
            "assembled_sha256": self.assembled_sha256,
        }
        if self.execution_context_digest:
            payload["execution_context_digest"] = self.execution_context_digest
        return payload

    def as_dict(self) -> dict[str, object]:
        return {**self._body(), "digest": self.digest}


def context_ledger_id(
    *,
    project_root_hash: str,
    session_id: str,
    operation_id: str,
    assembled_sha256: str,
    identity_sha256: str = "",
) -> str:
    if identity_sha256 and not _SHA256.fullmatch(identity_sha256):
        raise ValueError("context ledger identity sha256 is invalid")
    suffix = _digest(
        {
            "project_root_hash": project_root_hash,
            "session_id": session_id,
            "operation_id": operation_id,
            "assembled_sha256": identity_sha256 or assembled_sha256,
        }
    )[:24]
    return f"context-{suffix}"


def parse_context_ledger(payload: dict[str, Any]) -> ContextLedger:
    if str(payload.get("schema") or "") != CONTEXT_LEDGER_SCHEMA:
        raise ValueError("unsupported context ledger schema")
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list):
        raise ValueError("context ledger entries must be a list")
    entries = tuple(_parse_entry(item) for item in raw_entries)
    ledger = ContextLedger(
        ledger_id=str(payload.get("ledger_id") or ""),
        project_root_hash=str(payload.get("project_root_hash") or ""),
        session_id=str(payload.get("session_id") or ""),
        operation_id=str(payload.get("operation_id") or ""),
        plan_id=str(payload.get("plan_id") or ""),
        entries=entries,
        assembled_sha256=str(payload.get("assembled_sha256") or ""),
        execution_context_digest=str(payload.get("execution_context_digest") or ""),
    )
    supplied_digest = str(payload.get("digest") or "")
    if supplied_digest and supplied_digest != ledger.digest:
        raise ValueError("context ledger digest does not match its metadata")
    return ledger


def _parse_entry(item: Any) -> ContextLedgerEntry:
    if not isinstance(item, dict):
        raise ValueError("context ledger entries contain a non-object item")
    source_limit = item.get("limit")
    return ContextLedgerEntry(
        source_ref=str(item.get("source_ref") or ""),
        title=str(item.get("title") or ""),
        purpose=str(item.get("purpose") or ""),
        partition=str(item.get("partition") or ""),
        byte_count=int(item.get("byte_count") or 0),
        character_count=int(item.get("character_count") or 0),
        sha256=str(item.get("sha256") or ""),
        included=bool(item.get("included")),
        truncated=bool(item.get("truncated")),
        limit=int(source_limit) if source_limit is not None else None,
        unit=str(item.get("unit") or "characters"),
        preview=str(item.get("preview") or ""),
        note=str(item.get("note") or ""),
        visibility_tier=str(item.get("visibility_tier") or ""),
    )


def _digest(value: object) -> str:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
