"""Stable task-package, completion, and semantic-contract API."""

from ..tasking.agent_tasks.writer import (
    agent_task_completion_status,
    write_agent_completion_marker,
)
from ..tasking.gates import branch_selection_status
from ..tasking.registry import issue_next_task
from ..tasking.semantic_contracts import (
    semantic_artifact_definition,
    semantic_artifact_errors,
    semantic_artifact_relative_path,
    semantic_artifact_template,
    validated_branch_proposal_ids,
)
from ..tasking.operations import (
    ENGINE_OPERATION_SCHEMA,
    operation_from_legacy_command,
    operation_from_payload,
    operation_parameters,
    OPERATION_REGISTRY,
    resolve_operation_argv,
)
from ..tasking.state_contracts import SCENE_CANDIDATE_STATES, SCENE_REVISION_STATES
from ..tasking.spec import (
    EngineOperation,
    HumanGate,
    OutputContract,
    TaskDocument,
    TaskExecutionContract,
    TaskIdentity,
    TaskIntent,
    TaskLifecycle,
    TaskOperations,
    TaskResourceRef,
    TaskSpec,
    derive_execution_policy,
    infer_human_gate,
    parse_execution_contract,
    parse_output_contracts,
    parse_task_document,
)

__all__ = [
    "agent_task_completion_status",
    "branch_selection_status",
    "derive_execution_policy",
    "ENGINE_OPERATION_SCHEMA",
    "EngineOperation",
    "HumanGate",
    "infer_human_gate",
    "issue_next_task",
    "operation_from_legacy_command",
    "operation_from_payload",
    "operation_parameters",
    "OPERATION_REGISTRY",
    "OutputContract",
    "parse_execution_contract",
    "parse_output_contracts",
    "parse_task_document",
    "resolve_operation_argv",
    "semantic_artifact_definition",
    "semantic_artifact_errors",
    "semantic_artifact_relative_path",
    "semantic_artifact_template",
    "SCENE_CANDIDATE_STATES",
    "SCENE_REVISION_STATES",
    "TaskDocument",
    "TaskExecutionContract",
    "TaskIdentity",
    "TaskIntent",
    "TaskLifecycle",
    "TaskOperations",
    "TaskResourceRef",
    "TaskSpec",
    "validated_branch_proposal_ids",
    "write_agent_completion_marker",
]
