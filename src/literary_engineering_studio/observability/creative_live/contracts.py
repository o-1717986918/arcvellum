"""Stable event contracts shared by Runtime, API projections, and the client."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
from pathlib import Path
from typing import Any, Mapping


CREATIVE_LIVE_SCHEMA = "arcvellum/creative-live-event/v1"


class EventChannel(str, Enum):
    ACTIVITY = "activity"
    TRANSCRIPT = "transcript"
    ARTIFACT = "artifact"
    REVIEW = "review"
    USAGE = "usage"
    CONTROL = "control"


class EventVisibility(str, Enum):
    USER = "user"
    ADVANCED = "advanced"
    DIAGNOSTIC = "diagnostic"
    RESTRICTED = "restricted"


class ArtifactIdentity(str, Enum):
    STREAMING_PREVIEW = "streaming_preview"
    CANDIDATE_WRITTEN = "candidate_written"
    DETERMINISTIC_PREFLIGHT_PASSED = "deterministic_preflight_passed"
    SEMANTIC_REVIEW_PASSED = "semantic_review_passed"
    PROMOTED = "promoted"
    STATE_AND_CANON_APPLIED = "state_and_canon_applied"
    VALIDATION_FAILED = "validation_failed"
    REVISION_STREAMING = "revision_streaming"
    REVISION_WRITTEN = "revision_written"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


CHANNELS = frozenset(item.value for item in EventChannel)
VISIBILITIES = frozenset(item.value for item in EventVisibility)
ARTIFACT_IDENTITIES = frozenset(item.value for item in ArtifactIdentity)


@dataclass(frozen=True)
class CreativeLiveEvent:
    """One normalized event; empty identity fields remain explicit on the wire."""

    event_id: str
    sequence: int
    event: str
    channel: EventChannel
    visibility: EventVisibility
    durability: str
    at: str
    project_id: str = ""
    run_id: str = ""
    session_id: str = ""
    task_id: str = ""
    route: str = ""
    attempt_id: str = ""
    artifact: Mapping[str, Any] | None = None
    data: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise ValueError("creative live event_id is required")
        if self.sequence < 0:
            raise ValueError("creative live sequence must be non-negative")
        if not self.event.strip() or "." not in self.event:
            raise ValueError("creative live event must be a namespaced event name")
        if self.durability not in {"ephemeral", "durable"}:
            raise ValueError("creative live durability must be ephemeral or durable")
        if self.artifact is not None:
            identity = str(self.artifact.get("identity") or "")
            if identity not in ARTIFACT_IDENTITIES:
                raise ValueError(f"unsupported artifact identity: {identity}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": CREATIVE_LIVE_SCHEMA,
            "event_id": self.event_id,
            "sequence": self.sequence,
            "event": self.event,
            "channel": self.channel.value,
            "visibility": self.visibility.value,
            "durability": self.durability,
            "at": self.at,
            "project_id": self.project_id,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "route": self.route,
            "attempt_id": self.attempt_id,
            "artifact": dict(self.artifact) if self.artifact is not None else None,
            "data": dict(self.data),
        }

    @classmethod
    def create(
        cls,
        *,
        event: str,
        channel: EventChannel,
        visibility: EventVisibility,
        durability: str,
        sequence: int = 0,
        event_id: str = "",
        at: str = "",
        project_id: str = "",
        run_id: str = "",
        session_id: str = "",
        task_id: str = "",
        route: str = "",
        attempt_id: str = "",
        artifact: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
    ) -> "CreativeLiveEvent":
        timestamp = at or datetime.now(timezone.utc).isoformat()
        identity = event_id or _event_id(event, timestamp, sequence, run_id, session_id)
        return cls(
            event_id=identity,
            sequence=sequence,
            event=event,
            channel=channel,
            visibility=visibility,
            durability=durability,
            at=timestamp,
            project_id=project_id,
            run_id=run_id,
            session_id=session_id,
            task_id=task_id,
            route=route,
            attempt_id=attempt_id,
            artifact=artifact,
            data=data or {},
        )


def project_id(project_root: str | Path) -> str:
    normalized = str(Path(project_root).expanduser().resolve()).replace("\\", "/").casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]


def project_channel(project_root: str | Path) -> str:
    return f"project:{project_id(project_root)}"


def artifact_id(project: str, path: str, attempt_id: str = "") -> str:
    source = "\0".join((project, path.replace("\\", "/"), attempt_id))
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:32]


def _event_id(event: str, at: str, sequence: int, run_id: str, session_id: str) -> str:
    source = "\0".join((event, at, str(sequence), run_id, session_id))
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:32]
