"""Read agent-task/v1 dictionaries into typed task values."""

from __future__ import annotations

from typing import Mapping

from .spec_models import (
    EngineOperation,
    HumanGate,
    LIFECYCLE_FIELDS,
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
)
from .operations import operation_from_payload


HUMAN_GATE_TOKENS = (
    "human-choice",
    "human_approval",
    "approval",
    "canon-apply",
    "state-apply",
    "release-approval",
    "publish-approval",
)
HIGH_IMPACT_PREFIXES = (
    "canon/",
    "characters/",
    "drafts/scenes/",
    "manuscript/",
    "releases/",
    "state/",
)
CREATIVE_TASK_TOKENS = (
    "prose",
    "compose",
    "roleplay",
    "branch",
    "style",
    "extract",
    "review",
    "canon",
    "character",
    "world",
)
CORE_FIELDS = frozenset(
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
        "command",
        "operations",
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


def parse_task_document(
    payload: Mapping[str, object],
    *,
    normalize_path: PathNormalizer,
) -> TaskDocument:
    execution = parse_execution_contract(payload, normalize_path=normalize_path)
    lifecycle = TaskLifecycle.from_v1_payload(payload)
    contract = {
        key: value for key, value in payload.items() if key not in LIFECYCLE_FIELDS
    }
    spec = TaskSpec(
        identity=_identity(payload),
        intent=_intent(payload),
        execution=execution,
        required_reading=_resource_refs(
            payload.get("required_reading"),
            purpose="required-reading",
            scheme="engine",
            normalize_path=normalize_path,
        ),
        source_paths=_resource_refs(
            payload.get("source_paths"),
            purpose="agent-source",
            scheme="project",
            normalize_path=normalize_path,
        ),
        outputs=execution.outputs,
        operations=_operations(payload),
        validation_gates=_strings(payload.get("validation_gates")),
        forbidden_shortcuts=_strings(payload.get("forbidden_shortcuts")),
        extensions={
            key: value for key, value in contract.items() if key not in CORE_FIELDS
        },
        _v1_contract=contract,
    )
    return TaskDocument(spec=spec, lifecycle=lifecycle)


def infer_human_gate(payload: Mapping[str, object]) -> HumanGate:
    explicit = payload.get("human_gate")
    if isinstance(explicit, Mapping) and isinstance(
        explicit.get("required"), bool
    ):
        return _explicit_human_gate(explicit)
    haystack = " ".join(
        (
            str(payload.get("current_state") or ""),
            str(payload.get("task_type") or ""),
            str(payload.get("prompt_asset_id") or ""),
        )
    ).lower()
    reasons = tuple(token for token in HUMAN_GATE_TOKENS if token in haystack)
    return HumanGate(bool(reasons), reasons, "compatibility-inference")


def derive_execution_policy(
    payload: Mapping[str, object],
    human_gate: HumanGate,
) -> str:
    if human_gate.required:
        return "human-required"
    task_type = str(payload.get("task_type") or "").lower()
    prompt_id = str(payload.get("prompt_asset_id") or "").lower()
    if task_type == "deterministic-cli":
        return "deterministic"
    if "deterministic-cli-plus-platform-review" in task_type:
        return "agent-required"
    if "platform-agent" in task_type or prompt_id:
        return "agent-required"
    if str(payload.get("command") or "").strip():
        return "deterministic"
    return "agent-required"


def parse_execution_contract(
    payload: Mapping[str, object],
    *,
    normalize_path: PathNormalizer,
) -> TaskExecutionContract:
    gate = infer_human_gate(payload)
    policy = str(payload.get("execution_policy") or "").strip()
    role = str(payload.get("agent_role") or "").strip()
    capabilities = payload.get("runtime_capabilities_required")
    outputs = payload.get("output_contracts")
    compatibility_derived = not _has_explicit_contract(
        policy,
        role,
        capabilities,
        outputs,
        payload.get("human_gate"),
    )
    policy = policy or derive_execution_policy(payload, gate)
    paths = tuple(
        str(normalize_path(str(item)))
        for item in payload.get("expected_outputs") or []
    )
    return TaskExecutionContract(
        execution_policy=policy,
        agent_role=role or _derive_agent_role(payload, policy),
        human_gate=gate,
        runtime_capabilities_required=_capabilities(
            capabilities,
            policy,
            paths,
        ),
        outputs=_outputs(
            outputs,
            policy,
            paths,
            normalize_path=normalize_path,
        ),
        compatibility_derived=compatibility_derived,
    )


def parse_output_contracts(
    values: list[object],
    *,
    normalize_path: PathNormalizer,
) -> tuple[OutputContract, ...]:
    return tuple(
        _parse_output_contract(value, normalize_path=normalize_path)
        for value in values
    )


def _parse_output_contract(
    value: object,
    *,
    normalize_path: PathNormalizer,
) -> OutputContract:
    if not isinstance(value, Mapping):
        raise ValueError("task package output_contracts entries must be objects")
    path = str(value.get("path") or "").strip()
    kind = str(value.get("kind") or "").strip()
    policy = str(value.get("writeback_policy") or "").strip()
    if not path or not kind or policy not in {
        "automatic",
        "preview-required",
        "approval-required",
        "none",
    }:
        raise ValueError("invalid task package output contract")
    schema_name = str(value.get("schema_name") or "").strip()
    consumed_by = str(value.get("consumed_by") or "").strip()
    if bool(schema_name) != bool(consumed_by):
        raise ValueError(
            "semantic output contracts require both schema_name and consumed_by"
        )
    return OutputContract(
        str(normalize_path(path)),
        kind,
        policy,
        schema_name,
        consumed_by,
    )


def _identity(payload: Mapping[str, object]) -> TaskIdentity:
    return TaskIdentity(
        schema=str(payload.get("schema") or ""),
        task_id=str(payload.get("task_id") or ""),
        route=str(payload.get("route") or ""),
        scene_id=str(payload.get("scene_id") or ""),
        contract_revision=str(payload.get("task_contract_revision") or ""),
    )


def _intent(payload: Mapping[str, object]) -> TaskIntent:
    return TaskIntent(
        current_state=str(payload.get("current_state") or ""),
        task_type=str(payload.get("task_type") or "").strip(),
        prompt_asset_id=str(payload.get("prompt_asset_id") or ""),
    )


def _operations(payload: Mapping[str, object]) -> TaskOperations:
    explicit = payload.get("operations")
    if isinstance(explicit, Mapping):
        return TaskOperations(
            prepare=(
                operation_from_payload(explicit.get("prepare"))
                if "prepare" in explicit
                else _legacy_operation("prepare", payload.get("command"))
            ),
            submit=(
                operation_from_payload(explicit.get("submit"))
                if "submit" in explicit
                else _legacy_operation("submit", payload.get("submission_command"))
            ),
            complete=(
                operation_from_payload(explicit.get("complete"))
                if "complete" in explicit
                else _legacy_operation("complete", payload.get("completion_command"))
            ),
        )
    return TaskOperations(
        prepare=_legacy_operation("prepare", payload.get("command")),
        submit=_legacy_operation("submit", payload.get("submission_command")),
        complete=_legacy_operation("complete", payload.get("completion_command")),
    )


def _resource_refs(
    values: object,
    *,
    purpose: str,
    scheme: str,
    normalize_path: PathNormalizer,
) -> tuple[TaskResourceRef, ...]:
    if not isinstance(values, list):
        return ()
    return tuple(
        _resource_ref(
            value,
            purpose=purpose,
            scheme=scheme,
            normalize_path=normalize_path,
        )
        for value in values
    )


def _resource_ref(
    value: object,
    *,
    purpose: str,
    scheme: str,
    normalize_path: PathNormalizer,
) -> TaskResourceRef:
    path = str(normalize_path(str(value)))
    return TaskResourceRef(
        uri=f"{scheme}://{path}",
        path=path,
        purpose=purpose,
    )


def _legacy_operation(kind: str, value: object) -> EngineOperation | None:
    command = str(value or "").strip()
    if not command:
        return None
    return EngineOperation(
        operation_id=f"legacy.command.{kind}",
        arguments={"command": command},
        display_command=command,
    )


def _explicit_human_gate(explicit: Mapping[str, object]) -> HumanGate:
    reasons = tuple(
        str(item)
        for item in explicit.get("reasons") or []
        if str(item).strip()
    )
    return HumanGate(
        bool(explicit["required"]),
        reasons,
        str(explicit.get("source") or "task-package"),
    )


def _has_explicit_contract(
    policy: str,
    role: str,
    capabilities: object,
    outputs: object,
    human_gate: object,
) -> bool:
    return bool(
        policy
        and role
        and isinstance(capabilities, list)
        and isinstance(outputs, list)
        and isinstance(human_gate, Mapping)
    )


def _capabilities(
    explicit: object,
    policy: str,
    outputs: tuple[str, ...],
) -> tuple[str, ...]:
    if isinstance(explicit, list):
        return tuple(str(item) for item in explicit if str(item).strip())
    if policy == "human-required":
        return ()
    if policy == "deterministic":
        return ("deterministic-command",)
    values = ["read-task-sources"]
    if outputs:
        values.append("write-expected-outputs")
    return tuple(values)


def _outputs(
    explicit: object,
    policy: str,
    paths: tuple[str, ...],
    *,
    normalize_path: PathNormalizer,
) -> tuple[OutputContract, ...]:
    if isinstance(explicit, list):
        return parse_output_contracts(explicit, normalize_path=normalize_path)
    return tuple(
        _derive_output_contract(
            path,
            policy,
            normalize_path=normalize_path,
        )
        for path in paths
    )


def _derive_agent_role(payload: Mapping[str, object], policy: str) -> str:
    if policy == "human-required":
        return "human-decision"
    if policy == "deterministic":
        return "deterministic-engine"
    haystack = " ".join(
        (
            str(payload.get("task_type") or ""),
            str(payload.get("prompt_asset_id") or ""),
            str(payload.get("current_state") or ""),
        )
    ).lower()
    if "review" in haystack or "audit" in haystack:
        return "main-review-agent"
    if any(token in haystack for token in CREATIVE_TASK_TOKENS):
        return "main-creative-agent"
    return "main-agent"


def _derive_output_contract(
    path: str,
    execution_policy: str,
    *,
    normalize_path: PathNormalizer,
) -> OutputContract:
    normalized = str(normalize_path(path))
    lower = normalized.lower()
    if lower.endswith(".agent_tasks.md"):
        kind, policy = "deterministic", "automatic"
    elif lower.endswith("agent_completion.json") or ".agent_completion." in lower:
        kind, policy = "completion-evidence", "automatic"
    elif "approval" in lower or lower.startswith("decisions/"):
        kind, policy = "human-approval", "approval-required"
    elif execution_policy == "deterministic":
        kind, policy = "deterministic", "automatic"
    else:
        kind = "agent-authored"
        policy = (
            "approval-required"
            if lower.startswith(HIGH_IMPACT_PREFIXES)
            else "preview-required"
        )
    return OutputContract(normalized, kind, policy)


def _strings(value: object) -> tuple[str, ...]:
    return tuple(str(item) for item in value or [])
