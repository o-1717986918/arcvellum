"""Strict JSON codecs for immutable orchestration contracts."""

from __future__ import annotations

from dataclasses import MISSING, fields, is_dataclass
from enum import Enum
from types import UnionType
from typing import Any, TypeVar, Union, get_args, get_origin, get_type_hints

from .contracts import CompiledTaskGraph, CreativeExecutionPlan


_T = TypeVar("_T")


def parse_creative_execution_plan(payload: dict[str, Any]) -> CreativeExecutionPlan:
    return _parse_dataclass(CreativeExecutionPlan, payload, "creative execution plan")


def parse_compiled_task_graph(payload: dict[str, Any]) -> CompiledTaskGraph:
    return _parse_dataclass(CompiledTaskGraph, payload, "compiled task graph")


def _parse_dataclass(cls: type[_T], payload: object, label: str) -> _T:
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be an object")
    known = {field.name for field in fields(cls)}
    unknown = sorted(set(payload) - known)
    if unknown:
        raise ValueError(f"{label} contains unknown fields: {', '.join(unknown)}")
    hints = get_type_hints(cls)
    values: dict[str, Any] = {}
    for field in fields(cls):
        if field.name in payload:
            values[field.name] = _parse_value(
                hints[field.name],
                payload[field.name],
                f"{label}.{field.name}",
            )
            continue
        if field.default is MISSING and field.default_factory is MISSING:
            raise ValueError(f"{label} is missing field: {field.name}")
    return cls(**values)


def _parse_value(annotation: object, value: object, label: str) -> Any:
    if annotation is Any:
        return value
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin in {tuple, list, dict}:
        return _parse_container(origin, args, value, label)
    if origin in {Union, UnionType}:
        return _parse_union(args, value, label)
    if annotation is type(None):
        if value is not None:
            raise ValueError(f"{label} must be null")
        return None
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        try:
            return annotation(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} has an unsupported enum value") from exc
    if isinstance(annotation, type) and is_dataclass(annotation):
        return _parse_dataclass(annotation, value, label)
    return _parse_primitive(annotation, value, label)


def _parse_container(
    origin: object,
    args: tuple[object, ...],
    value: object,
    label: str,
) -> Any:
    if origin in {tuple, list}:
        if not isinstance(value, list):
            raise ValueError(f"{label} must be an array")
        item_type = args[0] if args else Any
        parsed = [
            _parse_value(item_type, item, f"{label}[{index}]")
            for index, item in enumerate(value)
        ]
        return tuple(parsed) if origin is tuple else parsed
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    key_type, item_type = args or (Any, Any)
    return {
        _parse_value(key_type, key, f"{label}.key"): _parse_value(
            item_type,
            item,
            f"{label}.{key}",
        )
        for key, item in value.items()
    }


def _parse_union(
    options: tuple[object, ...],
    value: object,
    label: str,
) -> Any:
    failures: list[str] = []
    for option in options:
        try:
            return _parse_value(option, value, label)
        except ValueError as exc:
            failures.append(str(exc))
    raise ValueError(f"{label} does not match its contract: {'; '.join(failures)}")


def _parse_primitive(annotation: object, value: object, label: str) -> Any:
    if annotation is bool:
        if type(value) is not bool:
            raise ValueError(f"{label} must be a boolean")
        return value
    if annotation is int:
        if type(value) is not int:
            raise ValueError(f"{label} must be an integer")
        return value
    if annotation is float:
        if type(value) not in {int, float}:
            raise ValueError(f"{label} must be a number")
        return float(value)
    if annotation is str:
        if not isinstance(value, str):
            raise ValueError(f"{label} must be a string")
        return value
    raise ValueError(f"{label} uses an unsupported contract type")
