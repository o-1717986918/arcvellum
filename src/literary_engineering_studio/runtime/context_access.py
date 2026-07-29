"""Safe context-read telemetry derived from completed Agent tool messages."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


CONTEXT_ACCESS_SCHEMA = "arcvellum/context-access-summary/v1"
_READ_TOOLS = {"read"}
_PATH_KEYS = ("filePath", "file_path", "filepath", "path")


def summarize_context_access(
    messages: Iterable[Mapping[str, Any]],
    workspace: Path,
) -> dict[str, object]:
    """Return counts only; never retain tool output, prose, or absolute paths."""

    root = workspace.resolve()
    contract = _task_context(root)
    execution = _mapping(contract.get("execution_context"))
    must_inline = set(_strings(execution.get("must_inline")))
    exact = set(_strings(execution.get("exact_on_demand")))
    expected_outputs = set(_strings(contract.get("expected_outputs")))
    expected_output_parents = _expected_output_parent_paths(
        expected_outputs
    )
    authorized = {
        *must_inline,
        *exact,
        *_strings(contract.get("source_paths")),
        *_strings(contract.get("reference_paths")),
        *_strings(contract.get("core_managed_outputs")),
    }
    counters = {
        "read_tool_calls": 0,
        "unique_read_targets": 0,
        "exact_on_demand_read_calls": 0,
        "exact_on_demand_unique_files": 0,
        "exact_on_demand_read_characters": 0,
        "must_inline_reread_calls": 0,
        "expected_output_read_calls": 0,
        "infrastructure_read_calls": 0,
        "other_authorized_read_calls": 0,
        "unmapped_read_calls": 0,
        "redundant_read_calls": 0,
    }
    seen: set[str] = set()
    exact_seen: set[str] = set()
    for tool, raw_path in _completed_reads(messages):
        if tool not in _READ_TOOLS:
            continue
        counters["read_tool_calls"] += 1
        relative = _workspace_relative(root, raw_path)
        if relative is None:
            counters["unmapped_read_calls"] += 1
            continue
        if relative in seen:
            counters["redundant_read_calls"] += 1
        else:
            seen.add(relative)
        if relative in exact:
            counters["exact_on_demand_read_calls"] += 1
            if relative not in exact_seen:
                exact_seen.add(relative)
                counters["exact_on_demand_read_characters"] += (
                    _text_character_count(root / Path(relative))
                )
        elif relative in must_inline:
            counters["must_inline_reread_calls"] += 1
        elif relative in expected_outputs:
            counters["expected_output_read_calls"] += 1
        elif relative in expected_output_parents:
            counters["expected_output_read_calls"] += 1
        elif _is_infrastructure_target(relative):
            counters["infrastructure_read_calls"] += 1
        elif relative in authorized:
            counters["other_authorized_read_calls"] += 1
        else:
            counters["unmapped_read_calls"] += 1
    counters["unique_read_targets"] = len(seen)
    counters["exact_on_demand_unique_files"] = len(exact_seen)
    digest = _digest(counters)
    return {
        "schema": CONTEXT_ACCESS_SCHEMA,
        **counters,
        "digest": digest,
    }


def _completed_reads(
    messages: Iterable[Mapping[str, Any]],
) -> Iterable[tuple[str, str]]:
    for message in messages:
        parts = message.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if not isinstance(part, Mapping) or part.get("type") != "tool":
                continue
            state = _mapping(part.get("state"))
            if str(state.get("status") or "") != "completed":
                continue
            tool = str(part.get("tool") or part.get("name") or "").lower()
            payload = _tool_input(part, state)
            raw_path = _path_value(payload)
            yield tool, raw_path


def _tool_input(
    part: Mapping[str, Any],
    state: Mapping[str, Any],
) -> Mapping[str, Any]:
    value = state.get("input")
    if value is None:
        value = part.get("input")
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return _mapping(parsed)
    return _mapping(value)


def _path_value(payload: Mapping[str, Any]) -> str:
    for key in _PATH_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _workspace_relative(root: Path, value: str) -> str | None:
    if not value:
        return None
    candidate = Path(value)
    resolved = (
        candidate.resolve()
        if candidate.is_absolute()
        else (root / candidate).resolve()
    )
    if not resolved.is_relative_to(root):
        return None
    return resolved.relative_to(root).as_posix()


def _task_context(workspace: Path) -> Mapping[str, Any]:
    path = workspace / "TASK_CONTEXT.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return _mapping(payload)


def _is_infrastructure_target(relative: str) -> bool:
    return (
        relative in {
            ".",
            "agent",
            "TASK.json",
            "TASK_CONTEXT.json",
            "AGENT_TASK.md",
            "AGENT_PROGRAM.md",
        }
        or relative.startswith("agent/")
    )


def _expected_output_parent_paths(paths: Iterable[str]) -> set[str]:
    parents: set[str] = set()
    for item in paths:
        parent = Path(item).parent
        while parent.as_posix() != ".":
            parents.add(parent.as_posix())
            parent = parent.parent
    return parents


def _text_character_count(path: Path) -> int:
    try:
        content = path.read_bytes()
    except OSError:
        return 0
    if b"\x00" in content:
        return 0
    try:
        return len(content.decode("utf-8"))
    except UnicodeDecodeError:
        return 0


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(
        dict.fromkeys(
            str(item).strip().replace("\\", "/")
            for item in value
            if str(item).strip()
        )
    )


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _digest(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = ["CONTEXT_ACCESS_SCHEMA", "summarize_context_access"]
