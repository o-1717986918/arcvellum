"""Stable imports for typed ArcVellum task protocol values."""

from .spec_models import (
    EXECUTION_CONTRACT_SCHEMA,
    TASK_SCHEMA_V1,
    TASK_SCHEMA_V2,
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
)
from .spec_v1 import (
    derive_execution_policy,
    infer_human_gate,
    parse_execution_contract,
    parse_output_contracts,
    parse_task_document as parse_task_document_v1,
)
from .spec_v2 import (
    parse_task_document_v2,
    task_document_to_v2,
    task_semantic_fingerprint,
)


def parse_task_document(payload, *, normalize_path):
    schema = str(payload.get("schema") or "")
    if not schema or schema == TASK_SCHEMA_V1:
        return parse_task_document_v1(payload, normalize_path=normalize_path)
    if schema == TASK_SCHEMA_V2:
        return parse_task_document_v2(payload, normalize_path=normalize_path)
    raise ValueError(f"unsupported task schema: {schema or 'missing'}")

__all__ = [
    "derive_execution_policy",
    "EngineOperation",
    "EXECUTION_CONTRACT_SCHEMA",
    "HumanGate",
    "infer_human_gate",
    "OutputContract",
    "parse_execution_contract",
    "parse_output_contracts",
    "parse_task_document",
    "TASK_SCHEMA_V1",
    "TASK_SCHEMA_V2",
    "TaskDocument",
    "TaskExecutionContract",
    "TaskIdentity",
    "TaskIntent",
    "TaskLifecycle",
    "TaskOperations",
    "TaskResourceRef",
    "TaskSpec",
    "task_document_to_v2",
    "task_semantic_fingerprint",
]
