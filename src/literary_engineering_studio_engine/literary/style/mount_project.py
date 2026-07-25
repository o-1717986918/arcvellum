"""Project materialization and metadata rendering for style mounts."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Any
from uuid import uuid4

from .mount_contracts import (
    STYLE_VERSION_MOUNT_RECEIPT_SCHEMA,
    STYLE_VERSION_MOUNT_SCHEMA,
    StyleVersionMountConflictError,
    StyleVersionMountError,
)
from .mount_inspection import (
    inside,
    object_value,
    read_json_object,
    relative,
)
from .version_inspection import inspect_style_version_directory


def materialize_mount(
    source: Path,
    target: Path,
    expected: dict[str, Any],
    *,
    project_root: Path,
) -> bool:
    if target.exists():
        if not target.is_dir() or not inside(project_root, target):
            raise StyleVersionMountConflictError("mounted version target is unsafe")
        manifest, errors = inspect_style_version_directory(target)
        if errors or not _same_version_manifest(manifest, expected):
            raise StyleVersionMountConflictError(
                "existing mounted version conflicts with the immutable source"
            )
        return False

    target.parent.mkdir(parents=True, exist_ok=True)
    staging_root = target.parent / f".{target.name}.mount-{uuid4().hex}"
    staged = staging_root / target.name
    try:
        shutil.copytree(source, staged)
        manifest, errors = inspect_style_version_directory(staged)
        if errors or not _same_version_manifest(manifest, expected):
            raise StyleVersionMountConflictError(
                "staged style version failed integrity verification"
            )
        staged.replace(target)
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)
    return True


def build_mount_metadata(
    root: Path,
    *,
    source: Path,
    mount_dir: Path,
    version: dict[str, Any],
    scope: str,
    priority: str,
    mounted_at: str,
    receipt_path: Path,
    previous: dict[str, Any],
) -> tuple[dict[str, object], dict[str, object]]:
    readiness = object_value(
        read_json_object(mount_dir / "style_skill.json").get("readiness")
    )
    manifest = {
        "schema": STYLE_VERSION_MOUNT_SCHEMA,
        "style_id": str(version.get("style_id") or ""),
        "version_id": str(version.get("version_id") or ""),
        "content_hash": str(version.get("content_hash") or ""),
        "author_id": str(version.get("author_id") or ""),
        "profile_id": str(version.get("profile_id") or ""),
        "scope": scope,
        "priority": priority,
        "priority_weight": 1000,
        "mount_path": relative(mount_dir, root),
        "prompt": relative(mount_dir / "prompt.md", root),
        "style_skill": relative(mount_dir / "style_skill.json", root),
        "style_version": relative(mount_dir / "style_version.json", root),
        "project_style": "style/active_style_skill.json",
        "mount_source": relative(source, root),
        "mounted_at": mounted_at,
        "allow_unreviewed": False,
        "review_status": str(version.get("review_status") or ""),
        "readiness": readiness,
        "integrity": {"status": "pass", "issues": []},
        "enforcement": {
            "director": "required",
            "composition": "required",
            "generation": "required",
            "revision": "required",
            "review": "required",
        },
        "receipt": relative(receipt_path, root),
        "previous": mount_identity(previous),
    }
    receipt = {
        "schema": STYLE_VERSION_MOUNT_RECEIPT_SCHEMA,
        "status": "committed",
        "mounted_at": manifest["mounted_at"],
        "current": mount_identity(manifest),
        "previous": mount_identity(previous),
        "scope": manifest["scope"],
        "priority": manifest["priority"],
        "mount_path": manifest["mount_path"],
        "active_manifest": "style/active_style_skill.json",
    }
    return manifest, receipt


def activation_writes(
    root: Path,
    active_path: Path,
    receipt_path: Path,
    manifest: dict[str, object],
    receipt: dict[str, object],
) -> dict[Path, str]:
    writes = {
        active_path: json_text(manifest),
        receipt_path: json_text(receipt),
    }
    project_yaml = root / "project.yaml"
    if project_yaml.is_file():
        writes[project_yaml] = render_project_yaml_style_mount(
            project_yaml.read_text(encoding="utf-8"),
            manifest,
        )
    return writes


def render_project_yaml_style_mount(
    text: str,
    manifest: dict[str, object],
) -> str:
    replacement = "\n".join(
        [
            "style:",
            "  mode: rights-declared-formal-session",
            f"  active_style_skill: {_yaml_scalar(manifest.get('style_id'))}",
            f"  active_style_version: {_yaml_scalar(manifest.get('version_id'))}",
            f"  content_hash: {_yaml_scalar(manifest.get('content_hash'))}",
            f"  scope: {_yaml_scalar(manifest.get('scope'))}",
            f"  priority: {_yaml_scalar(manifest.get('priority'))}",
            f"  priority_weight: {int(manifest.get('priority_weight') or 1000)}",
            f"  mount_path: {_yaml_scalar(manifest.get('mount_path'))}",
            "  target_profiles:",
            f"    - {_yaml_scalar(manifest.get('style_id'))}",
            "  blend_strategy: single-style-version",
        ]
    )
    return _replace_style_block(text, replacement)


def mount_identity(payload: dict[str, Any]) -> dict[str, str]:
    return {
        field: str(payload.get(field) or "")
        for field in ("style_id", "version_id", "content_hash")
    }


def require_inside(root: Path, path: Path) -> None:
    if not inside(root, path):
        raise StyleVersionMountError("style mount path escapes the project")


def json_text(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _replace_style_block(text: str, replacement: str) -> str:
    lines = text.splitlines()
    output: list[str] = []
    index = 0
    replaced = False
    while index < len(lines):
        line = lines[index]
        if line.startswith("style:"):
            output.append(replacement)
            replaced = True
            index += 1
            while index < len(lines) and (
                lines[index].startswith(" ") or not lines[index].strip()
            ):
                index += 1
            continue
        output.append(line)
        index += 1
    if not replaced:
        output.extend(["", replacement])
    return "\n".join(output).rstrip() + "\n"


def _same_version_manifest(
    left: dict[str, Any],
    right: dict[str, Any],
) -> bool:
    return all(
        str(left.get(field) or "") == str(right.get(field) or "")
        for field in ("style_id", "version_id", "content_hash")
    )


def _yaml_scalar(value: object) -> str:
    return json.dumps(str(value or ""), ensure_ascii=False)
