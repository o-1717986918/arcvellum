"""Previewable, backed-up, idempotent project schema migration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
import re
import shutil
from typing import Any

from literary_engineering_studio_engine.foundation.atomic_io import atomic_write_text
from literary_engineering_studio_engine.foundation.schema_aliases import (
    PROJECT_READING_SCHEMA,
    PROJECT_SCHEMA,
    SCHEMA_ALIASES,
)
from literary_engineering_studio_engine.tasking.spec import (
    TASK_SCHEMA_V1,
    TASK_SCHEMA_V2,
    parse_task_document,
    task_document_to_v2,
)


MIGRATION_SCHEMA = "arcvellum/project-schema-migration/v1"
MIGRATION_ACTIONS = frozenset({"preview", "backup", "apply"})
TEXT_SCHEMA_LINE = re.compile(
    r"^(?P<indent>\s*)(?P<key>schema|\"schema\")(?P<separator>\s*:\s*)"
    r"(?P<quote>[\"']?)(?P<value>[^\"'\s,}]+)(?P=quote)(?P<suffix>.*)$"
)


@dataclass(frozen=True)
class MigrationChange:
    path: str
    kind: str
    identities: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class MigrationResult:
    project_root: Path
    action: str
    changes: tuple[MigrationChange, ...]
    retained_legacy: tuple[tuple[str, str], ...]
    backup_root: Path | None
    applied: bool

    @property
    def changed(self) -> bool:
        return bool(self.changes)

    def to_record(self) -> dict[str, object]:
        return {
            "schema": MIGRATION_SCHEMA,
            "project_root": str(self.project_root),
            "action": self.action,
            "changed": self.changed,
            "change_count": len(self.changes),
            "changes": [asdict(item) for item in self.changes],
            "retained_legacy": [
                {"path": path, "schema": schema}
                for path, schema in self.retained_legacy
            ],
            "backup_root": str(self.backup_root) if self.backup_root else "",
            "applied": self.applied,
        }


@dataclass(frozen=True)
class _PlannedWrite:
    path: Path
    content: str
    change: MigrationChange


def migrate_project_schemas(
    project_root: Path,
    *,
    action: str = "preview",
    backup_root: Path | None = None,
) -> MigrationResult:
    """Plan, back up, or apply only registered and structurally safe migrations."""

    root = project_root.expanduser().resolve()
    normalized_action = action.strip().lower()
    if normalized_action not in MIGRATION_ACTIONS:
        raise ValueError(f"unsupported migration action: {action}")
    if not root.is_dir() or not (root / "project.yaml").is_file():
        raise FileNotFoundError(f"work project is missing project.yaml: {root}")

    writes, retained = _plan_writes(root)
    resolved_backup: Path | None = None
    if normalized_action in {"backup", "apply"} and writes:
        resolved_backup = _backup_files(root, writes, backup_root)
    if normalized_action == "apply":
        for item in writes:
            atomic_write_text(item.path, item.content)
        _write_migration_receipt(root, writes, resolved_backup)
    return MigrationResult(
        project_root=root,
        action=normalized_action,
        changes=tuple(item.change for item in writes),
        retained_legacy=tuple(retained),
        backup_root=resolved_backup,
        applied=normalized_action == "apply" and bool(writes),
    )


def _plan_writes(root: Path) -> tuple[list[_PlannedWrite], list[tuple[str, str]]]:
    writes: list[_PlannedWrite] = []
    retained: list[tuple[str, str]] = []
    for path in _project_files(root):
        relative = path.relative_to(root).as_posix()
        original = path.read_text(encoding="utf-8", errors="strict")
        if relative == "project.yaml":
            updated, identities, unknown = _project_descriptor(original)
            retained.extend((relative, item) for item in unknown)
            kind = "project-identity"
        elif relative.endswith(".task.json"):
            updated, identities = _task_document(original)
            kind = "task-v1-to-v2"
        elif path.suffix.lower() in {".json", ".jsonl"}:
            updated, identities, unknown = _json_document(original, jsonl=path.suffix.lower() == ".jsonl")
            retained.extend((relative, item) for item in unknown)
            kind = "registered-schema-alias"
        else:
            updated, identities, unknown = _text_document(original)
            retained.extend((relative, item) for item in unknown)
            kind = "registered-schema-alias"
        if updated != original:
            writes.append(
                _PlannedWrite(
                    path,
                    updated,
                    MigrationChange(relative, kind, tuple(identities)),
                )
            )
    return writes, sorted(set(retained))


def _project_files(root: Path) -> list[Path]:
    ignored = {".git", ".arcvellum", "node_modules", "releases", "exports"}
    supported = {".json", ".jsonl", ".yaml", ".yml", ".md"}
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in supported
        and not any(part in ignored for part in path.relative_to(root).parts)
    )


def _project_descriptor(text: str) -> tuple[str, list[tuple[str, str]], list[str]]:
    lines = text.splitlines()
    if lines and lines[0].startswith("schema:"):
        current = lines[0].split(":", 1)[1].strip().strip("\"'")
        if current == PROJECT_SCHEMA:
            return text, [], []
        target = SCHEMA_ALIASES.migration_target(current)
        if target:
            lines[0] = f"schema: {target}"
            return _with_original_newline(lines, text), [(current, target)], []
        unknown = [current] if current.startswith("literary-engineering-workbench/") else []
        return text, [], unknown
    lines.insert(0, f"schema: {PROJECT_SCHEMA}")
    return _with_original_newline(lines, text), [("<missing>", PROJECT_SCHEMA)], []


def _task_document(text: str) -> tuple[str, list[tuple[str, str]]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text, []
    if not isinstance(payload, dict) or payload.get("schema") != TASK_SCHEMA_V1:
        return text, []
    document = parse_task_document(payload, normalize_path=_normalize_relative)
    migrated = task_document_to_v2(document, canonicalize_aliases=True)
    return _json_text(migrated), [(TASK_SCHEMA_V1, TASK_SCHEMA_V2)]


def _json_document(
    text: str,
    *,
    jsonl: bool,
) -> tuple[str, list[tuple[str, str]], list[str]]:
    try:
        payload: Any
        if jsonl:
            payload = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            payload = json.loads(text)
    except json.JSONDecodeError:
        return text, [], []
    identities: list[tuple[str, str]] = []
    unknown: list[str] = []
    transformed = _transform_schema_values(payload, identities, unknown)
    if not identities:
        return text, [], unknown
    if jsonl:
        return "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in transformed), identities, unknown
    return _json_text(transformed), identities, unknown


def _transform_schema_values(
    value: Any,
    identities: list[tuple[str, str]],
    unknown: list[str],
    *,
    key: str = "",
) -> Any:
    if isinstance(value, dict):
        return {
            item_key: _transform_schema_values(item, identities, unknown, key=str(item_key))
            for item_key, item in value.items()
        }
    if isinstance(value, list):
        return [_transform_schema_values(item, identities, unknown, key=key) for item in value]
    if isinstance(value, str) and key in {"schema", "$id", "schema_value"}:
        target = SCHEMA_ALIASES.migration_target(value)
        if target:
            identities.append((value, target))
            return target
        if value.startswith("literary-engineering-workbench/"):
            unknown.append(value)
    return value


def _text_document(text: str) -> tuple[str, list[tuple[str, str]], list[str]]:
    identities: list[tuple[str, str]] = []
    unknown: list[str] = []
    lines: list[str] = []
    for line in text.splitlines():
        match = TEXT_SCHEMA_LINE.match(line)
        if not match:
            lines.append(line)
            continue
        current = match.group("value")
        target = SCHEMA_ALIASES.migration_target(current)
        if target:
            identities.append((current, target))
            line = (
                f"{match.group('indent')}{match.group('key')}{match.group('separator')}"
                f"{match.group('quote')}{target}{match.group('quote')}{match.group('suffix')}"
            )
        elif current.startswith("literary-engineering-workbench/"):
            unknown.append(current)
        lines.append(line)
    if not identities:
        return text, [], unknown
    return _with_original_newline(lines, text), identities, unknown


def _backup_files(root: Path, writes: list[_PlannedWrite], requested: Path | None) -> Path:
    if requested is not None:
        backup = requested.expanduser().resolve()
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = root / ".arcvellum" / "migrations" / f"schema-v2-{stamp}"
    if backup.exists() and any(backup.iterdir()):
        raise FileExistsError(f"migration backup directory is not empty: {backup}")
    for item in writes:
        relative = item.path.relative_to(root)
        target = backup / "files" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item.path, target)
    manifest = {
        "schema": MIGRATION_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(root),
        "files": [item.change.path for item in writes],
    }
    atomic_write_text(backup / "manifest.json", _json_text(manifest))
    return backup


def _write_migration_receipt(root: Path, writes: list[_PlannedWrite], backup: Path | None) -> None:
    receipt = root / ".arcvellum" / "migrations" / "latest-schema-migration.json"
    payload = {
        "schema": MIGRATION_SCHEMA,
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "backup_root": str(backup) if backup else "",
        "files": [item.change.path for item in writes],
    }
    atomic_write_text(receipt, _json_text(payload))


def _normalize_relative(value: str) -> PurePosixPath:
    text = str(value or "").strip().replace("\\", "/")
    path = PurePosixPath(text)
    if not text or path.is_absolute() or ".." in path.parts or ":" in path.parts[0]:
        raise ValueError(f"task path must be project-relative: {value}")
    return path


def _with_original_newline(lines: list[str], original: str) -> str:
    suffix = "\n" if original.endswith(("\n", "\r")) else ""
    return "\n".join(lines) + suffix


def _json_text(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


__all__ = [
    "MIGRATION_ACTIONS",
    "MIGRATION_SCHEMA",
    "MigrationChange",
    "MigrationResult",
    "migrate_project_schemas",
]
