"""Run-local snapshots for outputs protected during a repair turn."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
from typing import Any, Mapping


def prepare_output_protection(
    run_root: Path,
    workspace: Path,
    attempt: int,
    protected: tuple[str, ...],
) -> tuple[Path, Path, dict[str, object]]:
    """Create one repair-attempt directory and snapshot protected outputs."""

    attempt_root = run_root / "repairs" / f"attempt-{max(1, int(attempt)):02d}"
    snapshot_root = attempt_root / "protected"
    return attempt_root, snapshot_root, snapshot_outputs(
        workspace,
        snapshot_root,
        protected,
    )


def snapshot_outputs(
    workspace: Path,
    snapshot_root: Path,
    protected: tuple[str, ...],
) -> dict[str, object]:
    snapshot: dict[str, object] = {}
    for relative in protected:
        source = workspace / Path(relative)
        exists = source.exists()
        snapshot[relative] = {
            "exists": exists,
            "sha256": path_sha256(source) if exists else "",
        }
        if exists:
            _copy_path(source, snapshot_root / Path(relative))
    return snapshot


def restore_outputs(
    workspace: Path,
    snapshot_root: Path,
    snapshot_value: object,
) -> tuple[str, ...]:
    restored: list[str] = []
    for relative, value in _mapping(snapshot_value).items():
        identity = _mapping(value)
        target = workspace / Path(relative)
        existed = identity.get("exists") is True
        before = str(identity.get("sha256") or "")
        current = path_sha256(target) if target.exists() else ""
        if existed and current != before:
            _remove_path(target)
            _copy_path(snapshot_root / Path(relative), target)
            restored.append(relative)
        elif not existed and target.exists():
            _remove_path(target)
            restored.append(relative)
    return tuple(restored)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def path_sha256(path: Path) -> str:
    if not path.exists():
        return ""
    if path.is_file():
        return file_sha256(path)
    identities = {
        item.relative_to(path).as_posix(): file_sha256(item)
        for item in sorted(
            candidate
            for candidate in path.rglob("*")
            if candidate.is_file()
        )
    }
    return hashlib.sha256(
        json.dumps(
            identities,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _copy_path(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True)
    else:
        shutil.copy2(source, target)


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


__all__ = [
    "file_sha256",
    "path_sha256",
    "prepare_output_protection",
    "restore_outputs",
    "snapshot_outputs",
]
