"""Resource claims shared by the future orchestration compiler and runtime."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
from pathlib import Path, PurePosixPath
from typing import Literal

from ...contracts import TaskPackage, normalize_relative_path
from ..capabilities.contracts import CapabilityId
from ..capabilities.policy import build_capability_manifest


RESOURCE_CLAIM_SCHEMA = "arcvellum/resource-claim/v1"


class NetworkAccess(str, Enum):
    NONE = "none"
    ALLOWLISTED = "allowlisted"


@dataclass(frozen=True)
class ResourceClaim:
    task_node_id: str
    project_id: str
    reads: tuple[str, ...]
    writes: tuple[str, ...]
    runtime_slot: str
    model_slot: str
    network: Literal["none", "allowlisted"]
    exclusive_barriers: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": RESOURCE_CLAIM_SCHEMA,
            "task_node_id": self.task_node_id,
            "project_id": self.project_id,
            "reads": list(self.reads),
            "writes": list(self.writes),
            "runtime_slot": self.runtime_slot,
            "model_slot": self.model_slot,
            "network": self.network,
            "exclusive_barriers": list(self.exclusive_barriers),
        }


@dataclass(frozen=True)
class ResourceConflict:
    conflicts: bool
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {"conflicts": self.conflicts, "reasons": list(self.reasons)}


def derive_resource_claim(
    task: TaskPackage,
    *,
    task_node_id: str = "",
    runtime_slot: str = "agent-worker",
    model_slot: str = "default",
) -> ResourceClaim:
    agent_sources = task.payload.get("agent_source_paths")
    reads = agent_sources if isinstance(agent_sources, list) else list(task.source_paths)
    reads = [*reads, *task.required_reading, *task.core_managed_outputs]
    writes = list(task.expected_outputs)
    manifest = build_capability_manifest(task)
    network = (
        NetworkAccess.ALLOWLISTED.value
        if CapabilityId.RESEARCH_WEB.value in manifest.allowed_capability_ids
        else NetworkAccess.NONE.value
    )
    return ResourceClaim(
        task_node_id=task_node_id.strip() or task.task_id,
        project_id=project_identity(task.project_root),
        reads=tuple(_normalized(reads)),
        writes=tuple(_normalized(writes)),
        runtime_slot=runtime_slot.strip() or "agent-worker",
        model_slot=model_slot.strip() or "default",
        network=network,
        exclusive_barriers=tuple(_barriers(writes)),
    )


def resource_claim_from_dict(payload: dict[str, object]) -> ResourceClaim:
    """Parse a persisted claim without introducing a second claim model."""

    schema = str(payload.get("schema") or "")
    if schema and schema != RESOURCE_CLAIM_SCHEMA:
        raise ValueError("resource claim schema is invalid")
    return ResourceClaim(
        task_node_id=_required_text(payload, "task_node_id"),
        project_id=_required_text(payload, "project_id"),
        reads=_string_tuple(payload.get("reads")),
        writes=_string_tuple(payload.get("writes")),
        runtime_slot=_required_text(payload, "runtime_slot"),
        model_slot=_required_text(payload, "model_slot"),
        network=_network_policy(payload),
        exclusive_barriers=_string_tuple(payload.get("exclusive_barriers")),
    )


def claims_conflict(left: ResourceClaim, right: ResourceClaim) -> ResourceConflict:
    reasons: list[str] = []
    if left.project_id != right.project_id:
        return ResourceConflict(False, ())
    for barrier in sorted(set(left.exclusive_barriers) & set(right.exclusive_barriers)):
        reasons.append(f"exclusive-barrier:{barrier}")
    for left_path in left.writes:
        for right_path in right.writes:
            if paths_overlap(left_path, right_path):
                reasons.append(f"write-write:{left_path}:{right_path}")
        for right_path in right.reads:
            if paths_overlap(left_path, right_path):
                reasons.append(f"write-read:{left_path}:{right_path}")
    for left_path in left.reads:
        for right_path in right.writes:
            if paths_overlap(left_path, right_path):
                reasons.append(f"read-write:{left_path}:{right_path}")
    return ResourceConflict(bool(reasons), tuple(dict.fromkeys(reasons)))


def paths_overlap(left: str, right: str) -> bool:
    left_path = PurePosixPath(str(normalize_relative_path(left)))
    right_path = PurePosixPath(str(normalize_relative_path(right)))
    return left_path == right_path or left_path in right_path.parents or right_path in left_path.parents


def project_identity(root: Path) -> str:
    normalized = str(root.resolve()).replace("\\", "/").lower()
    return "project-" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _normalized(values: list[object]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = str(normalize_relative_path(str(value)))
        if normalized not in result:
            result.append(normalized)
    return result


def _barriers(writes: list[object]) -> list[str]:
    result: list[str] = []
    for value in writes:
        path = str(normalize_relative_path(str(value)))
        barrier = ""
        if path.startswith("canon/"):
            barrier = "canon-write"
        elif path.startswith("characters/"):
            barrier = "character-state-write"
        elif path.startswith("workflow/approvals/"):
            barrier = "approval-ledger-write"
        elif path.startswith("releases/"):
            barrier = "release-write"
        if barrier and barrier not in result:
            result.append(barrier)
    return result


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("resource claim path/barrier fields must be arrays")
    return tuple(str(item) for item in value)


def _required_text(payload: dict[str, object], field: str) -> str:
    value = str(payload.get(field) or "").strip()
    if not value:
        raise ValueError(f"resource claim {field} is required")
    return value


def _network_policy(payload: dict[str, object]) -> str:
    value = str(payload.get("network") or "")
    if value not in {item.value for item in NetworkAccess}:
        raise ValueError("resource claim network policy is invalid")
    return value
