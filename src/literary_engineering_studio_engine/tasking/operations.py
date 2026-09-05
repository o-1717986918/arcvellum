"""Registry and transport helpers for structured Engine operations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shlex
from types import MappingProxyType
from typing import Mapping, Sequence

from .spec_models import EngineOperation


ENGINE_OPERATION_SCHEMA = "arcvellum/engine-operation/v1"
ENGINE_MODULE = "literary_engineering_studio_engine"
ENGINE_OPERATION_PREFIX = "arcvellum.engine/"
TASK_SUBMIT_OPERATION = "arcvellum.task/submit.v1"
TASK_COMPLETE_OPERATION = "arcvellum.task/complete.v1"

FORBIDDEN_OPERATION_TOKENS = (
    "--allow-unreviewed",
    "--allow-review-notes",
    "--include-blocked",
    "--allow-unapproved",
    "--allow-unresolved",
    "--allow-missing-composition",
    "--allow-unselected-composition",
    "--allow-recommended-branch",
    "--allow-missing-branch",
    "LEW_MAINTAINER_MODE",
)

FORMAL_PREPARE_SUBCOMMANDS = frozenset(
    {
        "agent-canon-review",
        "agent-committee",
        "agent-review-scene",
        "apply-continuity-ledger",
        "archaeology-aggregate",
        "archaeology-materialize",
        "asset-create",
        "branch-simulate",
        "build-style-version",
        "canon-apply",
        "canon-evolve",
        "canon-lint",
        "chapter-obligation",
        "chapter-workspace",
        "compose-scene",
        "context",
        "export-package",
        "generate-scene",
        "longform-audit",
        "materialize-longform-plan",
        "plan-length-repair",
        "prepare-continuity-ledger",
        "prepare-continuity-ledger-review",
        "prepare-longform-review",
        "prepare-scene-character-assets",
        "prepare-story-architecture",
        "prepare-story-architecture-review",
        "prepare-style-review",
        "promote-candidate",
        "promote-candidate-asset",
        "publish-chapter",
        "review-candidate-asset",
        "review-scene",
        "revise-scene",
        "scene-handoff",
        "seed-project-assets",
        "simulate-scene",
        "source-ingest",
        "state-apply",
        "state-evolve",
        "style-eval",
        "style-profile",
        "style-prompt",
        "style-prompt-eval",
        "word-budget",
    }
)


@dataclass(frozen=True)
class OperationDefinition:
    operation_id: str
    phase: str
    subcommand: str


def prepare_operation_id(subcommand: str) -> str:
    return f"{ENGINE_OPERATION_PREFIX}{subcommand}.v1"


def _prepare_definitions() -> dict[str, OperationDefinition]:
    return {
        prepare_operation_id(command): OperationDefinition(
            operation_id=prepare_operation_id(command),
            phase="prepare",
            subcommand=command,
        )
        for command in sorted(FORMAL_PREPARE_SUBCOMMANDS)
    }


OPERATION_REGISTRY: Mapping[str, OperationDefinition] = MappingProxyType(
    {
        **_prepare_definitions(),
        TASK_SUBMIT_OPERATION: OperationDefinition(
            TASK_SUBMIT_OPERATION,
            "submit",
            "task-submit",
        ),
        TASK_COMPLETE_OPERATION: OperationDefinition(
            TASK_COMPLETE_OPERATION,
            "complete",
            "task-complete",
        ),
    }
)


def build_task_operations(task: Mapping[str, object]) -> dict[str, object]:
    """Build structured operations while preserving v1 display commands."""

    if str(task.get("execution_policy") or "") == "human-required":
        return {}
    operations: dict[str, object] = {}
    prepare = operation_from_legacy_command(str(task.get("command") or ""))
    if prepare is not None:
        operations["prepare"] = prepare.as_dict()
    task_id = str(task.get("task_id") or "").strip()
    if str(task.get("submission_command") or "").strip() and task_id:
        operations["submit"] = EngineOperation(
            operation_id=TASK_SUBMIT_OPERATION,
            arguments={"task_id": task_id},
            display_command=str(task["submission_command"]),
        ).as_dict()
    if str(task.get("completion_command") or "").strip() and task_id:
        operations["complete"] = EngineOperation(
            operation_id=TASK_COMPLETE_OPERATION,
            arguments={"task_id": task_id},
            display_command=str(task["completion_command"]),
        ).as_dict()
    return operations


def operation_from_legacy_command(command: str) -> EngineOperation | None:
    """Upgrade one trusted v1 Engine command into an argument-vector operation."""

    text = str(command or "").strip()
    if not text:
        return None
    parts = [_unquote(item) for item in shlex.split(text, posix=False)]
    try:
        module_index = parts.index("-m")
    except ValueError:
        return None
    if module_index + 1 >= len(parts) or parts[module_index + 1] != ENGINE_MODULE:
        return None
    argv = parts[module_index + 2 :]
    if not argv:
        raise ValueError("task command does not contain an Engine subcommand")
    operation_id = prepare_operation_id(argv[0])
    if operation_id not in OPERATION_REGISTRY:
        raise ValueError(f"unregistered formal Engine operation: {argv[0]}")
    return EngineOperation(
        operation_id=operation_id,
        arguments={"argv": argv},
        display_command=text,
    )


def operation_from_payload(value: object) -> EngineOperation | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("task operation must be an object")
    schema = str(value.get("schema") or "")
    if schema and schema != ENGINE_OPERATION_SCHEMA:
        raise ValueError(f"unsupported task operation schema: {schema}")
    operation_id = str(value.get("operation_id") or "").strip()
    arguments = value.get("arguments")
    if not operation_id or not isinstance(arguments, Mapping):
        raise ValueError("task operation requires operation_id and arguments")
    return EngineOperation(
        operation_id=operation_id,
        arguments=arguments,
        display_command=str(value.get("display_command") or ""),
    )


def operation_parameters(operation: EngineOperation | None) -> tuple[str, ...]:
    if operation is None:
        return ()
    definition = OPERATION_REGISTRY.get(operation.operation_id)
    if definition is not None and definition.phase != "prepare":
        return ()
    source = operation.display_command or " ".join(_operation_argv(operation))
    normalized = source.replace("<project>", "")
    optional_values = [item.strip() for item in re.findall(r"\[([^\]]+)\]", normalized)]
    required_source = re.sub(r"\[[^\]]+\]", "", normalized)
    values = [item.strip() for item in re.findall(r"<([^>]+)>", required_source)]
    values.extend(optional_values)
    return tuple(dict.fromkeys(item for item in values if item))


def resolve_operation_argv(
    operation: EngineOperation,
    project: Path,
    *,
    artifacts: Sequence[str] = (),
    handled_by: str = "",
    note: str = "",
) -> tuple[str, ...]:
    """Resolve a registered operation to the Engine CLI handler argument vector."""

    definition = OPERATION_REGISTRY.get(operation.operation_id)
    if definition is None:
        return _resolve_legacy_operation(
            operation,
            project,
            artifacts=artifacts,
            handled_by=handled_by,
            note=note,
        )
    argv = _registered_operation_argv(
        operation,
        definition,
        artifacts=artifacts,
        handled_by=handled_by,
        note=note,
    )
    if definition.phase == "prepare" and operation_parameters(operation):
        raise ValueError(
            "task operation requires: " + ", ".join(operation_parameters(operation))
        )
    _validate_operation_argv(argv)
    return _bind_project(argv, project)


def _resolve_legacy_operation(
    operation: EngineOperation,
    project: Path,
    **bindings: object,
) -> tuple[str, ...]:
    if not operation.operation_id.startswith("legacy.command."):
        raise ValueError(f"unknown Engine operation: {operation.operation_id}")
    command = str(operation.arguments.get("command") or operation.display_command)
    upgraded = operation_from_legacy_command(command)
    if upgraded is None:
        raise ValueError("legacy task command is not a registered Engine operation")
    return resolve_operation_argv(upgraded, project, **bindings)


def _registered_operation_argv(
    operation: EngineOperation,
    definition: OperationDefinition,
    *,
    artifacts: Sequence[str],
    handled_by: str,
    note: str,
) -> tuple[str, ...]:
    if definition.phase == "prepare":
        argv = _operation_argv(operation)
        if not argv or argv[0] != definition.subcommand:
            raise ValueError("Engine operation arguments do not match its registered subcommand")
        return argv
    if definition.phase == "submit":
        return _submit_argv(operation, artifacts=artifacts, note=note)
    return _complete_argv(operation, handled_by=handled_by, note=note)


def _submit_argv(
    operation: EngineOperation,
    *,
    artifacts: Sequence[str],
    note: str,
) -> tuple[str, ...]:
    if not artifacts:
        raise ValueError("task submit operation requires at least one artifact")
    values = [
        "task-submit",
        "<project>",
        "--task-id",
        _required_argument(operation, "task_id"),
    ]
    for artifact in artifacts:
        values.extend(["--from", str(artifact)])
    if note:
        values.extend(["--note", note])
    return tuple(values)


def _complete_argv(
    operation: EngineOperation,
    *,
    handled_by: str,
    note: str,
) -> tuple[str, ...]:
    if not handled_by:
        raise ValueError("task complete operation requires handled_by")
    values = [
        "task-complete",
        "<project>",
        "--task-id",
        _required_argument(operation, "task_id"),
        "--handled-by",
        handled_by,
    ]
    if note:
        values.extend(["--note", note])
    return tuple(values)


def _bind_project(argv: Sequence[str], project: Path) -> tuple[str, ...]:
    root = str(project.resolve())
    return tuple(
        root if item == "<project>" else item.replace("<project>", root)
        for item in argv
    )


def _operation_argv(operation: EngineOperation) -> tuple[str, ...]:
    value = operation.arguments.get("argv")
    if not isinstance(value, tuple):
        if not isinstance(value, list):
            raise ValueError("prepare operation requires an argv list")
    return tuple(str(item) for item in value)


def _required_argument(operation: EngineOperation, name: str) -> str:
    value = str(operation.arguments.get(name) or "").strip()
    if not value:
        raise ValueError(f"Engine operation requires argument: {name}")
    return value


def _validate_operation_argv(argv: Sequence[str]) -> None:
    if not argv:
        raise ValueError("Engine operation argument vector is empty")
    if any(token in item for item in argv for token in FORBIDDEN_OPERATION_TOKENS):
        raise ValueError("Engine operation contains a formal-mode bypass token")
    if any(item in {"&&", "||", "|", ">", "<", ";", "`"} for item in argv):
        raise ValueError("legacy task operation contains unsupported shell syntax")


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


__all__ = [
    "build_task_operations",
    "ENGINE_OPERATION_SCHEMA",
    "FORMAL_PREPARE_SUBCOMMANDS",
    "operation_from_legacy_command",
    "operation_from_payload",
    "operation_parameters",
    "OPERATION_REGISTRY",
    "OperationDefinition",
    "prepare_operation_id",
    "resolve_operation_argv",
    "TASK_COMPLETE_OPERATION",
    "TASK_SUBMIT_OPERATION",
]
