"""Machine-owned snapshots for the active immutable style mount."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from .mount_contracts import (
    STYLE_VERSION_MOUNT_SCHEMA,
    StyleVersionMountConflictError,
)
from .mount_inspection import (
    inspect_active_style_mount,
    object_value,
    safe_project_path,
)


STYLE_MOUNT_SNAPSHOT_SCHEMA = "arcvellum/style-mount-snapshot/v1"
_IDENTITY_FIELDS = (
    "style_id",
    "version_id",
    "content_hash",
    "prompt_sha256",
)


@dataclass(frozen=True)
class StyleMountSnapshot:
    style_id: str
    version_id: str
    content_hash: str
    prompt_sha256: str
    digest: str
    prompt_path: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "schema": STYLE_MOUNT_SNAPSHOT_SCHEMA,
            "style_id": self.style_id,
            "version_id": self.version_id,
            "content_hash": self.content_hash,
            "prompt_sha256": self.prompt_sha256,
            "digest": self.digest,
        }


@dataclass(frozen=True)
class StyleMountSnapshotValidation:
    status: str
    message: str
    current: dict[str, str]

    @property
    def passed(self) -> bool:
        return self.status in {"pass", "not_required", "legacy_unverified"}


def active_style_mount_snapshot(project_root: Path) -> StyleMountSnapshot | None:
    """Return the exact active version snapshot, failing closed on conflicts."""

    root = project_root.expanduser().resolve()
    active = inspect_active_style_mount(root)
    if not active or not _is_versioned(active):
        return None
    integrity = object_value(active.get("integrity"))
    if integrity.get("status") != "pass":
        issues = integrity.get("issues")
        detail = "; ".join(str(item) for item in issues) if isinstance(issues, list) else ""
        raise StyleVersionMountConflictError(
            "active immutable style mount failed integrity checks"
            + (f": {detail}" if detail else "")
        )
    identity = {
        field: str(active.get(field) or "").strip()
        for field in ("style_id", "version_id", "content_hash")
    }
    if not all(identity.values()):
        raise StyleVersionMountConflictError(
            "active immutable style mount identity is incomplete"
        )
    prompt = safe_project_path(root, str(active.get("prompt_path") or ""))
    if prompt is None or not prompt.is_file():
        raise StyleVersionMountConflictError(
            "active immutable style mount prompt is missing or unsafe"
        )
    prompt_sha256 = hashlib.sha256(prompt.read_bytes()).hexdigest()
    snapshot_body = {
        "schema": STYLE_MOUNT_SNAPSHOT_SCHEMA,
        **identity,
        "prompt_sha256": prompt_sha256,
    }
    digest = hashlib.sha256(
        json.dumps(
            snapshot_body,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return StyleMountSnapshot(
        style_id=identity["style_id"],
        version_id=identity["version_id"],
        content_hash=identity["content_hash"],
        prompt_sha256=prompt_sha256,
        digest=digest,
        prompt_path=prompt,
    )


def active_style_mount_snapshot_payload(project_root: Path) -> dict[str, str]:
    snapshot = active_style_mount_snapshot(project_root)
    return snapshot.as_dict() if snapshot else {}


def active_style_mount_snapshot_bytes(project_root: Path) -> bytes:
    """Return a canonical byte representation for provenance digests."""

    return json.dumps(
        active_style_mount_snapshot_payload(project_root),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def artifact_style_mount_snapshot(*payloads: object) -> dict[str, Any]:
    """Read the first direct or generation-standard snapshot from artifacts."""

    for item in payloads:
        if not isinstance(item, dict):
            continue
        direct = item.get("style_mount_snapshot")
        if isinstance(direct, dict):
            return dict(direct)
        standards = item.get("generation_standards")
        if isinstance(standards, dict):
            nested = standards.get("style_mount_snapshot")
            if isinstance(nested, dict):
                return dict(nested)
    return {}


def read_artifact_style_mount_snapshot(*paths: Path) -> dict[str, Any]:
    """Read a snapshot from the first valid JSON artifact path."""

    payloads: list[dict[str, Any]] = []
    for path in paths:
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    return artifact_style_mount_snapshot(*payloads)


def active_style_prompt_path(project_root: Path) -> Path | None:
    """Resolve mounted prompt while refusing fallback for a broken version mount."""

    root = project_root.expanduser().resolve()
    active = inspect_active_style_mount(root)
    if not active:
        return None
    if _is_versioned(active):
        snapshot = active_style_mount_snapshot(root)
        return snapshot.prompt_path if snapshot else None
    prompt = safe_project_path(root, str(active.get("prompt_path") or ""))
    return prompt if prompt and prompt.is_file() else None


def active_style_evidence_paths(project_root: Path) -> list[Path]:
    """Return safe active-mount evidence paths for context provenance."""

    root = project_root.expanduser().resolve()
    active_path = root / "style" / "active_style_skill.json"
    active = inspect_active_style_mount(root)
    if not active:
        return []
    if _is_versioned(active):
        active_style_mount_snapshot(root)
    paths = [active_path] if active_path.is_file() else []
    for field in ("prompt_path", "style_skill", "style_version"):
        candidate = safe_project_path(root, str(active.get(field) or ""))
        if candidate and candidate.is_file():
            paths.append(candidate)
    return list(dict.fromkeys(paths))


def validate_style_mount_snapshot(
    project_root: Path,
    recorded: object,
) -> StyleMountSnapshotValidation:
    """Compare an artifact snapshot with the currently active immutable mount."""

    root = project_root.expanduser().resolve()
    active = inspect_active_style_mount(root)
    try:
        current_snapshot = active_style_mount_snapshot(root)
    except StyleVersionMountConflictError as exc:
        return StyleMountSnapshotValidation("conflict", str(exc), {})
    recorded_payload = recorded if isinstance(recorded, dict) else {}
    if current_snapshot is None:
        if recorded_payload.get("digest"):
            return StyleMountSnapshotValidation(
                "stale",
                "artifact references a style version that is no longer active",
                {},
            )
        if active:
            return StyleMountSnapshotValidation(
                "legacy_unverified",
                "legacy style mount has no immutable snapshot",
                {},
            )
        return StyleMountSnapshotValidation(
            "not_required",
            "no immutable style version is active",
            {},
        )
    current = current_snapshot.as_dict()
    if not recorded_payload:
        return StyleMountSnapshotValidation(
            "stale",
            "artifact predates the current immutable style mount snapshot",
            current,
        )
    mismatches = [
        field
        for field in (*_IDENTITY_FIELDS, "digest")
        if str(recorded_payload.get(field) or "") != str(current.get(field) or "")
    ]
    if mismatches:
        return StyleMountSnapshotValidation(
            "stale",
            "artifact style mount snapshot differs from the active version: "
            + ", ".join(mismatches),
            current,
        )
    if str(recorded_payload.get("schema") or "") != STYLE_MOUNT_SNAPSHOT_SCHEMA:
        return StyleMountSnapshotValidation(
            "stale",
            "artifact style mount snapshot schema is missing or outdated",
            current,
        )
    return StyleMountSnapshotValidation(
        "pass",
        "artifact uses the active immutable style mount snapshot",
        current,
    )


def style_mount_snapshot_errors(
    project_root: Path,
    artifacts: dict[str, object],
) -> list[str]:
    """Return stage-labelled errors when artifacts do not share the active snapshot."""

    errors: list[str] = []
    for label, recorded in artifacts.items():
        validation = validate_style_mount_snapshot(project_root, recorded)
        if not validation.passed:
            errors.append(f"{label} style mount snapshot {validation.status}: {validation.message}")
    return errors


def _is_versioned(payload: dict[str, Any]) -> bool:
    return (
        str(payload.get("schema") or "") == STYLE_VERSION_MOUNT_SCHEMA
        or bool(payload.get("version_id"))
        or bool(payload.get("content_hash"))
    )


__all__ = [
    "STYLE_MOUNT_SNAPSHOT_SCHEMA",
    "StyleMountSnapshot",
    "StyleMountSnapshotValidation",
    "active_style_evidence_paths",
    "active_style_mount_snapshot",
    "active_style_mount_snapshot_bytes",
    "active_style_mount_snapshot_payload",
    "active_style_prompt_path",
    "artifact_style_mount_snapshot",
    "read_artifact_style_mount_snapshot",
    "style_mount_snapshot_errors",
    "validate_style_mount_snapshot",
]
