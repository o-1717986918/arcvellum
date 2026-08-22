"""Audited migration of legacy promoted-scene context into immutable storage."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from ....foundation.atomic_io import atomic_write_batch
from .context_archive import seal_context_archive
from .historical import (
    build_historical_promotion_evidence,
    validate_historical_promotion,
)


MIGRATION_SCHEMA = "arcvellum/historical-context-migration/v1"


@dataclass(frozen=True)
class HistoricalContextMigrationResult:
    promotion_manifest: Path
    archive_manifest: Path
    receipt: Path
    archive_id: str


@dataclass(frozen=True)
class _MigrationInputs:
    promotion_path: Path
    promotion: dict[str, object]
    candidate_path: Path
    draft_path: Path
    snapshot_path: Path
    snapshot: dict[str, object]
    before_manifest_sha: str
    before_evidence_sha: str


def migrate_legacy_historical_context(
    root: Path,
    scene_id: str,
    *,
    snapshot_prompt: Path,
    packet_source: Path,
    trace_source: Path,
) -> HistoricalContextMigrationResult:
    """Recover exact legacy context only when a revision snapshot proves it."""

    root = root.resolve()
    inputs = _migration_inputs(
        root, scene_id, snapshot_prompt, packet_source, trace_source
    )
    archive = seal_context_archive(
        root,
        scene_id,
        inputs.candidate_path,
        packet_source=packet_source,
        trace_source=trace_source,
    )
    migrated = _migrated_promotion(root, scene_id, inputs, archive)
    manifest_text = json.dumps(migrated, ensure_ascii=False, indent=2) + "\n"
    receipt_path = (
        root
        / "workflow"
        / "migrations"
        / "historical_context"
        / f"{scene_id}-{archive['archive_id']}.json"
    )
    receipt = _migration_receipt(
        root, scene_id, inputs, archive, migrated, manifest_text, packet_source, trace_source
    )
    atomic_write_batch(
        {
            inputs.promotion_path: manifest_text,
            receipt_path: json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        }
    )
    migrated_validation = validate_historical_promotion(root, scene_id)
    if not migrated_validation.passed:
        raise ValueError(
            "migrated historical promotion is invalid: "
            + "; ".join(migrated_validation.errors)
        )
    return HistoricalContextMigrationResult(
        promotion_manifest=inputs.promotion_path,
        archive_manifest=root / str(archive["archive_manifest"]),
        receipt=receipt_path,
        archive_id=str(archive["archive_id"]),
    )


def _migration_inputs(
    root: Path,
    scene_id: str,
    snapshot_prompt: Path,
    packet_source: Path,
    trace_source: Path,
) -> _MigrationInputs:
    promotion_path = root / "drafts" / "promotions" / f"{scene_id}_promotion.json"
    promotion = _read_json(promotion_path)
    validation = validate_historical_promotion(root, scene_id, promotion)
    if (
        not legacy_promotion_is_migratable(validation)
        or validation.candidate_path is None
        or validation.draft_path is None
    ):
        raise ValueError("legacy promotion is not valid: " + "; ".join(validation.errors))
    evidence = promotion.get("historical_evidence")
    if not isinstance(evidence, dict):
        raise ValueError("legacy promotion has no historical evidence")
    if isinstance(evidence.get("context_archive"), dict):
        raise ValueError("promotion already has an immutable context archive")
    snapshot_path = _resolve_project_path(root, snapshot_prompt)
    snapshot = _read_json(snapshot_path).get("historical_context_snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("migration snapshot prompt has no historical_context_snapshot")
    before_manifest_sha = _file_sha256(promotion_path)
    before_evidence_sha = str(evidence.get("evidence_sha256") or "").lower()
    _validate_snapshot_binding(
        root, scene_id, snapshot, promotion_path, validation.draft_path,
        before_manifest_sha, before_evidence_sha, packet_source, trace_source,
    )
    return _MigrationInputs(
        promotion_path, promotion, validation.candidate_path, validation.draft_path,
        snapshot_path, snapshot, before_manifest_sha, before_evidence_sha,
    )


def _validate_snapshot_binding(
    root: Path, scene_id: str, snapshot: dict[str, object], promotion_path: Path,
    draft_path: Path, promotion_sha: str, evidence_sha: str,
    packet_source: Path, trace_source: Path,
) -> None:
    errors = _snapshot_identity_errors(scene_id, snapshot)
    errors.extend(_snapshot_promotion_errors(root, snapshot, promotion_path, draft_path, promotion_sha, evidence_sha))
    errors.extend(_snapshot_source_errors(snapshot, packet_source, trace_source))
    if errors:
        raise ValueError("invalid historical context migration: " + "; ".join(errors))


def _snapshot_identity_errors(scene_id: str, snapshot: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if snapshot.get("schema") != "arcvellum/historical-revision-context/v1":
        errors.append("snapshot schema mismatch")
    unsigned = dict(snapshot)
    snapshot_sha = str(unsigned.pop("snapshot_sha256", "") or "").lower()
    if not snapshot_sha or snapshot_sha != _payload_sha256(unsigned):
        errors.append("snapshot identity digest mismatch")
    if str(snapshot.get("scene_id") or "") != scene_id:
        errors.append("snapshot scene_id mismatch")
    return errors


def _snapshot_promotion_errors(
    root: Path, snapshot: dict[str, object], promotion_path: Path,
    draft_path: Path, promotion_sha: str, evidence_sha: str,
) -> list[str]:
    errors: list[str] = []
    if str(snapshot.get("promotion_manifest") or "").replace("\\", "/") != promotion_path.relative_to(root).as_posix():
        errors.append("snapshot promotion path mismatch")
    if str(snapshot.get("source_draft") or "").replace("\\", "/") != draft_path.relative_to(root).as_posix():
        errors.append("snapshot source draft path mismatch")
    if str(snapshot.get("source_draft_sha256") or "").lower() != _file_sha256(draft_path):
        errors.append("snapshot source draft digest mismatch")
    if str(snapshot.get("promotion_manifest_sha256") or "").lower() != promotion_sha:
        errors.append("snapshot promotion manifest digest mismatch")
    if str(snapshot.get("promotion_evidence_sha256") or "").lower() != evidence_sha:
        errors.append("snapshot promotion evidence digest mismatch")
    return errors


def _snapshot_source_errors(
    snapshot: dict[str, object], packet_source: Path, trace_source: Path,
) -> list[str]:
    errors: list[str] = []
    for source, key in (
        (packet_source, "context_packet_sha256"),
        (trace_source, "context_trace_sha256"),
    ):
        if not source.is_file():
            errors.append(f"recovery source not found: {source}")
        elif _file_sha256(source) != str(snapshot.get(key) or "").lower():
            errors.append(f"recovery source does not match {key}")
    return errors


def _migrated_promotion(
    root: Path,
    scene_id: str,
    inputs: _MigrationInputs,
    archive: dict[str, object],
) -> dict[str, object]:
    predecessor = {
        "schema": "arcvellum/historical-context-migration-predecessor/v1",
        "promotion_manifest_sha256": inputs.before_manifest_sha,
        "promotion_evidence_sha256": inputs.before_evidence_sha,
        "revision_snapshot_sha256": str(inputs.snapshot.get("snapshot_sha256") or "").lower(),
    }
    migrated = dict(inputs.promotion)
    migrated["historical_evidence"] = build_historical_promotion_evidence(
        root,
        scene_id=scene_id,
        candidate_path=inputs.candidate_path,
        draft_path=inputs.draft_path,
        generation_gate=_dict(inputs.promotion.get("candidate_generation")),
        review_gate=_dict(inputs.promotion.get("candidate_review")),
        style_mount_snapshot=_dict(inputs.promotion.get("style_mount_snapshot")),
        context_archive=archive,
        migration_predecessor=predecessor,
    )
    return migrated


def _migration_receipt(
    root: Path,
    scene_id: str,
    inputs: _MigrationInputs,
    archive: dict[str, object],
    migrated: dict[str, object],
    manifest_text: str,
    packet_source: Path,
    trace_source: Path,
) -> dict[str, object]:
    historical = _dict(migrated.get("historical_evidence"))
    return {
        "schema": MIGRATION_SCHEMA,
        "scene_id": scene_id,
        "status": "applied",
        "promotion_manifest": inputs.promotion_path.relative_to(root).as_posix(),
        "promotion_manifest_before_sha256": inputs.before_manifest_sha,
        "promotion_manifest_after_sha256": _bytes_sha256(manifest_text.encode("utf-8")),
        "historical_evidence_before_sha256": inputs.before_evidence_sha,
        "historical_evidence_after_sha256": str(historical.get("evidence_sha256") or ""),
        "snapshot_prompt": inputs.snapshot_path.relative_to(root).as_posix(),
        "snapshot_prompt_sha256": _file_sha256(inputs.snapshot_path),
        "snapshot_sha256": str(inputs.snapshot.get("snapshot_sha256") or ""),
        "recovery_assurance": str(inputs.snapshot.get("recovery_assurance") or "exact-snapshot"),
        "recovery_packet_source": str(packet_source.resolve()),
        "recovery_trace_source": str(trace_source.resolve()),
        "context_archive": archive,
    }


def legacy_promotion_is_migratable(validation: object) -> bool:
    errors = tuple(getattr(validation, "errors", ()) or ())
    return bool(
        getattr(validation, "candidate_path", None) is not None
        and getattr(validation, "draft_path", None) is not None
        and (
            bool(getattr(validation, "passed", False))
            or errors == ("historical context archive is missing",)
        )
    )
def _resolve_project_path(root: Path, value: Path) -> Path:
    path = value if value.is_absolute() else root / value
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("snapshot prompt must be inside the work project") from exc
    return resolved


def _dict(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def _file_sha256(path: Path) -> str:
    return _bytes_sha256(path.read_bytes())


def _bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _payload_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _bytes_sha256(encoded)


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


__all__ = [
    "HistoricalContextMigrationResult",
    "MIGRATION_SCHEMA",
    "legacy_promotion_is_migratable",
    "migrate_legacy_historical_context",
]
