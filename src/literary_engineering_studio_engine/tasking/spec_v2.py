"""Strict ArcVellum task/v2 protocol codec.

The v2 envelope separates immutable task intent from mutable lifecycle state.
Route-specific data is retained only under ``spec.extensions``; consumers that
still use the v1 flat contract receive a lossless legacy projection.
"""

from __future__ import annotations

import hashlib
import json
from typing import Mapping

from .operations import operation_from_payload
from .spec_models import (
    TASK_SCHEMA_V1,
    TASK_SCHEMA_V2,
    EngineOperation,
    HumanGate,
    OutputContract,
    PathNormalizer,
    TaskDocument,
    TaskExecutionContract,
    TaskIdentity,
    TaskIntent,
    TaskLifecycle,
    TaskOperations,
    TaskResourceRef,
    TaskSpec,
    thaw_mapping,
)


ROOT_KEYS = frozenset({"schema", "spec", "lifecycle"})
SPEC_KEYS = frozenset(
    {
        "identity",
        "intent",
        "execution",
        "resources",
        "outputs",
        "operations",
        "validation",
        "extensions",
    }
)
IDENTITY_KEYS = frozenset({"task_id", "route", "scene_id", "contract_revision"})
INTENT_KEYS = frozenset({"current_state", "task_type", "prompt_asset_id"})
EXECUTION_KEYS = frozenset(
    {
        "policy",
        "agent_role",
        "human_gate",
        "runtime_capabilities_required",
        "compatibility_derived",
    }
)
HUMAN_GATE_KEYS = frozenset({"required", "reasons", "source"})
RESOURCES_KEYS = frozenset({"required_reading", "source_paths"})
RESOURCE_KEYS = frozenset({"uri", "path", "purpose", "required", "sha256"})
OUTPUT_KEYS = frozenset(
    {"path", "kind", "writeback_policy", "schema_name", "consumed_by"}
)
OPERATIONS_KEYS = frozenset({"prepare", "submit", "complete"})
VALIDATION_KEYS = frozenset({"gates", "forbidden_shortcuts"})
LIFECYCLE_KEYS = frozenset(
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
        "rollback",
        "superseded_at",
        "superseded_by",
        "supersession_reason",
        "refreshed_at",
        "refreshed_from_status",
        "extensions",
    }
)
RESERVED_V1_EXTENSION_KEYS = frozenset(
    {
        "schema",
        "task_contract_revision",
        "task_id",
        "route",
        "scene_id",
        "current_state",
        "task_type",
        "prompt_asset_id",
        "required_reading",
        "source_paths",
        "expected_outputs",
        "operations",
        "command",
        "submission_command",
        "completion_command",
        "execution_policy",
        "agent_role",
        "human_gate",
        "runtime_capabilities_required",
        "output_contracts",
        "validation_gates",
        "forbidden_shortcuts",
    }
)


def parse_task_document_v2(
    payload: Mapping[str, object],
    *,
    normalize_path: PathNormalizer,
) -> TaskDocument:
    _expect_keys(payload, ROOT_KEYS, "task")
    if payload.get("schema") != TASK_SCHEMA_V2:
        raise ValueError(f"unsupported task schema: {payload.get('schema')}")
    spec_payload = _mapping(payload.get("spec"), "task.spec")
    lifecycle_payload = _mapping(payload.get("lifecycle"), "task.lifecycle")
    _expect_keys(spec_payload, SPEC_KEYS, "task.spec")
    _expect_keys(lifecycle_payload, LIFECYCLE_KEYS, "task.lifecycle")
    _validate_lifecycle(lifecycle_payload)
    return _document_from_sections(spec_payload, lifecycle_payload, normalize_path)


def _document_from_sections(
    spec_payload: Mapping[str, object],
    lifecycle_payload: Mapping[str, object],
    normalize_path: PathNormalizer,
) -> TaskDocument:
    identity_payload = _mapping(spec_payload.get("identity"), "task.spec.identity")
    intent_payload = _mapping(spec_payload.get("intent"), "task.spec.intent")
    execution_payload = _mapping(spec_payload.get("execution"), "task.spec.execution")
    resources_payload = _mapping(spec_payload.get("resources"), "task.spec.resources")
    validation_payload = _mapping(spec_payload.get("validation"), "task.spec.validation")
    extensions = _mapping(spec_payload.get("extensions"), "task.spec.extensions")
    _expect_keys(identity_payload, IDENTITY_KEYS, "task.spec.identity")
    _expect_keys(intent_payload, INTENT_KEYS, "task.spec.intent")
    _expect_keys(execution_payload, EXECUTION_KEYS, "task.spec.execution")
    _expect_keys(resources_payload, RESOURCES_KEYS, "task.spec.resources")
    _expect_keys(validation_payload, VALIDATION_KEYS, "task.spec.validation")
    conflicting = sorted(RESERVED_V1_EXTENSION_KEYS & set(extensions))
    if conflicting:
        raise ValueError(
            "task.spec.extensions contains reserved fields: " + ", ".join(conflicting)
        )
    identity = _identity(identity_payload)
    intent = _intent(intent_payload)
    required_reading = _resources(
        resources_payload.get("required_reading"),
        "task.spec.resources.required_reading",
        normalize_path,
    )
    source_paths = _resources(
        resources_payload.get("source_paths"),
        "task.spec.resources.source_paths",
        normalize_path,
    )
    outputs = _outputs(spec_payload.get("outputs"), normalize_path)
    execution = _execution(execution_payload, outputs)
    operations = _operations(spec_payload.get("operations"))
    gates = _string_list(validation_payload.get("gates"), "task.spec.validation.gates")
    shortcuts = _string_list(
        validation_payload.get("forbidden_shortcuts"),
        "task.spec.validation.forbidden_shortcuts",
    )
    lifecycle = TaskLifecycle.from_v2_payload(lifecycle_payload)
    spec = TaskSpec(
        identity=identity,
        intent=intent,
        execution=execution,
        required_reading=required_reading,
        source_paths=source_paths,
        outputs=outputs,
        operations=operations,
        validation_gates=gates,
        forbidden_shortcuts=shortcuts,
        extensions=extensions,
        _v1_contract=_v1_contract(
            identity,
            intent,
            execution,
            required_reading,
            source_paths,
            outputs,
            operations,
            gates,
            shortcuts,
            extensions,
        ),
    )
    return TaskDocument(spec=spec, lifecycle=lifecycle)


def _validate_lifecycle(payload: Mapping[str, object]) -> None:
    status = _required_text(payload, "status", "task.lifecycle")
    allowed = {"issued", "opened", "submitted", "blocked", "complete", "superseded"}
    if status not in allowed:
        raise ValueError("task.lifecycle.status is invalid")


def _identity(payload: Mapping[str, object]) -> TaskIdentity:
    return TaskIdentity(
        schema=TASK_SCHEMA_V2,
        task_id=_required_text(payload, "task_id", "task.spec.identity"),
        route=_required_text(payload, "route", "task.spec.identity"),
        scene_id=str(payload.get("scene_id") or ""),
        contract_revision=_required_text(
            payload, "contract_revision", "task.spec.identity"
        ),
    )


def _intent(payload: Mapping[str, object]) -> TaskIntent:
    return TaskIntent(
        current_state=_required_text(payload, "current_state", "task.spec.intent"),
        task_type=_required_text(payload, "task_type", "task.spec.intent"),
        prompt_asset_id=_required_text(
            payload, "prompt_asset_id", "task.spec.intent"
        ),
    )


def task_document_to_v2(document: TaskDocument) -> dict[str, object]:
    spec = document.spec
    return {
        "schema": TASK_SCHEMA_V2,
        "spec": {
            "identity": {
                "task_id": spec.identity.task_id,
                "route": spec.identity.route,
                "scene_id": spec.identity.scene_id,
                "contract_revision": spec.identity.contract_revision,
            },
            "intent": {
                "current_state": spec.intent.current_state,
                "task_type": spec.intent.task_type,
                "prompt_asset_id": spec.intent.prompt_asset_id,
            },
            "execution": {
                "policy": spec.execution.execution_policy,
                "agent_role": spec.execution.agent_role,
                "human_gate": spec.execution.human_gate.as_dict(),
                "runtime_capabilities_required": list(
                    spec.execution.runtime_capabilities_required
                ),
                "compatibility_derived": spec.execution.compatibility_derived,
            },
            "resources": {
                "required_reading": [_resource_dict(item) for item in spec.required_reading],
                "source_paths": [_resource_dict(item) for item in spec.source_paths],
            },
            "outputs": [item.as_dict() for item in spec.outputs],
            "operations": spec.operations.as_dict(),
            "validation": {
                "gates": list(spec.validation_gates),
                "forbidden_shortcuts": list(spec.forbidden_shortcuts),
            },
            "extensions": thaw_mapping(spec.extensions),
        },
        "lifecycle": document.lifecycle.as_v2_dict(),
    }


def task_semantic_fingerprint(
    document: TaskDocument,
) -> str:
    """Hash task meaning independently of storage protocol and lifecycle."""

    spec = task_document_to_v2(document)["spec"]
    encoded = json.dumps(
        spec,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _execution(
    payload: Mapping[str, object],
    outputs: tuple[OutputContract, ...],
) -> TaskExecutionContract:
    policy = _required_text(payload, "policy", "task.spec.execution")
    if policy not in {"deterministic", "agent-required", "human-required"}:
        raise ValueError("task.spec.execution.policy is invalid")
    gate_payload = _mapping(payload.get("human_gate"), "task.spec.execution.human_gate")
    _expect_keys(gate_payload, HUMAN_GATE_KEYS, "task.spec.execution.human_gate")
    if not isinstance(gate_payload.get("required"), bool):
        raise ValueError("task.spec.execution.human_gate.required must be boolean")
    gate = HumanGate(
        required=bool(gate_payload["required"]),
        reasons=_string_list(
            gate_payload.get("reasons"), "task.spec.execution.human_gate.reasons"
        ),
        source=_required_text(
            gate_payload, "source", "task.spec.execution.human_gate"
        ),
    )
    compatibility = payload.get("compatibility_derived", False)
    if not isinstance(compatibility, bool):
        raise ValueError("task.spec.execution.compatibility_derived must be boolean")
    return TaskExecutionContract(
        execution_policy=policy,
        agent_role=_required_text(payload, "agent_role", "task.spec.execution"),
        human_gate=gate,
        runtime_capabilities_required=_string_list(
            payload.get("runtime_capabilities_required"),
            "task.spec.execution.runtime_capabilities_required",
        ),
        outputs=outputs,
        compatibility_derived=compatibility,
    )


def _resources(
    value: object,
    path: str,
    normalize_path: PathNormalizer,
) -> tuple[TaskResourceRef, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{path} must be an array")
    result: list[TaskResourceRef] = []
    for index, item in enumerate(value):
        entry_path = f"{path}[{index}]"
        entry = _mapping(item, entry_path)
        _expect_keys(entry, RESOURCE_KEYS, entry_path)
        normalized = str(normalize_path(_required_text(entry, "path", entry_path)))
        required = entry.get("required", True)
        if not isinstance(required, bool):
            raise ValueError(f"{entry_path}.required must be boolean")
        result.append(
            TaskResourceRef(
                uri=_required_text(entry, "uri", entry_path),
                path=normalized,
                purpose=_required_text(entry, "purpose", entry_path),
                required=required,
                sha256=str(entry.get("sha256") or ""),
            )
        )
    return tuple(result)


def _outputs(value: object, normalize_path: PathNormalizer) -> tuple[OutputContract, ...]:
    if not isinstance(value, list):
        raise ValueError("task.spec.outputs must be an array")
    result: list[OutputContract] = []
    for index, item in enumerate(value):
        path = f"task.spec.outputs[{index}]"
        entry = _mapping(item, path)
        _expect_keys(entry, OUTPUT_KEYS, path)
        policy = _required_text(entry, "writeback_policy", path)
        if policy not in {"automatic", "preview-required", "approval-required", "none"}:
            raise ValueError(f"{path}.writeback_policy is invalid")
        schema_name = str(entry.get("schema_name") or "")
        consumed_by = str(entry.get("consumed_by") or "")
        if bool(schema_name) != bool(consumed_by):
            raise ValueError(f"{path} requires both schema_name and consumed_by")
        result.append(
            OutputContract(
                path=str(normalize_path(_required_text(entry, "path", path))),
                kind=_required_text(entry, "kind", path),
                writeback_policy=policy,
                schema_name=schema_name,
                consumed_by=consumed_by,
            )
        )
    return tuple(result)


def _operations(value: object) -> TaskOperations:
    payload = _mapping(value, "task.spec.operations")
    _expect_keys(payload, OPERATIONS_KEYS, "task.spec.operations")
    return TaskOperations(
        prepare=_optional_operation(payload, "prepare"),
        submit=_optional_operation(payload, "submit"),
        complete=_optional_operation(payload, "complete"),
    )


def _optional_operation(payload: Mapping[str, object], name: str) -> EngineOperation | None:
    if name not in payload:
        return None
    raw = _mapping(payload[name], f"task.spec.operations.{name}")
    _expect_keys(
        raw,
        frozenset({"schema", "operation_id", "arguments", "display_command"}),
        f"task.spec.operations.{name}",
    )
    if raw.get("schema") != "arcvellum/engine-operation/v1":
        raise ValueError(f"task.spec.operations.{name}.schema is invalid")
    operation = operation_from_payload(raw)
    if operation is None:
        raise ValueError(f"task.spec.operations.{name} is invalid")
    return operation


def _v1_contract(
    identity: TaskIdentity,
    intent: TaskIntent,
    execution: TaskExecutionContract,
    required_reading: tuple[TaskResourceRef, ...],
    source_paths: tuple[TaskResourceRef, ...],
    outputs: tuple[OutputContract, ...],
    operations: TaskOperations,
    gates: tuple[str, ...],
    shortcuts: tuple[str, ...],
    extensions: Mapping[str, object],
) -> dict[str, object]:
    contract = thaw_mapping(extensions)
    contract.update(
        {
            "schema": TASK_SCHEMA_V1,
            "task_contract_revision": identity.contract_revision,
            "task_id": identity.task_id,
            "route": identity.route,
            "scene_id": identity.scene_id,
            "current_state": intent.current_state,
            "task_type": intent.task_type,
            "prompt_asset_id": intent.prompt_asset_id,
            "execution_policy": execution.execution_policy,
            "agent_role": execution.agent_role,
            "human_gate": execution.human_gate.as_dict(),
            "runtime_capabilities_required": list(
                execution.runtime_capabilities_required
            ),
            "required_reading": [item.path for item in required_reading],
            "source_paths": [item.path for item in source_paths],
            "expected_outputs": [item.path for item in outputs],
            "output_contracts": [item.as_dict() for item in outputs],
            "operations": operations.as_dict(),
            "validation_gates": list(gates),
            "forbidden_shortcuts": list(shortcuts),
        }
    )
    for name, operation in (
        ("command", operations.prepare),
        ("submission_command", operations.submit),
        ("completion_command", operations.complete),
    ):
        contract[name] = operation.display_command if operation else ""
    return contract


def _resource_dict(value: TaskResourceRef) -> dict[str, object]:
    result: dict[str, object] = {
        "uri": value.uri,
        "path": value.path,
        "purpose": value.purpose,
        "required": value.required,
    }
    if value.sha256:
        result["sha256"] = value.sha256
    return result


def _mapping(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must be an object")
    return value


def _expect_keys(value: Mapping[str, object], allowed: frozenset[str], path: str) -> None:
    unexpected = sorted(set(value) - allowed)
    if unexpected:
        raise ValueError(f"{path} has unsupported fields: {', '.join(unexpected)}")


def _required_text(value: Mapping[str, object], name: str, path: str) -> str:
    result = str(value.get(name) or "").strip()
    if not result:
        raise ValueError(f"{path}.{name} must not be empty")
    return result


def _string_list(value: object, path: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{path} must be an array")
    result = tuple(str(item) for item in value if str(item).strip())
    if len(result) != len(value):
        raise ValueError(f"{path} entries must be non-empty strings")
    return result


__all__ = [
    "parse_task_document_v2",
    "task_document_to_v2",
    "task_semantic_fingerprint",
]
