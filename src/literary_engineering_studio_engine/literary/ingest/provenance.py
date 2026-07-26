"""Freshness checks for Archive candidates derived by Project Archaeology."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .reconstruction import verify_archaeology_aggregate


_PROVENANCE_PATH_FIELDS = (
    "manifest_path",
    "aggregate_path",
    "resolution_path",
    "reconstruction_path",
    "domain_review_path",
)
_PROVENANCE_REVISION_FIELDS = {
    "aggregate_revision": "aggregate_path",
    "resolution_revision": "resolution_path",
    "reconstruction_revision": "reconstruction_path",
    "domain_review_revision": "domain_review_path",
}


def archaeology_candidate_provenance_errors(
    root: Path,
    payload: dict[str, Any],
) -> list[str]:
    provenance = payload.get("archaeology_provenance")
    if not isinstance(provenance, dict):
        return []
    errors = _required_field_errors(provenance)
    objects, source_errors = _load_provenance_sources(root, provenance)
    errors.extend(source_errors)
    errors.extend(_revision_errors(provenance, objects))
    errors.extend(_aggregate_errors(root, provenance, objects))
    return list(dict.fromkeys(errors))


def _required_field_errors(provenance: dict[str, Any]) -> list[str]:
    required = (*_PROVENANCE_PATH_FIELDS, *_PROVENANCE_REVISION_FIELDS)
    return [
        f"archaeology provenance missing {field}"
        for field in required
        if not str(provenance.get(field) or "")
    ]


def _load_provenance_sources(
    root: Path,
    provenance: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    objects: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for field in _PROVENANCE_PATH_FIELDS:
        relative = str(provenance.get(field) or "")
        path = _safe_project_path(root, relative)
        if path is None or not path.is_file():
            errors.append(f"archaeology provenance source missing: {relative or field}")
        else:
            objects[field] = _read_object(path)
    return objects, errors


def _revision_errors(
    provenance: dict[str, Any],
    objects: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    for field, object_key in _PROVENANCE_REVISION_FIELDS.items():
        current = str(objects.get(object_key, {}).get("revision") or "")
        if current and current != str(provenance.get(field) or ""):
            errors.append(f"archaeology candidate is stale: {field} changed")
    return errors


def _aggregate_errors(
    root: Path,
    provenance: dict[str, Any],
    objects: dict[str, dict[str, Any]],
) -> list[str]:
    manifest = objects.get("manifest_path", {})
    aggregate = objects.get("aggregate_path", {})
    if not manifest or not aggregate:
        return []
    import_dir = (root / str(provenance["manifest_path"])).parent
    return verify_archaeology_aggregate(
        root,
        manifest,
        aggregate,
        import_dir=import_dir.relative_to(root),
    )


def _safe_project_path(root: Path, relative: str) -> Path | None:
    path = Path(relative.replace("\\", "/"))
    if not relative or path.is_absolute() or ".." in path.parts:
        return None
    resolved = (root / path).resolve()
    return resolved if resolved.is_relative_to(root.resolve()) else None


def _read_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
