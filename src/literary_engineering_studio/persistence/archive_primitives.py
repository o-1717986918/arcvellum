"""Shared validation primitives for the Archive persistence boundary."""

from __future__ import annotations


def archive_project_key(project_root: str) -> str:
    value = str(project_root or "").strip().replace("\\", "/").rstrip("/")
    if not value:
        raise ValueError("archive project root must not be empty")
    return value.casefold()


def validate_archive_asset_key(asset_id: str, revision: str = "") -> None:
    if not asset_id or ":" not in asset_id or len(asset_id) > 260:
        raise ValueError(f"invalid archive asset id: {asset_id}")
    if revision and (not revision.startswith("sha256:") or len(revision) != 71):
        raise ValueError(f"invalid archive revision: {revision}")


def archive_relative_path(value: object) -> str:
    path = str(value or "").strip().replace("\\", "/").lstrip("./")
    if not path or path.startswith("/") or ":" in path or ".." in path.split("/"):
        raise ValueError(f"invalid archive index path: {value}")
    return path
