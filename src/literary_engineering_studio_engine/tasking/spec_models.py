"""Immutable values for the ArcVellum task protocol."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Mapping


TASK_SCHEMA_V1 = "literary-engineering-workbench/agent-task/v1"
EXECUTION_CONTRACT_SCHEMA = "literary-engineering-studio/task-execution/v0.3"
LIFECYCLE_FIELDS = frozenset(
    {
        "status",
        "created_at",
        "opened_at",
        "submitted_at",
        "completed_at",
        "blocked_at",
        "submission",
        "submitted_artifacts",
        "completion",
        "validation",
        "refreshed_at",
        "refreshed_from_status",
    }
)
PathNormalizer = Callable[[str], object]


@dataclass(frozen=True)
class HumanGate:
    required: bool
    reasons: tuple[str, ...]
    source: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "required": self.required,
            "reasons": list(self.reasons),
            "source": self.source,
        }


@dataclass(frozen=True)
class OutputContract:
    path: str
    kind: str
    writeback_policy: str
    schema_name: str = ""
    consumed_by: str = ""

    def as_dict(self) -> dict[str, str]:
        result = {
            "path": self.path,
            "kind": self.kind,
            "writeback_policy": self.writeback_policy,
        }
        if self.schema_name:
            result["schema_name"] = self.schema_name
        if self.consumed_by:
            result["consumed_by"] = self.consumed_by
        return result


@dataclass(frozen=True)
class TaskExecutionContract:
    execution_policy: str
    agent_role: str
    human_gate: HumanGate
    runtime_capabilities_required: tuple[str, ...]
    outputs: tuple[OutputContract, ...]
    compatibility_derived: bool

    @property
    def writeback_policy(self) -> str:
        policies = {item.writeback_policy for item in self.outputs}
        for policy in ("approval-required", "preview-required", "automatic"):
            if policy in policies:
                return policy
        return "none"

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": EXECUTION_CONTRACT_SCHEMA,
            "execution_policy": self.execution_policy,
            "agent_role": self.agent_role,
            "human_gate": self.human_gate.as_dict(),
            "runtime_capabilities_required": list(
                self.runtime_capabilities_required
            ),
            "outputs": [item.as_dict() for item in self.outputs],
            "writeback_policy": self.writeback_policy,
            "compatibility_derived": self.compatibility_derived,
        }


@dataclass(frozen=True)
class TaskIdentity:
    schema: str
    task_id: str
    route: str
    scene_id: str
    contract_revision: str


@dataclass(frozen=True)
class TaskIntent:
    current_state: str
    task_type: str
    prompt_asset_id: str


@dataclass(frozen=True)
class TaskResourceRef:
    uri: str
    path: str
    purpose: str
    required: bool = True
    sha256: str = ""


@dataclass(frozen=True)
class EngineOperation:
    operation_id: str
    arguments: Mapping[str, object] = field(default_factory=dict)
    display_command: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "arguments",
            freeze_mapping(dict(self.arguments)),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": "arcvellum/engine-operation/v1",
            "operation_id": self.operation_id,
            "arguments": thaw_mapping(self.arguments),
            "display_command": self.display_command,
        }


@dataclass(frozen=True)
class TaskOperations:
    prepare: EngineOperation | None = None
    submit: EngineOperation | None = None
    complete: EngineOperation | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            name: operation.as_dict()
            for name, operation in (
                ("prepare", self.prepare),
                ("submit", self.submit),
                ("complete", self.complete),
            )
            if operation is not None
        }


@dataclass(frozen=True)
class TaskLifecycle:
    status: str
    created_at: str = ""
    opened_at: str = ""
    submitted_at: str = ""
    completed_at: str = ""
    blocked_at: str = ""
    submission: str = ""
    completion: str = ""
    submitted_artifacts: tuple[str, ...] = ()
    validation: Mapping[str, object] = field(default_factory=dict)
    _v1_fields: Mapping[str, object] = field(
        default_factory=dict,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "validation", freeze_mapping(self.validation))
        object.__setattr__(self, "_v1_fields", freeze_mapping(self._v1_fields))

    @classmethod
    def from_v1_payload(cls, payload: Mapping[str, object]) -> "TaskLifecycle":
        fields = {
            key: payload[key]
            for key in LIFECYCLE_FIELDS
            if key in payload
        }
        validation = payload.get("validation")
        return cls(
            status=str(payload.get("status") or "issued"),
            created_at=str(payload.get("created_at") or ""),
            opened_at=str(payload.get("opened_at") or ""),
            submitted_at=str(payload.get("submitted_at") or ""),
            completed_at=str(payload.get("completed_at") or ""),
            blocked_at=str(payload.get("blocked_at") or ""),
            submission=str(payload.get("submission") or ""),
            completion=str(payload.get("completion") or ""),
            submitted_artifacts=tuple(
                str(item) for item in payload.get("submitted_artifacts") or []
            ),
            validation=validation if isinstance(validation, Mapping) else {},
            _v1_fields=fields,
        )

    def to_v1_fields(self) -> dict[str, object]:
        return thaw_mapping(self._v1_fields)


@dataclass(frozen=True)
class TaskSpec:
    identity: TaskIdentity
    intent: TaskIntent
    execution: TaskExecutionContract
    required_reading: tuple[TaskResourceRef, ...]
    source_paths: tuple[TaskResourceRef, ...]
    outputs: tuple[OutputContract, ...]
    operations: TaskOperations
    validation_gates: tuple[str, ...]
    forbidden_shortcuts: tuple[str, ...]
    extensions: Mapping[str, object] = field(default_factory=dict)
    _v1_contract: Mapping[str, object] = field(
        default_factory=dict,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "extensions", freeze_mapping(self.extensions))
        object.__setattr__(self, "_v1_contract", freeze_mapping(self._v1_contract))

    @property
    def resources(self) -> tuple[TaskResourceRef, ...]:
        return self.required_reading + self.source_paths

    def to_v1_payload(
        self,
        lifecycle: "TaskLifecycle | None" = None,
    ) -> dict[str, object]:
        payload = thaw_mapping(self._v1_contract)
        if lifecycle is not None:
            payload.update(lifecycle.to_v1_fields())
        return payload


@dataclass(frozen=True)
class TaskDocument:
    spec: TaskSpec
    lifecycle: TaskLifecycle

    def to_v1_payload(self) -> dict[str, object]:
        return self.spec.to_v1_payload(self.lifecycle)


def freeze_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(
        {str(key): _freeze_value(item) for key, item in value.items()}
    )


def thaw_mapping(value: Mapping[str, object]) -> dict[str, object]:
    return {key: _thaw_value(item) for key, item in value.items()}


def _freeze_value(value: object) -> object:
    if isinstance(value, Mapping):
        return freeze_mapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    return value


def _thaw_value(value: object) -> object:
    if isinstance(value, Mapping):
        return thaw_mapping(value)
    if isinstance(value, tuple):
        return [_thaw_value(item) for item in value]
    return value
