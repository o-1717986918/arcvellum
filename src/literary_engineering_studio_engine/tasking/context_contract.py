"""Cross-route normalization for Engine-owned task context contracts."""

from __future__ import annotations

from pathlib import PurePosixPath


CONTEXT_CONTRACT_SCHEMA = (
    "literary-engineering-workbench/task-context-contract/v1"
)
CONTEXT_CONTRACT_FIELDS = {
    "context_contract_required",
    "context_contract_schema",
    "context_contract_revision",
    "context_contract_status",
    "context_must_inline_paths",
}
CONTEXT_CONTRACT_STATUSES = {"shadow-ready", "bounded-ready"}
CONTEXT_CONTRACT_FINGERPRINT_FIELDS = (
    "context_contract_required",
    "context_contract_schema",
    "context_contract_revision",
    "context_contract_status",
    "context_must_inline_paths",
    "context_summary_references",
    "context_excluded_paths",
)
CONTEXT_SOURCE_FIELDS = (
    "agent_source_paths",
    "core_managed_outputs",
    "required_reading",
)


def normalize_context_contract(task: dict[str, object]) -> None:
    present = CONTEXT_CONTRACT_FIELDS & set(task)
    if not present:
        return
    _validate_header(task, present)
    normalized = _mandatory_paths(task)
    allowed = {
        path
        for field in CONTEXT_SOURCE_FIELDS
        for path in _path_list(task, field)
    }
    unauthorized = [path for path in normalized if path not in allowed]
    if unauthorized:
        raise ValueError(
            "formal task mandatory context is outside the Agent source contract: "
            + ", ".join(unauthorized)
        )
    task["context_must_inline_paths"] = normalized


def _validate_header(task: dict[str, object], present: set[str]) -> None:
    if task.get("context_contract_required") is not True:
        raise ValueError(
            "formal task context_contract_required must be true when a contract is present"
        )
    missing = CONTEXT_CONTRACT_FIELDS - present
    if missing:
        raise ValueError(
            "formal task has a partial context contract; missing: "
            + ", ".join(sorted(missing))
        )
    if task.get("context_contract_schema") != CONTEXT_CONTRACT_SCHEMA:
        raise ValueError("formal task context contract schema is invalid")
    if not str(task.get("context_contract_revision") or "").strip():
        raise ValueError("formal task context contract revision is required")
    if str(task.get("context_contract_status") or "") not in CONTEXT_CONTRACT_STATUSES:
        raise ValueError("formal task context contract status is invalid")


def _mandatory_paths(task: dict[str, object]) -> list[str]:
    values = task.get("context_must_inline_paths")
    if not isinstance(values, list) or not values:
        raise ValueError(
            "formal task context_must_inline_paths must be a non-empty list"
        )
    normalized = [_normalize_path(item) for item in values]
    if len(normalized) != len(set(normalized)):
        raise ValueError("formal task context_must_inline_paths contains duplicates")
    return normalized


def _path_list(task: dict[str, object], field: str) -> list[str]:
    value = task.get(field)
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"formal task context source field must be a list: {field}")
    return [_normalize_path(item) for item in value]


def _normalize_path(value: object) -> str:
    text = str(value or "").strip().replace("\\", "/")
    if not text:
        raise ValueError("formal task context path must not be empty")
    path = PurePosixPath(text)
    if (
        path.is_absolute()
        or ":" in path.parts[0]
        or any(part in {"", ".", ".."} for part in path.parts)
        or text.endswith("/")
    ):
        raise ValueError(
            f"formal task context path must be a normalized file path: {value}"
        )
    return path.as_posix()
