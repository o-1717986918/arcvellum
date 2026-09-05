"""Consumer-side validation for Literary Engineering task packages."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
from typing import Any

from .protocols.task_context import (
    validate_optional_context_contract as _validate_optional_context_contract,
)
from .protocols.review_context import (
    validate_optional_review_context_declaration as _validate_optional_review_context_declaration,
)
from literary_engineering_studio_engine.public.tasking import (
    HumanGate,
    OutputContract,
    TaskDocument,
    TaskExecutionContract,
    TaskLifecycle,
    TaskSpec,
    derive_execution_policy,
    parse_output_contracts,
    parse_task_document,
)

TASK_SCHEMA = "literary-engineering-workbench/agent-task/v1"
EXPLICIT_EXECUTION_FIELDS = {
    "execution_policy",
    "agent_role",
    "human_gate",
    "runtime_capabilities_required",
    "output_contracts",
}
PROMPT_ASSET_LIST_FIELDS = (
    "required_inputs",
    "optional_inputs",
    "context_groups",
    "hard_constraints",
    "style_constraints",
    "output_contract",
    "review_requirements",
    "forbidden_shortcuts",
)


@dataclass(frozen=True)
class TaskPackage:
    project_root: Path
    task_json_path: Path
    task_markdown_path: Path
    payload: dict[str, Any]

    @property
    def task_id(self) -> str:
        return self.task_spec.identity.task_id

    @property
    def route(self) -> str:
        return self.task_spec.identity.route

    @property
    def scene_id(self) -> str:
        return self.task_spec.identity.scene_id

    @property
    def current_state(self) -> str:
        return self.task_spec.intent.current_state

    @property
    def task_type(self) -> str:
        return self.task_spec.intent.task_type

    @property
    def command(self) -> str:
        operation = self.task_spec.operations.prepare
        return operation.display_command if operation else ""

    @property
    def source_paths(self) -> tuple[str, ...]:
        return tuple(item.path for item in self.task_spec.source_paths)

    @property
    def required_reading(self) -> tuple[str, ...]:
        return tuple(item.path for item in self.task_spec.required_reading)

    @property
    def expected_outputs(self) -> tuple[str, ...]:
        return tuple(item.path for item in self.task_spec.outputs)

    @property
    def task_document(self) -> TaskDocument:
        return parse_task_document(
            self.payload,
            normalize_path=normalize_relative_path,
        )

    @property
    def task_spec(self) -> TaskSpec:
        return self.task_document.spec

    @property
    def lifecycle(self) -> TaskLifecycle:
        return self.task_document.lifecycle

    @property
    def semantic_artifact(self) -> dict[str, str]:
        value = self.payload.get("semantic_artifact")
        if not isinstance(value, dict):
            return {}
        return {key: str(value.get(key) or "") for key in ("path", "kind", "schema_name", "consumed_by", "writeback_policy")}

    @property
    def core_managed_outputs(self) -> tuple[str, ...]:
        """Outputs created by the deterministic command, never by the Agent."""

        declared = {str(item) for item in self.expected_outputs}
        protected = {
            str(item) for item in self.payload.get("core_managed_outputs") or []
        }
        protected.update(item for item in declared if item.endswith(".agent_tasks.md"))
        return tuple(
            item for item in self.expected_outputs if item in protected
        )

    @property
    def human_gate(self) -> HumanGate:
        return self.task_spec.execution.human_gate

    @property
    def human_gate_reasons(self) -> tuple[str, ...]:
        return self.human_gate.reasons

    @property
    def execution_contract(self) -> TaskExecutionContract:
        return self.task_spec.execution

    def resolve_project_path(self, relative: str) -> Path:
        normalized = normalize_relative_path(relative)
        target = (self.project_root / Path(*normalized.parts)).resolve()
        if not target.is_relative_to(self.project_root):
            raise ValueError(f"task path escapes project root: {relative}")
        return target


def load_task_package(project_root: Path, task_json_path: Path) -> TaskPackage:
    root = project_root.resolve()
    path = task_json_path.resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"task JSON must be inside the work project: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"invalid task JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"task JSON must be an object: {path}")
    _validate_task_payload(payload)
    markdown_rel = str(payload.get("task_markdown") or "")
    if not markdown_rel:
        markdown_rel = f"workflow/tasks/{payload['task_id']}.agent_tasks.md"
    markdown_path = (root / Path(*normalize_relative_path(markdown_rel).parts)).resolve()
    if not markdown_path.exists():
        raise FileNotFoundError(f"task Markdown not found: {markdown_path}")
    return TaskPackage(root, path, markdown_path, payload)


def load_task_package_snapshot(
    project_root: Path,
    task_json_path: Path,
    task_markdown_path: Path,
) -> TaskPackage:
    """Load a machine-owned run snapshot that intentionally lives outside the project."""

    root = project_root.resolve()
    json_path = task_json_path.resolve()
    markdown_path = task_markdown_path.resolve()
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"invalid task snapshot JSON: {json_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"task snapshot JSON must be an object: {json_path}")
    _validate_task_payload(payload)
    if not markdown_path.is_file():
        raise FileNotFoundError(f"task snapshot Markdown not found: {markdown_path}")
    return TaskPackage(root, json_path, markdown_path, payload)


def normalize_relative_path(value: str) -> PurePosixPath:
    text = str(value or "").strip().replace("\\", "/")
    if not text:
        raise ValueError("task path must not be empty")
    segments = text.split("/")
    if len(segments) > 1 and segments[-1] == "":
        segments.pop()
    if any(segment in {"", ".", ".."} for segment in segments):
        raise ValueError(
            f"task path must be a normalized project-relative path: {value}"
        )
    path = PurePosixPath(*segments)
    if not path.parts or path.is_absolute() or ":" in path.parts[0]:
        raise ValueError(f"task path must be a normalized project-relative path: {value}")
    return path


def _validate_task_payload(payload: dict[str, Any]) -> None:
    if payload.get("schema") != TASK_SCHEMA:
        raise ValueError(f"unsupported task schema: {payload.get('schema')}")
    for field in ("task_id", "route", "current_state", "task_type"):
        if not str(payload.get(field) or "").strip():
            raise ValueError(f"task package missing {field}")
    for field in ("required_reading", "source_paths", "expected_outputs"):
        values = payload.get(field)
        if not isinstance(values, list):
            raise ValueError(f"task package field must be a list: {field}")
        for value in values:
            normalize_relative_path(str(value))
    for field in ("validation_gates", "forbidden_shortcuts"):
        if not isinstance(payload.get(field), list):
            raise ValueError(f"task package field must be a list: {field}")
    _validate_optional_execution_contract(payload)
    _validate_optional_context_contract(
        payload,
        normalize_path=normalize_relative_path,
    )
    _validate_optional_review_context_declaration(
        payload,
        normalize_path=normalize_relative_path,
    )


def _validate_optional_execution_contract(payload: dict[str, Any]) -> None:
    present = EXPLICIT_EXECUTION_FIELDS & set(payload)
    if present and present != EXPLICIT_EXECUTION_FIELDS:
        missing = ", ".join(sorted(EXPLICIT_EXECUTION_FIELDS - present))
        raise ValueError(f"partial explicit execution contract; missing: {missing}")
    _validate_execution_policy_fields(payload)
    _validate_execution_output_fields(payload)
    _validate_semantic_artifact(payload)
    _validate_prompt_asset(payload)


def _validate_execution_policy_fields(payload: dict[str, Any]) -> None:
    if "execution_policy" in payload and payload["execution_policy"] not in {
        "deterministic",
        "agent-required",
        "human-required",
    }:
        raise ValueError("task package execution_policy is invalid")
    if "agent_role" in payload and not str(payload["agent_role"] or "").strip():
        raise ValueError("task package agent_role must not be empty")
    if "human_gate" in payload:
        gate = payload["human_gate"]
        if not isinstance(gate, dict) or not isinstance(gate.get("required"), bool):
            raise ValueError("task package human_gate must contain a boolean required field")
        if not isinstance(gate.get("reasons", []), list):
            raise ValueError("task package human_gate.reasons must be a list")


def _validate_execution_output_fields(payload: dict[str, Any]) -> None:
    for field in ("runtime_capabilities_required", "output_contracts"):
        if field in payload and not isinstance(payload[field], list):
            raise ValueError(f"task package field must be a list: {field}")
    if "output_contracts" in payload:
        parse_output_contracts(
            payload["output_contracts"],
            normalize_path=normalize_relative_path,
        )


def _validate_semantic_artifact(payload: dict[str, Any]) -> None:
    if "semantic_artifact" not in payload:
        return
    semantic = payload["semantic_artifact"]
    if not isinstance(semantic, dict):
        raise ValueError("task package semantic_artifact must be an object")
    path = str(semantic.get("path") or "").strip()
    if not path or path not in {str(item) for item in payload.get("expected_outputs") or []}:
        raise ValueError("task package semantic_artifact path must be an expected output")
    for field in ("kind", "schema_name", "consumed_by"):
        if not str(semantic.get(field) or "").strip():
            raise ValueError(f"task package semantic_artifact.{field} must not be empty")
    if str(semantic.get("writeback_policy") or "") not in {"automatic", "preview-required", "approval-required", "none"}:
        raise ValueError("task package semantic_artifact.writeback_policy is invalid")


def _validate_prompt_asset(payload: dict[str, Any]) -> None:
    prompt_asset = payload.get("prompt_asset")
    if prompt_asset is None:
        return
    if not isinstance(prompt_asset, dict):
        raise ValueError("task package prompt_asset must be an object")
    for field in ("requested_id", "resolved_id", "version", "body"):
        if not str(prompt_asset.get(field) or "").strip():
            raise ValueError(f"task package prompt_asset.{field} must not be empty")
    for field in PROMPT_ASSET_LIST_FIELDS:
        if not isinstance(prompt_asset.get(field), list):
            raise ValueError(f"task package prompt_asset.{field} must be a list")


def _derive_execution_policy(payload: dict[str, Any], human_gate: HumanGate) -> str:
    return derive_execution_policy(payload, human_gate)
