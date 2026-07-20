"""Schema validation and repair helpers for persisted agent runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agent_provider import run_agent_task
from .resources import engine_path


SCHEMA_DIR = engine_path("schemas", "agent_outputs")


@dataclass(frozen=True)
class AgentSchemaValidationResult:
    project_root: Path
    run_dir: Path
    schema_name: str
    status: str
    validation_path: Path
    error_count: int
    warning_count: int


@dataclass(frozen=True)
class AgentRepairResult:
    project_root: Path
    source_run_dir: Path
    repair_run_dir: Path
    schema_name: str
    validation_path: Path
    status: str


def validate_agent_run(project_root: Path, *, run_id: str = "", run_dir: Path | None = None, schema_name: str) -> AgentSchemaValidationResult:
    root = project_root.resolve()
    resolved_run_dir = _resolve_run_dir(root, run_id=run_id, run_dir=run_dir)
    parsed_path = resolved_run_dir / "parsed_output.json"
    if not parsed_path.exists():
        raise FileNotFoundError(f"parsed agent output not found: {parsed_path}")
    payload = json.loads(parsed_path.read_text(encoding="utf-8"))
    errors, warnings = validate_payload(payload, schema_name)
    status = "pass" if not errors else "failed"
    validation_path = resolved_run_dir / "schema_validation.json"
    report = {
        "schema": "literary-engineering-workbench/agent-schema-validation/v0.1",
        "generated_at": _now(),
        "schema_name": schema_name,
        "status": status,
        "run_dir": _rel_str(resolved_run_dir, root),
        "parsed_output": _rel_str(parsed_path, root),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
    validation_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return AgentSchemaValidationResult(
        project_root=root,
        run_dir=resolved_run_dir,
        schema_name=schema_name,
        status=status,
        validation_path=validation_path,
        error_count=len(errors),
        warning_count=len(warnings),
    )


def repair_agent_run(
    project_root: Path,
    *,
    run_id: str = "",
    run_dir: Path | None = None,
    schema_name: str,
    provider: str = "auto",
) -> AgentRepairResult:
    root = project_root.resolve()
    source_run_dir = _resolve_run_dir(root, run_id=run_id, run_dir=run_dir)
    parsed_path = source_run_dir / "parsed_output.json"
    raw_path = source_run_dir / "raw_output.md"
    validation_path = source_run_dir / "schema_validation.json"
    if not parsed_path.exists():
        raise FileNotFoundError(f"parsed agent output not found: {parsed_path}")
    if not validation_path.exists():
        validate_agent_run(root, run_dir=source_run_dir, schema_name=schema_name)
    parsed_text = parsed_path.read_text(encoding="utf-8")
    raw_text = raw_path.read_text(encoding="utf-8") if raw_path.exists() else ""
    validation_text = validation_path.read_text(encoding="utf-8")

    repair_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    repair_dir = source_run_dir / "repair_attempts" / repair_id
    spec = load_schema_spec(schema_name)
    system_prompt = "You repair agent JSON so it conforms exactly to the requested schema. Output JSON only."
    user_prompt = f"""Repair the agent output for schema `{schema_name}`.

Schema spec:
```json
{json.dumps(spec, ensure_ascii=False, indent=2)}
```

Schema validation:
```json
{validation_text}
```

Parsed output:
```json
{parsed_text}
```

Raw output:
```text
{raw_text[:6000]}
```
"""
    run_result = run_agent_task(
        root,
        agent_id=f"{schema_name.replace('.', '-')}-repairer",
        task="repair-json",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        provider=provider,
        output_dir=repair_dir,
        metadata={"source_run_dir": _rel_str(source_run_dir, root), "schema_name": schema_name},
        dry_run_output=minimal_payload(schema_name),
    )
    validation = validate_agent_run(root, run_dir=run_result.run_dir, schema_name=schema_name)
    return AgentRepairResult(
        project_root=root,
        source_run_dir=source_run_dir,
        repair_run_dir=run_result.run_dir,
        schema_name=schema_name,
        validation_path=validation.validation_path,
        status=validation.status,
    )


def validate_payload(payload: dict[str, Any], schema_name: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    spec = load_schema_spec(schema_name)
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    expected_schema = spec.get("schema_value", "")
    if expected_schema and payload.get("schema") != expected_schema:
        errors.append({"path": "schema", "message": f"expected {expected_schema}", "actual": str(payload.get("schema", ""))})
    for field in spec.get("required", []):
        if field not in payload:
            errors.append({"path": field, "message": "required field missing", "actual": ""})
    type_map = spec.get("types", {})
    for field, expected_type in type_map.items():
        if field in payload and not _matches_type(payload[field], str(expected_type)):
            errors.append({"path": field, "message": f"expected type {expected_type}", "actual": type(payload[field]).__name__})
    enum_map = spec.get("enums", {})
    for field, values in enum_map.items():
        if field in payload and payload[field] not in values:
            errors.append({"path": field, "message": "value not in enum", "actual": str(payload[field])})
    for field in spec.get("recommended", []):
        if field not in payload:
            warnings.append({"path": field, "message": "recommended field missing", "actual": ""})
    return errors, warnings


def load_schema_spec(schema_name: str) -> dict[str, Any]:
    safe = schema_name.strip()
    if not safe or "/" in safe or "\\" in safe or ".." in safe:
        raise ValueError("invalid schema name")
    path = SCHEMA_DIR / f"{safe}.schema.json"
    if not path.exists():
        raise FileNotFoundError(f"agent schema not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def minimal_payload(schema_name: str, **overrides: Any) -> dict[str, Any]:
    spec = load_schema_spec(schema_name)
    payload: dict[str, Any] = {"schema": spec.get("schema_value", schema_name)}
    for field, expected_type in spec.get("types", {}).items():
        if field in payload:
            continue
        payload[field] = _default_value(str(expected_type), field)
    for field in spec.get("required", []):
        payload.setdefault(field, "")
    for field, values in spec.get("enums", {}).items():
        if values and payload.get(field) not in values:
            payload[field] = values[0]
    payload.update(overrides)
    return payload


def _resolve_run_dir(root: Path, *, run_id: str = "", run_dir: Path | None = None) -> Path:
    if run_dir is not None:
        resolved = run_dir if run_dir.is_absolute() else root / run_dir
    elif run_id:
        resolved = root / "agents" / "runs" / run_id
    else:
        raise ValueError("run_id or run_dir is required")
    resolved = resolved.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"agent run directory not found: {resolved}")
    return resolved


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "str":
        return isinstance(value, str)
    if expected == "list":
        return isinstance(value, list)
    if expected == "dict":
        return isinstance(value, dict)
    if expected == "bool":
        return isinstance(value, bool)
    if expected == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    return True


def _default_value(expected: str, field: str) -> Any:
    if expected == "list":
        return []
    if expected == "dict":
        return {}
    if expected == "bool":
        return False
    if expected == "number":
        return 0
    if field.endswith("_id"):
        return "n/a"
    return ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel_str(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
