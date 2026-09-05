"""Route-neutral construction of formal task envelopes."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
from typing import Mapping, Sequence

from .paths import normalize_relative_path, now, resolve_project_path, task_id
from .spec_models import TASK_SCHEMA_V1


@dataclass(frozen=True)
class WordCountContract:
    target: int = 0
    minimum: int = 0
    maximum: int = 0


@dataclass(frozen=True)
class TaskBuilder:
    """Build the common flat task view consumed by route enrichment.

    A route supplies literary meaning through its blueprint and ``route_fields``.
    This builder owns only protocol identity, normalized resources, lifecycle
    defaults, and the shared submit/complete display contract.
    """

    route: str
    target_id: str
    current_state: str
    blueprint: Mapping[str, object]
    scene_id: str
    required_reading: Sequence[str]
    forbidden_shortcuts: Sequence[str]
    route_fields: Mapping[str, object] = field(default_factory=dict)
    word_count: WordCountContract = field(default_factory=WordCountContract)
    include_target_id: bool = True
    identifier: str = ""
    root: Path | None = None

    def build(self) -> dict[str, object]:
        identifier = self.identifier or task_id(
            self.route,
            self.target_id,
            self.current_state,
        )
        expected_outputs = normalized_unique(self.blueprint["expected_outputs"])
        source_paths = normalized_unique(self.blueprint["source_paths"])
        payload: dict[str, object] = {
            "schema": TASK_SCHEMA_V1,
            "task_id": identifier,
            "status": "issued",
            "created_at": now(),
            "route": self.route,
            "scene_id": self.scene_id,
        }
        if self.include_target_id:
            payload["target_id"] = self.target_id
        payload.update(self.route_fields)
        payload.update(
            {
                "current_state": self.current_state,
                "task_type": self.blueprint["task_type"],
                "prompt_asset_id": self.blueprint["prompt_asset_id"],
                "command": self.blueprint["command"],
                "required_reading": list(
                    self.blueprint.get("required_reading", self.required_reading)
                ),
                "source_paths": source_paths,
                "context_trace": self.blueprint.get("context_trace", ""),
                "hard_constraints": list(self.blueprint["hard_constraints"]),
                "style_constraints": list(self.blueprint["style_constraints"]),
                "word_count_target": self.word_count.target,
                "word_count_min": self.word_count.minimum,
                "word_count_max": self.word_count.maximum,
                "expected_outputs": expected_outputs,
                "submission_command": submission_command(identifier),
                "completion_command": completion_command(identifier),
                "validation_gates": list(self.blueprint["validation_gates"]),
                "forbidden_shortcuts": list(self.forbidden_shortcuts),
                "next_allowed_states": list(self.blueprint["next_allowed_states"]),
            }
        )
        self._attach_blueprint_contracts(payload, expected_outputs)
        return payload

    def _attach_blueprint_contracts(
        self,
        payload: dict[str, object],
        expected_outputs: list[str],
    ) -> None:
        agent_sources = self.blueprint.get("agent_source_paths")
        if isinstance(agent_sources, (list, tuple)):
            payload["agent_source_paths"] = normalized_unique(agent_sources)
        owned = self.blueprint.get("system_owned_fields")
        if isinstance(owned, Mapping):
            payload["system_owned_fields"] = dict(owned)
        core_outputs = normalized_unique(self.blueprint.get("core_managed_outputs", []))
        if core_outputs:
            payload["core_managed_outputs"] = [
                item for item in core_outputs if item in expected_outputs
            ]
        self._attach_repair_provenance(payload)

    def _attach_repair_provenance(self, payload: dict[str, object]) -> None:
        repair_targets = normalized_unique(self.blueprint.get("repair_targets", []))
        if not repair_targets:
            return
        payload["repair_targets"] = repair_targets
        if self.root is None:
            return
        payload["repair_target_sha256_before_revision"] = {
            relative: file_sha256(resolve_project_path(self.root, relative))
            for relative in repair_targets
            if resolve_project_path(self.root, relative).is_file()
        }


def normalized_unique(values: object) -> list[str]:
    if not isinstance(values, (list, tuple)):
        return []
    result: list[str] = []
    for item in values:
        normalized = normalize_relative_path(str(item))
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def submission_command(identifier: str) -> str:
    return (
        "python -m literary_engineering_studio_engine task-submit <project> "
        f"--task-id {identifier} --from <artifact>"
    )


def completion_command(identifier: str) -> str:
    return (
        "python -m literary_engineering_studio_engine task-complete <project> "
        f"--task-id {identifier}"
    )


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


__all__ = [
    "TaskBuilder",
    "WordCountContract",
    "completion_command",
    "file_sha256",
    "normalized_unique",
    "submission_command",
]
