"""Resolution and integrity inspection for version-bound style mounts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .mount_contracts import StyleVersionMountConflictError
from .session import formal_style_profile_dirs
from .version_inspection import inspect_style_version_directory


def resolve_style_profile_version(
    root: Path,
    *,
    style_id: str,
    version_id: str,
    content_hash: str,
) -> tuple[Path, dict[str, Any]]:
    matches: list[tuple[Path, dict[str, Any]]] = []
    conflicts: list[str] = []
    for profile in formal_style_profile_dirs(root):
        candidate = profile / "versions" / version_id
        if not candidate.is_dir() or not inside(root, candidate):
            continue
        manifest, errors = inspect_style_version_directory(candidate)
        if str(manifest.get("style_id") or "") != style_id:
            continue
        if errors:
            conflicts.extend(errors)
            continue
        if str(manifest.get("content_hash") or "") != content_hash:
            raise StyleVersionMountConflictError(
                "requested content hash does not match the immutable style version"
            )
        matches.append((candidate, manifest))
    if conflicts:
        raise StyleVersionMountConflictError(
            "immutable style version failed integrity checks: "
            + "; ".join(dict.fromkeys(conflicts))
        )
    if not matches:
        raise FileNotFoundError(
            f"style profile version not found: {style_id}/{version_id}"
        )
    if len(matches) != 1:
        raise StyleVersionMountConflictError(
            "multiple immutable style versions share the requested identity"
        )
    return matches[0]


def inspect_active_style_mount(project_root: Path) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    payload = read_json_object(root / "style" / "active_style_skill.json")
    if not payload:
        return {}
    result = dict(payload)
    result.update(_prompt_projection(root, payload))
    if not payload.get("version_id") or not payload.get("content_hash"):
        result["integrity"] = {
            "status": "legacy-unverified",
            "issues": ["legacy mount is not bound to an immutable style version"],
        }
        return result
    errors = _active_version_errors(root, payload)
    result["integrity"] = {
        "status": "pass" if not errors else "conflict",
        "issues": list(dict.fromkeys(errors)),
    }
    if errors:
        result["prompt_exists"] = False
        result["prompt_path"] = ""
    return result


def same_active_mount(
    payload: dict[str, Any],
    *,
    style_id: str,
    version_id: str,
    content_hash: str,
) -> bool:
    integrity = object_value(payload.get("integrity"))
    return (
        integrity.get("status") == "pass"
        and str(payload.get("style_id") or "") == style_id
        and str(payload.get("version_id") or "") == version_id
        and str(payload.get("content_hash") or "") == content_hash
    )


def manifest_mount_dir(root: Path, payload: dict[str, Any]) -> Path:
    path = safe_project_path(root, str(payload.get("mount_path") or ""))
    if path is None:
        raise StyleVersionMountConflictError("active style mount path is invalid")
    return path


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def object_value(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_project_path(root: Path, relative: str) -> Path | None:
    if not relative or Path(relative).is_absolute():
        return None
    candidate = (root / relative).resolve()
    return candidate if candidate.is_relative_to(root) else None


def inside(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _prompt_projection(
    root: Path,
    payload: dict[str, Any],
) -> dict[str, object]:
    prompt = safe_project_path(root, str(payload.get("prompt") or ""))
    exists = bool(prompt and prompt.is_file())
    return {
        "prompt_exists": exists,
        "prompt_path": relative(prompt, root) if exists and prompt else "",
    }


def _active_version_errors(
    root: Path,
    payload: dict[str, Any],
) -> list[str]:
    mount_dir = safe_project_path(root, str(payload.get("mount_path") or ""))
    if mount_dir is None or not mount_dir.is_dir():
        return ["mounted style version directory is missing"]
    manifest, package_errors = inspect_style_version_directory(mount_dir)
    errors = list(package_errors)
    errors.extend(
        f"active style mount {field} does not match mounted package"
        for field in ("style_id", "version_id", "content_hash")
        if str(payload.get(field) or "") != str(manifest.get(field) or "")
    )
    return errors
