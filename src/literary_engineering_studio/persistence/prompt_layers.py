"""Versioned file adapter for global and work-project prompt layers."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import threading
from typing import Any


_SAFE_ID = re.compile(r"^[a-z][a-z0-9._-]{1,100}$")


class FilePromptLayerRepository:
    def __init__(self, data_root: Path):
        self._data_root = data_root.resolve()
        self._lock = threading.RLock()

    def active(self, scope: str, project_root: Path | None, layer_id: str) -> dict[str, Any] | None:
        record = self._read(self._path(scope, project_root, layer_id))
        return next((item for item in record["versions"] if item["version"] == record["active"]), None)

    def history(self, scope: str, project_root: Path | None, layer_id: str) -> list[dict[str, Any]]:
        return list(self._read(self._path(scope, project_root, layer_id))["versions"])

    def save(self, scope: str, project_root: Path | None, layer_id: str, text: str) -> dict[str, Any]:
        with self._lock:
            path = self._path(scope, project_root, layer_id)
            record = self._read(path)
            version = max((int(item["version"]) for item in record["versions"]), default=0) + 1
            entry = {"version": version, "text": text, "created_at": datetime.now(timezone.utc).isoformat()}
            record["versions"].append(entry)
            record["active"] = version
            self._write(path, record)
            return entry

    def activate(self, scope: str, project_root: Path | None, layer_id: str, version: int) -> dict[str, Any]:
        with self._lock:
            path = self._path(scope, project_root, layer_id)
            record = self._read(path)
            entry = next((item for item in record["versions"] if item["version"] == version), None)
            if entry is None:
                raise ValueError("prompt version does not exist")
            record["active"] = version
            self._write(path, record)
            return entry

    def reset(self, scope: str, project_root: Path | None, layer_id: str) -> None:
        with self._lock:
            path = self._path(scope, project_root, layer_id)
            record = self._read(path)
            record["active"] = 0
            self._write(path, record)

    def _path(self, scope: str, project_root: Path | None, layer_id: str) -> Path:
        if not _SAFE_ID.fullmatch(layer_id):
            raise ValueError("invalid prompt layer id")
        if scope == "global":
            base = self._data_root / "prompt-layers" / "global"
        elif scope == "project" and project_root is not None:
            root = project_root.resolve()
            if not root.is_dir() or not (root / "project.yaml").is_file():
                raise ValueError("prompt project scope needs a work project")
            base = root / ".arcvellum" / "prompt-layers"
        else:
            raise ValueError("invalid prompt scope")
        return base / f"{layer_id}.json"

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {"schema": "arcvellum/prompt-layer-history/v1", "active": 0, "versions": []}
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("prompt layer history is unreadable") from exc
        if (not isinstance(record, dict) or record.get("schema") != "arcvellum/prompt-layer-history/v1"
                or not isinstance(record.get("versions"), list)):
            raise ValueError("prompt layer history is invalid")
        _validate_history(record)
        return record

    @staticmethod
    def _write(path: Path, record: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)


def _validate_history(record: dict[str, Any]) -> None:
    versions = record["versions"]
    seen: set[int] = set()
    for entry in versions:
        if not _valid_history_entry(entry, seen):
            raise ValueError("prompt layer history has an invalid version")
        seen.add(entry["version"])
    active = record.get("active")
    if type(active) is not int or active not in seen | {0}:
        raise ValueError("prompt layer history has an invalid active version")


def _valid_history_entry(entry: Any, seen: set[int]) -> bool:
    return (isinstance(entry, dict) and type(entry.get("version")) is int
            and entry["version"] >= 1 and entry["version"] not in seen
            and isinstance(entry.get("text"), str) and bool(entry["text"].strip())
            and len(entry["text"]) <= 12_000 and isinstance(entry.get("created_at"), str))
