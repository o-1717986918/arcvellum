"""Controlled Studio use cases for Engine-owned style version mounts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from literary_engineering_studio_engine.literary.style.mount import (
    StyleMountPriority,
    StyleMountScope,
    inspect_active_style_mount,
    mount_style_profile_version,
)
from literary_engineering_studio_engine.literary.style.snapshot import (
    active_style_mount_snapshot_payload,
    style_version_mount_snapshot,
)

from .comparison_projection import project_style_version_comparison
from .impact_projection import project_style_mount_impact
from .version_service import StyleVersionProjectionService


class StyleMountChoiceError(ValueError):
    code = "style_mount_choice_invalid"


class StyleMountPreviewError(RuntimeError):
    code = "style_mount_preview_stale"


class StyleMountApplicationService:
    def __init__(
        self,
        versions: StyleVersionProjectionService | None = None,
    ) -> None:
        self.versions = versions or StyleVersionProjectionService()

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

    def preview(
        self,
        project_root: Path,
        *,
        style_id: str,
        version_id: str,
        content_hash: str,
    ) -> dict[str, object]:
        root = project_root.expanduser().resolve()
        target_snapshot = style_version_mount_snapshot(
            root,
            style_id=style_id,
            version_id=version_id,
            content_hash=content_hash,
        ).as_dict()
        current_snapshot = active_style_mount_snapshot_payload(root)
        target_detail = self.versions.version_detail(
            root,
            style_id=style_id,
            version_id=version_id,
        )
        current_detail = self._active_version_detail(root, current_snapshot)
        impact = project_style_mount_impact(
            root,
            current_snapshot=current_snapshot,
            target_snapshot=target_snapshot,
        )
        payload: dict[str, object] = {
            "schema": "arcvellum/style-mount-preview/v1",
            "status": (
                "already-mounted"
                if _same_identity(current_snapshot, target_snapshot)
                else "confirmation-required"
            ),
            "current": _safe_snapshot(current_snapshot),
            "target": _safe_snapshot(target_snapshot),
            "comparison": project_style_version_comparison(
                current_detail,
                target_detail,
            ),
            "impact": impact,
            "requires_confirmation": not _same_identity(
                current_snapshot,
                target_snapshot,
            ),
        }
        payload["revision"] = _payload_hash(payload)
        return payload

    def mount_confirmed(
        self,
        project_root: Path,
        *,
        style_id: str,
        version_id: str,
        content_hash: str,
        preview_revision: str,
        scope: str = StyleMountScope.PROJECT.value,
        priority: str = StyleMountPriority.HIGHEST.value,
    ) -> dict[str, object]:
        preview = self.preview(
            project_root,
            style_id=style_id,
            version_id=version_id,
            content_hash=content_hash,
        )
        required_revision = str(preview.get("revision") or "")
        if preview.get("requires_confirmation") and (
            not preview_revision or preview_revision != required_revision
        ):
            raise StyleMountPreviewError(
                "style mount preview is missing or stale; review the current impact before mounting"
            )
        result = self.mount(
            project_root,
            style_id=style_id,
            version_id=version_id,
            content_hash=content_hash,
            scope=scope,
            priority=priority,
        )
        return {
            **result,
            "preview_revision": required_revision,
            "impact": preview["impact"],
            "comparison": preview["comparison"],
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

    def _active_version_detail(
        self,
        root: Path,
        snapshot: dict[str, str],
    ) -> dict[str, object]:
        if not snapshot:
            return {}
        try:
            return self.versions.version_detail(
                root,
                style_id=str(snapshot.get("style_id") or ""),
                version_id=str(snapshot.get("version_id") or ""),
            )
        except FileNotFoundError:
            return {}


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


def _safe_snapshot(payload: dict[str, object]) -> dict[str, str]:
    return {
        field: str(payload.get(field) or "")
        for field in (
            "style_id",
            "version_id",
            "content_hash",
            "prompt_sha256",
            "digest",
        )
        if payload.get(field)
    }


def _same_identity(
    left: dict[str, object],
    right: dict[str, object],
) -> bool:
    return bool(left) and all(
        str(left.get(field) or "") == str(right.get(field) or "")
        for field in ("style_id", "version_id", "content_hash")
    )


def _payload_hash(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
