"""Closed field sets for the ArcVellum task/v2 protocol."""

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

__all__ = [
    "EXECUTION_KEYS",
    "HUMAN_GATE_KEYS",
    "IDENTITY_KEYS",
    "INTENT_KEYS",
    "LIFECYCLE_KEYS",
    "OPERATIONS_KEYS",
    "OUTPUT_KEYS",
    "RESERVED_V1_EXTENSION_KEYS",
    "RESOURCE_KEYS",
    "RESOURCES_KEYS",
    "ROOT_KEYS",
    "SPEC_KEYS",
    "VALIDATION_KEYS",
]
