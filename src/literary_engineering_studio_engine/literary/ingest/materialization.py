"""Deterministic service for reviewed archaeology candidate materialization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .materialization_records import (
    build_materialization_manifest,
    build_materialization_records,
    file_sha256,
    materialization_collision_errors,
)
from .materialization_storage import commit_materialization
from .reconstruction import verify_archaeology_aggregate
from .reconstruction_contracts import (
    read_json_object,
    reconstruction_paths,
    validate_identity_resolution,
    validate_reconstruction_candidate,
)
from .domain_review import validate_domain_review


def materialize_archaeology_candidates(
    project_root: Path,
    work_id: str,
) -> tuple[Path, list[str]]:
    root = project_root.resolve()
    import_dir = _import_dir(root, work_id)
    manifest, errors = read_json_object(import_dir / "source_manifest.json")
    output = root / reconstruction_paths(import_dir.relative_to(root))["materialization"]
    if errors:
        return output, errors
    context = _materialization_context(root, import_dir, manifest)
    errors = _materialization_gate_errors(root, import_dir, **context)
    if errors:
        return output, errors
    if str(manifest.get("mode") or "") == "analysis":
        return output, ["analysis mode cannot materialize promotable Archive candidates"]
    records = build_materialization_records(root, import_dir, **context)
    errors = materialization_collision_errors(root, records)
    if errors:
        return output, errors
    paths = reconstruction_paths(import_dir.relative_to(root))
    materialization = build_materialization_manifest(
        import_dir,
        **context,
        records=records,
    )
    commit_materialization(
        root,
        records,
        output=output,
        report=root / paths["materialization_report"],
        manifest=materialization,
    )
    return output, []


def archaeology_materialization_errors(
    root: Path,
    import_dir: Path,
) -> list[str]:
    manifest = _read_object(import_dir / "source_manifest.json")
    paths = reconstruction_paths(import_dir.relative_to(root))
    output = _read_project_object(root, paths["materialization"])
    if not output:
        return [f"archaeology materialization manifest missing: {paths['materialization']}"]
    context = _materialization_context(root, import_dir, manifest)
    errors = _materialization_gate_errors(root, import_dir, **context)
    if errors:
        return errors
    records = build_materialization_records(root, import_dir, **context)
    expected = build_materialization_manifest(
        import_dir,
        **context,
        records=records,
    )
    if output != expected:
        errors.append("archaeology materialization does not match current reviewed reconstruction")
    errors.extend(_materialized_asset_errors(root, output))
    return list(dict.fromkeys(errors))


def _materialization_context(
    root: Path,
    import_dir: Path,
    manifest: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    paths = reconstruction_paths(import_dir.relative_to(root))
    return {
        "manifest": manifest,
        "aggregate": _read_project_object(root, _aggregate_path(manifest)),
        "resolution": _read_project_object(root, paths["resolution"]),
        "candidate": _read_project_object(root, paths["candidate"]),
        "review": _read_project_object(root, paths["review"]),
    }


def _materialization_gate_errors(
    root: Path,
    import_dir: Path,
    *,
    manifest: dict[str, Any],
    aggregate: dict[str, Any],
    resolution: dict[str, Any],
    candidate: dict[str, Any],
    review: dict[str, Any],
) -> list[str]:
    if not all((manifest, aggregate, resolution, candidate, review)):
        return ["archaeology reconstruction inputs are incomplete"]
    errors = verify_archaeology_aggregate(
        root,
        manifest,
        aggregate,
        import_dir=import_dir.relative_to(root),
    )
    errors.extend(validate_identity_resolution(resolution, manifest=manifest, aggregate=aggregate))
    errors.extend(
        validate_reconstruction_candidate(
            candidate,
            manifest=manifest,
            aggregate=aggregate,
            resolution=resolution,
        )
    )
    errors.extend(validate_domain_review(review, manifest=manifest, candidate=candidate))
    if str(review.get("status") or "") != "pass":
        errors.append("archaeology domain review must pass before materialization")
    return list(dict.fromkeys(errors))


def _materialized_asset_errors(
    root: Path,
    output: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    for item in output.get("materialized_assets") or []:
        errors.extend(_materialized_asset_error(root, item))
    return errors


def _materialized_asset_error(root: Path, item: object) -> list[str]:
    if not isinstance(item, dict):
        return ["materialization asset record must be an object"]
    relative = str(item.get("candidate_path") or "")
    path = root / relative
    if not path.is_file():
        return [f"materialized Archive candidate missing: {relative}"]
    if file_sha256(path) != str(item.get("candidate_sha256") or ""):
        return [f"materialized Archive candidate changed: {relative}"]
    return []


def _aggregate_path(manifest: dict[str, Any]) -> str:
    archaeology = manifest.get("archaeology")
    return (
        str(archaeology.get("aggregate_path") or "")
        if isinstance(archaeology, dict)
        else ""
    )


def _import_dir(root: Path, work_id: str) -> Path:
    if not work_id or "/" in work_id or "\\" in work_id or work_id in {".", ".."}:
        raise ValueError("work_id must be a single source-import directory name")
    path = (root / "sources" / "imports" / work_id).resolve()
    if not path.is_relative_to((root / "sources" / "imports").resolve()):
        raise ValueError("source import path leaves the work project")
    return path


def _read_project_object(root: Path, relative: str) -> dict[str, Any]:
    path = _safe_project_path(root, relative)
    return _read_object(path) if path is not None else {}


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
