"""Controlled Studio use cases for Engine-owned style version mounts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from literary_engineering_studio_engine.literary.style.mount import (
    StyleMountPriority,
    StyleMountScope,
    inspect_active_style_mount,
    mount_style_profile_version,
)


class StyleMountChoiceError(ValueError):
    code = "style_mount_choice_invalid"


class StyleMountApplicationService:
    def status(self, project_root: Path) -> dict[str, object]:
        active = inspect_active_style_mount(project_root)
        integrity = _object(active.get("integrity"))
        return {
            "schema": "arcvellum/style-mount-status/v1",
            "ok": True,
            "status": (
                "unmounted"
                if not active
                else "active"
                if integrity.get("status") == "pass"
                else "legacy"
                if integrity.get("status") == "legacy-unverified"
                else "conflict"
            ),
            "active_mount": _safe_active_mount(active),
        }

    def mount(
        self,
        project_root: Path,
        *,
        style_id: str,
        version_id: str,
        content_hash: str,
        scope: str = StyleMountScope.PROJECT.value,
        priority: str = StyleMountPriority.HIGHEST.value,
    ) -> dict[str, object]:
        root = project_root.expanduser().resolve()
        result = mount_style_profile_version(
            root,
            style_id=style_id,
            version_id=version_id,
            content_hash=content_hash,
            scope=scope,
            priority=priority,
        )
        status = self.status(root)
        return {
            "schema": "arcvellum/style-mount-transaction/v1",
            "ok": True,
            "status": "mounted" if result.created else "already-mounted",
            "created": result.created,
            "style_id": result.style_id,
            "version_id": result.version_id,
            "content_hash": result.content_hash,
            "scope": scope,
            "priority": priority,
            "mount_dir": _relative(result.mount_dir, root),
            "active_manifest": _relative(result.active_manifest_path, root),
            "receipt": (
                _relative(result.receipt_path, root)
                if result.receipt_path is not None
                else ""
            ),
            "active_mount": status["active_mount"],
        }

    def mount_choice(
        self,
        project_root: Path,
        choice: dict[str, Any],
    ) -> dict[str, object]:
        selected = str(choice.get("selected") or "").strip()
        options = (
            choice.get("options")
            if isinstance(choice.get("options"), list)
            else []
        )
        option = next(
            (
                item
                for item in options
                if isinstance(item, dict)
                and str(item.get("id") or "") == selected
            ),
            None,
        )
        if not isinstance(option, dict):
            raise StyleMountChoiceError(
                "selected style version is not one of the declared choices"
            )
        identity = {
            field: str(option.get(field) or "").strip()
            for field in ("style_id", "version_id", "content_hash")
        }
        if not all(identity.values()):
            raise StyleMountChoiceError(
                "style mount choice lacks an exact immutable version identity"
            )
        return self.mount(
            project_root,
            style_id=identity["style_id"],
            version_id=identity["version_id"],
            content_hash=identity["content_hash"],
        )


def _safe_active_mount(payload: dict[str, Any]) -> dict[str, object]:
    allowed = (
        "schema",
        "style_id",
        "version_id",
        "content_hash",
        "author_id",
        "profile_id",
        "scope",
        "priority",
        "mounted_at",
        "review_status",
        "readiness",
        "integrity",
        "enforcement",
    )
    return {key: payload[key] for key in allowed if key in payload}


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _object(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
