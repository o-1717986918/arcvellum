"""Pure record construction for reviewed archaeology materialization."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ...agent_schema import validate_payload
from ..assets.registry import ASSET_CANDIDATE_DIRS, ASSET_SCHEMA_NAMES
from .evidence import canonical_digest
from .reconstruction_contracts import MATERIALIZATION_SCHEMA, reconstruction_paths


def build_materialization_records(
    root: Path,
    import_dir: Path,
    *,
    manifest: dict[str, Any],
    aggregate: dict[str, Any],
    resolution: dict[str, Any],
    candidate: dict[str, Any],
    review: dict[str, Any],
) -> list[dict[str, Any]]:
    decisions = _review_decisions(review)
    provenance_paths = _provenance_paths(root, import_dir, manifest=manifest)
    records: list[dict[str, Any]] = []
    for asset in candidate.get("assets") or []:
        record = _materialization_record(
            asset,
            decisions=decisions,
            provenance_paths=provenance_paths,
            manifest=manifest,
            aggregate=aggregate,
            resolution=resolution,
            candidate=candidate,
            review=review,
        )
        if record:
            records.append(record)
    return records


def build_materialization_manifest(
    import_dir: Path,
    *,
    manifest: dict[str, Any],
    aggregate: dict[str, Any],
    resolution: dict[str, Any],
    candidate: dict[str, Any],
    review: dict[str, Any],
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    materialized_ids = {str(record["candidate_id"]) for record in records}
    payload = {
        "schema": MATERIALIZATION_SCHEMA,
        "work_id": str(manifest.get("work_id") or import_dir.name),
        "mode": str(manifest.get("mode") or ""),
        "status": "complete",
        "aggregate_revision": str(aggregate.get("revision") or ""),
        "resolution_revision": str(resolution.get("revision") or ""),
        "reconstruction_revision": str(candidate.get("revision") or ""),
        "domain_review_revision": str(review.get("revision") or ""),
        "materialized_assets": [_manifest_asset(item) for item in records],
        "deferred_assets": _deferred_assets(
            candidate,
            decisions=_review_decisions(review),
            materialized_ids=materialized_ids,
        ),
        "rules": [
            "Materialized files are Archive candidates, not formal project truth.",
            "Every candidate still requires exact-content Archive review and approval.",
            "Source or reconstruction changes make archaeology provenance stale.",
        ],
    }
    payload["revision"] = canonical_digest(payload)
    return payload


def materialization_collision_errors(
    root: Path,
    records: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    registered = set(ASSET_CANDIDATE_DIRS.values())
    for record in records:
        errors.extend(_record_collision_errors(root, record, registered))
    return list(dict.fromkeys(errors))


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _materialization_record(
    asset: object,
    *,
    decisions: dict[str, str],
    provenance_paths: dict[str, str],
    manifest: dict[str, Any],
    aggregate: dict[str, Any],
    resolution: dict[str, Any],
    candidate: dict[str, Any],
    review: dict[str, Any],
) -> dict[str, Any] | None:
    if not isinstance(asset, dict):
        return None
    candidate_id = str(asset.get("candidate_id") or "")
    if not _is_promotable_asset(asset, decisions.get(candidate_id)):
        return None
    asset_type = str(asset.get("asset_type") or "").strip().lower().replace("_", "-")
    payload = _candidate_payload(
        asset,
        asset_type=asset_type,
        candidate_id=candidate_id,
        provenance_paths=provenance_paths,
        manifest=manifest,
        aggregate=aggregate,
        resolution=resolution,
        candidate=candidate,
        review=review,
    )
    schema_errors, _warnings = validate_payload(payload, ASSET_SCHEMA_NAMES[asset_type])
    if schema_errors:
        raise ValueError(f"reviewed archaeology asset became invalid: {candidate_id}")
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    relative = ASSET_CANDIDATE_DIRS[asset_type] / f"{candidate_id}.json"
    return {
        "candidate_id": candidate_id,
        "asset_type": asset_type,
        "candidate_path": relative.as_posix(),
        "candidate_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        "payload": payload,
        "encoded": encoded,
    }


def _candidate_payload(
    asset: dict[str, Any],
    *,
    asset_type: str,
    candidate_id: str,
    provenance_paths: dict[str, str],
    manifest: dict[str, Any],
    aggregate: dict[str, Any],
    resolution: dict[str, Any],
    candidate: dict[str, Any],
    review: dict[str, Any],
) -> dict[str, Any]:
    payload = dict(asset.get("payload") or {})
    source_paths = [
        str(item) for item in payload.get("source_paths") or [] if str(item).strip()
    ]
    payload.update(
        {
            "asset_type": asset_type,
            "candidate_id": candidate_id,
            "source_paths": list(
                dict.fromkeys([*source_paths, *provenance_paths.values()])
            ),
            "candidate_status": "ready_for_review",
            "archaeology_provenance": {
                **provenance_paths,
                "work_id": str(manifest.get("work_id") or ""),
                "mode": str(manifest.get("mode") or ""),
                "aggregate_revision": str(aggregate.get("revision") or ""),
                "resolution_revision": str(resolution.get("revision") or ""),
                "reconstruction_revision": str(candidate.get("revision") or ""),
                "domain_review_revision": str(review.get("revision") or ""),
                "evidence_refs": list(asset.get("evidence_refs") or []),
                "confidence": asset.get("confidence"),
                "unresolved_refs": list(asset.get("unresolved_refs") or []),
            },
        }
    )
    return payload


def _review_decisions(review: dict[str, Any]) -> dict[str, str]:
    return {
        str(item.get("candidate_id") or ""): str(item.get("decision") or "")
        for item in review.get("asset_decisions") or []
        if isinstance(item, dict)
    }


def _is_promotable_asset(asset: dict[str, Any], decision: str | None) -> bool:
    return (
        decision == "promote"
        and str(asset.get("promotion_recommendation") or "") == "promote"
    )


def _manifest_asset(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": item["candidate_id"],
        "asset_type": item["asset_type"],
        "candidate_path": item["candidate_path"],
        "candidate_sha256": item["candidate_sha256"],
    }


def _deferred_assets(
    candidate: dict[str, Any],
    *,
    decisions: dict[str, str],
    materialized_ids: set[str],
) -> list[dict[str, str]]:
    return [
        {
            "candidate_id": str(item.get("candidate_id") or ""),
            "decision": decisions.get(str(item.get("candidate_id") or ""), "hold"),
        }
        for item in candidate.get("assets") or []
        if isinstance(item, dict)
        and str(item.get("candidate_id") or "") not in materialized_ids
    ]


def _provenance_paths(
    root: Path,
    import_dir: Path,
    *,
    manifest: dict[str, Any],
) -> dict[str, str]:
    paths = reconstruction_paths(import_dir.relative_to(root))
    archaeology = manifest.get("archaeology")
    aggregate = (
        str(archaeology.get("aggregate_path") or "")
        if isinstance(archaeology, dict)
        else ""
    )
    return {
        "manifest_path": (import_dir / "source_manifest.json").relative_to(root).as_posix(),
        "aggregate_path": aggregate,
        "resolution_path": paths["resolution"],
        "reconstruction_path": paths["candidate"],
        "domain_review_path": paths["review"],
    }


def _record_collision_errors(
    root: Path,
    record: dict[str, Any],
    registered: set[Path],
) -> list[str]:
    candidate_id = str(record["candidate_id"])
    target = (root / str(record["candidate_path"])).resolve()
    errors = [
        f"Archive candidate id already exists in another candidate domain: {candidate_id}"
        for folder in registered
        if (root / folder / f"{candidate_id}.json").resolve().is_file()
        and (root / folder / f"{candidate_id}.json").resolve() != target
    ]
    if target.is_file() and file_sha256(target) != str(record["candidate_sha256"]):
        errors.append(
            "refusing to overwrite an existing Archive candidate with changed "
            f"reconstruction content: {candidate_id}; issue a new candidate_id"
        )
    return errors
