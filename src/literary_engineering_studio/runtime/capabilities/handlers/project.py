"""Curated project and schema inspection capabilities."""

from __future__ import annotations

from typing import Any

from ruamel.yaml import YAML

from literary_engineering_studio_engine.prompting.agents.schema import load_schema_spec

from ..context import CapabilityContext
from ..contracts import HandlerOutput


PROJECT_FIELDS = (
    "title",
    "project_id",
    "language",
    "genre",
    "format",
    "status",
    "target_word_count",
    "target_words",
    "target_chapters",
    "target_volumes",
)


def project_query(context: CapabilityContext, arguments: dict[str, Any]) -> HandlerOutput:
    query = str(arguments.get("query") or "overview").strip().lower()
    if query == "task":
        data = {
            "task_id": context.task.task_id,
            "route": context.task.route,
            "current_state": context.task.current_state,
            "agent_role": context.task.execution_contract.agent_role,
            "expected_output_count": len(context.manifest.writable_paths),
        }
    elif query == "sources":
        data = {
            "readable_paths": list(context.manifest.readable_paths),
            "writable_paths": list(context.manifest.writable_paths),
        }
    elif query == "overview":
        descriptor = context.task.project_root / "project.yaml"
        parsed: dict[str, Any] = {}
        if descriptor.is_file():
            loaded = YAML(typ="safe").load(descriptor.read_text(encoding="utf-8"))
            parsed = loaded if isinstance(loaded, dict) else {}
        data = {key: parsed[key] for key in PROJECT_FIELDS if key in parsed}
        data["route"] = context.task.route
        data["current_state"] = context.task.current_state
    else:
        raise ValueError("project.query supports only overview, task, or sources")
    return HandlerOutput(f"project query completed: {query}", data)


def schema_inspect(_context: CapabilityContext, arguments: dict[str, Any]) -> HandlerOutput:
    schema_name = str(arguments.get("schema_name") or "").strip()
    if not schema_name:
        raise ValueError("schema_name is required")
    spec = load_schema_spec(schema_name)
    data = {
        "schema_name": schema_name,
        "schema_value": spec.get("schema_value", ""),
        "required": list(spec.get("required") or []),
        "recommended": list(spec.get("recommended") or []),
        "types": dict(spec.get("types") or {}),
        "enums": dict(spec.get("enums") or {}),
    }
    return HandlerOutput(f"schema inspected: {schema_name}", data)
