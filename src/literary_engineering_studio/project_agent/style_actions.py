"""Project Agent style actions over version mounts and author-owned directions."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .action_receipts import action_receipt


def style_mount_action(style_mounts: Any, invalidate_project: Any | None):
    def mount(root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        identity = {
            field: str(arguments.get(field) or "").strip()
            for field in ("style_id", "version_id", "content_hash")
        }
        if not all(identity.values()):
            raise ValueError("project_style_mount requires exact style_id, version_id, and content_hash")
        preview = style_mounts.preview(root, **identity)
        result = style_mounts.mount_confirmed(
            root, **identity, preview_revision=str(preview.get("revision") or ""),
            scope=str(arguments.get("scope") or "project"),
            priority=str(arguments.get("priority") or "highest"),
        )
        if invalidate_project is not None:
            invalidate_project(root, "project-agent-style")
        return {
            "ok": True, "operation": "mount_style",
            "style_id": identity["style_id"], "version_id": identity["version_id"],
            "status": result.get("status"), "impact": result.get("impact") or {},
            "receipt": action_receipt("mount_style", result),
        }

    return mount


def owner_style_write_action(
    write_owner_style: Callable[..., dict[str, Any]], invalidate_project: Any | None,
):
    def write(root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        content = arguments.get("content")
        if not isinstance(content, str):
            raise ValueError("project_owner_style_write requires content text")
        result = write_owner_style(
            root, content=content,
            base_revision=str(arguments.get("base_revision") or ""),
            reason=str(arguments.get("reason") or ""),
        )
        if invalidate_project is not None:
            invalidate_project(root, "project-agent-owner-style")
        return {"ok": True, "operation": "owner_style_write", **result}

    return write


__all__ = ["owner_style_write_action", "style_mount_action"]
