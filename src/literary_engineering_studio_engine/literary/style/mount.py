"""Use-case orchestration for version-bound project style mounts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil
from uuid import uuid4

from ...atomic_io import atomic_write_batch
from .mount_contracts import (
    STYLE_VERSION_MOUNT_RECEIPT_SCHEMA,
    STYLE_VERSION_MOUNT_SCHEMA,
    StyleMountPriority,
    StyleMountScope,
    StyleVersionMountConflictError,
    StyleVersionMountError,
    StyleVersionMountResult,
    normalize_mount_intent,
)
from .mount_inspection import (
    inspect_active_style_mount,
    manifest_mount_dir,
    resolve_style_profile_version,
    same_active_mount,
)
from .mount_project import (
    activation_writes,
    build_mount_metadata,
    materialize_mount,
    render_project_yaml_style_mount,
    require_inside,
)


def mount_style_profile_version(
    project_root: Path,
    *,
    style_id: str,
    version_id: str,
    content_hash: str,
    scope: StyleMountScope | str = StyleMountScope.PROJECT,
    priority: StyleMountPriority | str = StyleMountPriority.HIGHEST,
) -> StyleVersionMountResult:
    """Mount one exact immutable version without accepting a caller path."""

    intent = normalize_mount_intent(
        project_root,
        style_id=style_id,
        version_id=version_id,
        content_hash=content_hash,
        scope=scope,
        priority=priority,
    )
    source, version = resolve_style_profile_version(
        intent.root,
        style_id=intent.style_id,
        version_id=intent.version_id,
        content_hash=intent.content_hash,
    )
    active_path = intent.root / "style" / "active_style_skill.json"
    current = inspect_active_style_mount(intent.root)
    if same_active_mount(
        current,
        style_id=intent.style_id,
        version_id=intent.version_id,
        content_hash=intent.content_hash,
    ):
        return _existing_result(intent, active_path, current)
    return _activate_version(intent, source, version, active_path, current)


def _existing_result(intent, active_path, current) -> StyleVersionMountResult:
    return StyleVersionMountResult(
        intent.root,
        intent.style_id,
        intent.version_id,
        intent.content_hash,
        manifest_mount_dir(intent.root, current),
        active_path,
        None,
        False,
    )


def _activate_version(
    intent,
    source: Path,
    version: dict[str, object],
    active_path: Path,
    current: dict[str, object],
) -> StyleVersionMountResult:
    mount_dir = (
        intent.root
        / "style"
        / "mounted"
        / intent.style_id
        / intent.version_id
    )
    require_inside(intent.root, mount_dir)
    copied = materialize_mount(
        source,
        mount_dir,
        version,
        project_root=intent.root,
    )
    mounted_at = datetime.now(timezone.utc).isoformat()
    receipt_path = _new_receipt_path(intent.root, mounted_at)
    manifest, receipt = build_mount_metadata(
        intent.root,
        source=source,
        mount_dir=mount_dir,
        version=version,
        scope=intent.scope,
        priority=intent.priority,
        mounted_at=mounted_at,
        receipt_path=receipt_path,
        previous=current,
    )
    try:
        atomic_write_batch(
            activation_writes(
                intent.root,
                active_path,
                receipt_path,
                manifest,
                receipt,
            )
        )
    except Exception:
        if copied:
            shutil.rmtree(mount_dir, ignore_errors=True)
        raise
    return StyleVersionMountResult(
        intent.root,
        intent.style_id,
        intent.version_id,
        intent.content_hash,
        mount_dir,
        active_path,
        receipt_path,
        True,
    )


def _new_receipt_path(root: Path, mounted_at: str) -> Path:
    stamp = mounted_at.replace(":", "").replace("+", "-")
    return (
        root
        / "style"
        / "mount_receipts"
        / f"{stamp}-{uuid4().hex[:10]}.json"
    )


__all__ = [
    "STYLE_VERSION_MOUNT_RECEIPT_SCHEMA",
    "STYLE_VERSION_MOUNT_SCHEMA",
    "StyleMountPriority",
    "StyleMountScope",
    "StyleVersionMountConflictError",
    "StyleVersionMountError",
    "StyleVersionMountResult",
    "inspect_active_style_mount",
    "mount_style_profile_version",
    "render_project_yaml_style_mount",
]
