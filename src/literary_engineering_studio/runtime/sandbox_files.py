"""Filesystem primitives for isolated task workspaces."""

from __future__ import annotations

from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Iterable

from .sandbox_contracts import SandboxManifest


def control_workspace(sandbox: SandboxManifest) -> Path:
    return sandbox.control_workspace or sandbox.workspace


def agent_workspace(sandbox: SandboxManifest) -> Path:
    return sandbox.agent_workspace or sandbox.workspace


def workspace_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        hashes[path.relative_to(root).as_posix()] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    return hashes


def path_digest(path: Path) -> str:
    if not path.exists():
        return ""
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    hashes = workspace_hashes(path)
    return hashlib.sha256(
        json.dumps(hashes, sort_keys=True).encode("utf-8")
    ).hexdigest()


def path_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def readable_diff(before: Path, after: Path, relative: str) -> str:
    if not after.is_file() or (before.exists() and not before.is_file()):
        return "目录内容发生变化；请查看文件清单。"
    if after.suffix.lower() not in {
        ".md", ".txt", ".json", ".yaml", ".yml", ".csv", ".py"
    }:
        return "二进制或不可读文本文件；请核对文件大小与摘要。"
    before_lines = (
        before.read_text(encoding="utf-8", errors="replace").splitlines()
        if before.is_file()
        else []
    )
    after_lines = after.read_text(
        encoding="utf-8", errors="replace"
    ).splitlines()
    diff = list(
        difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile="正式项目/" + relative,
            tofile="候选写回/" + relative,
            lineterm="",
            n=3,
        )
    )
    if len(diff) > 180:
        diff = diff[:180] + ["... 差异过长，已在预览中截断 ..."]
    return "\n".join(diff)


def copy_path(source: Path, destination: Path) -> None:
    if source.is_symlink():
        raise ValueError(f"symbolic links are not allowed in task sandboxes: {source}")
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def copy_path_atomically(source: Path, target: Path) -> None:
    """Replace one output atomically and leave transaction rollback to caller."""
    target.parent.mkdir(parents=True, exist_ok=True)
    staged = target.with_name(
        f".{target.name}.arcvellum-write-{os.getpid()}-"
        f"{datetime.now(timezone.utc).strftime('%f')}"
    )
    remove_path(staged)
    try:
        copy_path(source, staged)
        remove_path(target)
        os.replace(staged, target)
    finally:
        remove_path(staged)


def remove_path(path: Path) -> None:
    if path.exists() and path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def unique_paths(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value).replace("\\", "/")
        if normalized not in seen:
            result.append(normalized)
            seen.add(normalized)
    return result


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "agent_workspace",
    "control_workspace",
    "copy_path",
    "copy_path_atomically",
    "path_digest",
    "path_size",
    "readable_diff",
    "remove_path",
    "unique_paths",
    "utc_now",
    "workspace_hashes",
]
