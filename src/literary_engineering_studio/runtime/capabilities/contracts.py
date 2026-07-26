"""Versioned contracts for bounded runtime capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from typing import Any


CAPABILITY_MANIFEST_SCHEMA = "arcvellum/capability-manifest/v1"
CAPABILITY_REQUEST_SCHEMA = "arcvellum/capability-request/v1"
CAPABILITY_RESULT_SCHEMA = "arcvellum/capability-result/v1"
CAPABILITY_POLICY_REVISION = "2026-07-26.1"
DEFAULT_MAX_RESULT_CHARS = 24_000
MAX_MAX_RESULT_CHARS = 200_000
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")


class CapabilityId(str, Enum):
    PROJECT_QUERY = "project.query"
    SCHEMA_INSPECT = "schema.inspect"
    TEXT_STATISTICS = "text.statistics"
    CITATION_LOOKUP = "citation.lookup"
    REFERENCE_SEARCH = "reference.search"
    RESEARCH_WEB = "research.web"
    ASSET_DIFF = "asset.diff"


class CapabilityStatus(str, Enum):
    COMPLETED = "completed"
    DENIED = "denied"
    FAILED = "failed"


@dataclass(frozen=True)
class CapabilityManifest:
    task_id: str
    route: str
    current_state: str
    agent_role: str
    allowed_capability_ids: tuple[str, ...]
    readable_paths: tuple[str, ...]
    writable_paths: tuple[str, ...]
    network_domains: tuple[str, ...] = ()
    max_result_chars: int = DEFAULT_MAX_RESULT_CHARS
    policy_revision: str = CAPABILITY_POLICY_REVISION

    @property
    def digest(self) -> str:
        return _digest(self._body())

    def _body(self) -> dict[str, Any]:
        return {
            "schema": CAPABILITY_MANIFEST_SCHEMA,
            "policy_revision": self.policy_revision,
            "task_id": self.task_id,
            "route": self.route,
            "current_state": self.current_state,
            "agent_role": self.agent_role,
            "allowed_capability_ids": list(self.allowed_capability_ids),
            "readable_paths": list(self.readable_paths),
            "writable_paths": list(self.writable_paths),
            "network_domains": list(self.network_domains),
            "max_result_chars": self.max_result_chars,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self._body(), "digest": self.digest}


@dataclass(frozen=True)
class CapabilityRequest:
    request_id: str
    task_id: str
    capability_id: str
    arguments: dict[str, Any]

    def __post_init__(self) -> None:
        if not _REQUEST_ID_PATTERN.fullmatch(self.request_id):
            raise ValueError("invalid capability request_id")
        if not self.task_id.strip():
            raise ValueError("capability request task_id is required")
        try:
            CapabilityId(self.capability_id)
        except ValueError as exc:
            raise ValueError(f"unknown capability: {self.capability_id}") from exc
        if not isinstance(self.arguments, dict):
            raise ValueError("capability arguments must be an object")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": CAPABILITY_REQUEST_SCHEMA,
            "request_id": self.request_id,
            "task_id": self.task_id,
            "capability_id": self.capability_id,
            "arguments": self.arguments,
        }


@dataclass(frozen=True)
class CapabilityResult:
    request_id: str
    task_id: str
    capability_id: str
    status: str
    summary: str
    data: dict[str, Any]
    result_digest: str
    duration_ms: int
    artifact: str = ""
    error_code: str = ""
    error_message: str = ""
    truncated: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": CAPABILITY_RESULT_SCHEMA,
            "request_id": self.request_id,
            "task_id": self.task_id,
            "capability_id": self.capability_id,
            "status": self.status,
            "summary": self.summary,
            "data": self.data,
            "result_digest": self.result_digest,
            "duration_ms": self.duration_ms,
            "artifact": self.artifact,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "truncated": self.truncated,
        }


@dataclass(frozen=True)
class HandlerOutput:
    summary: str
    data: dict[str, Any]


class CapabilityPolicyError(ValueError):
    """A request violates its immutable capability manifest."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def result_digest(value: object) -> str:
    return _digest(value)


def bounded_result_limit(value: object) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return DEFAULT_MAX_RESULT_CHARS
    return max(1_000, min(parsed, MAX_MAX_RESULT_CHARS))


def _digest(value: object) -> str:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
