"""Version-aware persistence boundary for formal task packages."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath

from .spec import (
    TASK_SCHEMA_V1,
    TASK_SCHEMA_V2,
    parse_task_document,
    task_document_to_v2,
)


@dataclass(frozen=True)
class TaskStorageRecord:
    storage_schema: str
    raw_payload: dict[str, object]
    compatibility_payload: dict[str, object]


def load_task_record(path: Path) -> TaskStorageRecord:
    if not path.exists():
        raise FileNotFoundError(f"task not found: {path}")
    raw = _read_object(path)
    schema = str(raw.get("schema") or "")
    if schema in {"", TASK_SCHEMA_V1}:
        # Historical v1 files were deliberately permissive.  Preserve that
        # reader contract; strict validation starts at the v2 write boundary.
        compatibility = dict(raw)
    elif schema == TASK_SCHEMA_V2:
        document = parse_task_document(raw, normalize_path=_normalize_relative)
        compatibility = document.to_v1_payload()
    else:
        raise ValueError(f"not an agent task registry file: {path}")
    return TaskStorageRecord(
        storage_schema=schema,
        raw_payload=raw,
        compatibility_payload=compatibility,
    )


def load_task_payload(path: Path) -> dict[str, object]:
    """Return the stable flat compatibility view for either protocol version."""

    return load_task_record(path).compatibility_payload


def write_task_payload(
    path: Path,
    payload: dict[str, object],
    *,
    storage_schema: str | None = None,
) -> None:
    """Persist a task, preserving existing v1 files unless v2 is requested."""

    schema = storage_schema or _existing_schema(path) or TASK_SCHEMA_V2
    if schema == TASK_SCHEMA_V1:
        serialized = dict(payload)
        serialized["schema"] = TASK_SCHEMA_V1
    elif schema == TASK_SCHEMA_V2:
        compatible = dict(payload)
        compatible["schema"] = TASK_SCHEMA_V1
        document = parse_task_document(
            compatible,
            normalize_path=_normalize_relative,
        )
        serialized = task_document_to_v2(document, canonicalize_aliases=True)
    else:
        raise ValueError(f"unsupported task storage schema: {schema}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(serialized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def task_storage_schema(path: Path) -> str:
    return _existing_schema(path) or ""


def _existing_schema(path: Path) -> str:
    if not path.is_file():
        return ""
    return str(_read_object(path).get("schema") or "")


def _read_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"task JSON must be an object: {path}")
    return payload


def _normalize_relative(value: str) -> PurePosixPath:
    text = str(value or "").strip().replace("\\", "/")
    path = PurePosixPath(text)
    if not text or path.is_absolute() or ".." in path.parts or ":" in path.parts[0]:
        raise ValueError(f"task path must be project-relative: {value}")
    return path


__all__ = [
    "load_task_payload",
    "load_task_record",
    "TaskStorageRecord",
    "task_storage_schema",
    "write_task_payload",
]
