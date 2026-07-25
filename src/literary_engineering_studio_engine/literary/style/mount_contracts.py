"""Contracts for immutable style-version activation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import re


STYLE_VERSION_MOUNT_SCHEMA = "arcvellum/style-profile-version-mount/v1"
STYLE_VERSION_MOUNT_RECEIPT_SCHEMA = "arcvellum/style-profile-version-mount-receipt/v1"
_STYLE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,128}$")
_VERSION_ID_RE = re.compile(r"^v1-[0-9a-f]{20}$")
_CONTENT_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


class StyleMountScope(str, Enum):
    PROJECT = "project"


class StyleMountPriority(str, Enum):
    HIGHEST = "highest"


class StyleVersionMountError(ValueError):
    code = "style_version_mount_invalid"


class StyleVersionMountConflictError(StyleVersionMountError):
    code = "style_version_mount_conflict"


@dataclass(frozen=True)
class StyleVersionMountResult:
    project_root: Path
    style_id: str
    version_id: str
    content_hash: str
    mount_dir: Path
    active_manifest_path: Path
    receipt_path: Path | None
    created: bool


@dataclass(frozen=True)
class StyleMountIntent:
    root: Path
    style_id: str
    version_id: str
    content_hash: str
    scope: str
    priority: str


def normalize_mount_intent(
    project_root: Path,
    *,
    style_id: str,
    version_id: str,
    content_hash: str,
    scope: StyleMountScope | str,
    priority: StyleMountPriority | str,
) -> StyleMountIntent:
    root = project_root.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")
    return StyleMountIntent(
        root,
        _stable(style_id, _STYLE_ID_RE, "style_id"),
        _stable(version_id, _VERSION_ID_RE, "version_id"),
        _stable(content_hash, _CONTENT_HASH_RE, "content_hash"),
        _enum_value(StyleMountScope, scope, "scope"),
        _enum_value(StyleMountPriority, priority, "priority"),
    )


def _stable(value: str, pattern: re.Pattern[str], field: str) -> str:
    stable = str(value or "").strip()
    if not pattern.fullmatch(stable):
        raise StyleVersionMountError(f"{field} must match {pattern.pattern}")
    return stable


def _enum_value(enum_type: type[Enum], value: Enum | str, field: str) -> str:
    try:
        return str(enum_type(value).value)
    except ValueError as exc:
        allowed = ", ".join(str(item.value) for item in enum_type)
        raise StyleVersionMountError(f"{field} must be one of: {allowed}") from exc
