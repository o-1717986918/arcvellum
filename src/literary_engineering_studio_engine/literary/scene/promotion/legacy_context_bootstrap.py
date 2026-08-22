"""One-time bootstrap for promoted scenes created before context archives."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from ....foundation.atomic_io import atomic_write_batch
from .context_archive import context_archive_plan
from .context_migration import (
    HistoricalContextMigrationResult,
    legacy_promotion_is_migratable,
    migrate_legacy_historical_context,
)
from .historical import validate_historical_promotion


LEGACY_BOOTSTRAP_ASSURANCE = "legacy-unsealed-project-context"


@dataclass(frozen=True)
class LegacyContextBootstrapPlan:
    scene_id: str
    promotion_manifest: str
    candidate: str
    candidate_manifest: str
    source_prompt_manifest: str
    source_draft: str
    source_context_packet: str
    source_context_trace: str
    archived_context_packet: str
    archived_context_trace: str
    archive_manifest: str
    bootstrap_snapshot: str
    migration_receipt: str

    @property
    def output_paths(self) -> tuple[str, ...]:
        return (
            self.promotion_manifest,
            self.archived_context_packet,
            self.archived_context_trace,
            self.archive_manifest,
            self.bootstrap_snapshot,
            self.migration_receipt,
        )


def legacy_context_migration_plan(
    root: Path,
    scene_id: str,
) -> LegacyContextBootstrapPlan | None:
    """Describe a one-time migration for an otherwise valid legacy promotion."""

    root = root.resolve()
    validation = validate_historical_promotion(root, scene_id)
    if not legacy_promotion_is_migratable(validation):
        return None
    if validation.candidate_path is None or validation.draft_path is None:
        return None
    promotion_path = root / "drafts" / "promotions" / f"{scene_id}_promotion.json"
    promotion = _read_json(promotion_path)
    evidence = promotion.get("historical_evidence")
    if not isinstance(evidence, dict) or isinstance(evidence.get("context_archive"), dict):
        return None
    candidate = validation.candidate_path.resolve()
    candidate_manifest = _read_json(candidate.with_suffix(".json"))
    prompt_rel = _normalized_relative(candidate_manifest.get("prompt_manifest"))
    if not prompt_rel:
        prompt_rel = candidate.with_suffix(".prompt.json").relative_to(root).as_posix()
    prompt_path = _safe_project_path(root, prompt_rel)
    prompt = _read_json(prompt_path) if prompt_path is not None else {}
    packet_rel = _normalized_relative(prompt.get("context"))
    trace_rel = _normalized_relative(prompt.get("context_trace"))
    packet = _safe_project_path(root, packet_rel)
    trace = _safe_project_path(root, trace_rel)
    if packet is None or trace is None:
        return None
    source_errors = _legacy_context_source_errors(
        scene_id,
        prompt,
        packet_rel,
        trace_rel,
        packet,
        trace,
    )
    if source_errors:
        raise ValueError("legacy context recovery is invalid: " + "; ".join(source_errors))
    archive = context_archive_plan(
        root,
        scene_id,
        candidate,
        packet_source=packet,
        trace_source=trace,
    )
    if not archive:
        raise ValueError("legacy context recovery could not plan an immutable archive")
    archive_id = str(archive["archive_id"])
    migration_dir = Path("workflow") / "migrations" / "historical_context"
    return LegacyContextBootstrapPlan(
        scene_id=scene_id,
        promotion_manifest=promotion_path.relative_to(root).as_posix(),
        candidate=candidate.relative_to(root).as_posix(),
        candidate_manifest=candidate.with_suffix(".json").relative_to(root).as_posix(),
        source_prompt_manifest=prompt_rel,
        source_draft=validation.draft_path.resolve().relative_to(root).as_posix(),
        source_context_packet=packet_rel,
        source_context_trace=trace_rel,
        archived_context_packet=str(archive["archived_context_packet"]),
        archived_context_trace=str(archive["archived_context_trace"]),
        archive_manifest=str(archive["archive_manifest"]),
        bootstrap_snapshot=(
            migration_dir / f"{scene_id}-{archive_id}.bootstrap.json"
        ).as_posix(),
        migration_receipt=(
            migration_dir / f"{scene_id}-{archive_id}.json"
        ).as_posix(),
    )


def legacy_context_migration_output_paths(
    root: Path,
    scene_id: str,
) -> tuple[str, ...]:
    plan = legacy_context_migration_plan(root, scene_id)
    return plan.output_paths if plan is not None else ()


def bootstrap_legacy_historical_context(
    root: Path,
    scene_id: str,
) -> HistoricalContextMigrationResult | None:
    """Seal still-present scene-time context before a legacy draft is revised."""

    root = root.resolve()
    plan = legacy_context_migration_plan(root, scene_id)
    if plan is None:
        return None
    promotion_path = root / plan.promotion_manifest
    promotion = _read_json(promotion_path)
    evidence = _dict(promotion.get("historical_evidence"))
    candidate = root / plan.candidate
    candidate_manifest = root / plan.candidate_manifest
    prompt_path = root / plan.source_prompt_manifest
    draft = root / plan.source_draft
    packet = root / plan.source_context_packet
    trace = root / plan.source_context_trace
    trace_payload = _read_json(trace)
    snapshot: dict[str, object] = {
        "schema": "arcvellum/historical-revision-context/v1",
        "scene_id": scene_id,
        "source_draft": plan.source_draft,
        "source_draft_sha256": _file_sha256(draft),
        "promotion_manifest": plan.promotion_manifest,
        "promotion_manifest_sha256": _file_sha256(promotion_path),
        "promotion_evidence_sha256": str(evidence.get("evidence_sha256") or "").lower(),
        "promoted_candidate": plan.candidate,
        "promoted_candidate_sha256": _file_sha256(candidate),
        "candidate_manifest": plan.candidate_manifest,
        "candidate_manifest_sha256": _file_sha256(candidate_manifest),
        "source_prompt_manifest": plan.source_prompt_manifest,
        "source_prompt_manifest_sha256": _file_sha256(prompt_path),
        "context_packet": plan.source_context_packet,
        "context_packet_sha256": _file_sha256(packet),
        "context_trace": plan.source_context_trace,
        "context_trace_sha256": _file_sha256(trace),
        "context_revisions": {
            key: str(trace_payload.get(key) or "")
            for key in (
                "project_revision",
                "state_revision",
                "canon_revision",
                "style_mount_revision",
                "word_budget_revision",
                "rhythm_plan_revision",
                "retrieval_digest",
            )
        },
        "recovery_assurance": LEGACY_BOOTSTRAP_ASSURANCE,
    }
    snapshot["snapshot_sha256"] = _payload_sha256(snapshot)
    snapshot_path = root / plan.bootstrap_snapshot
    atomic_write_batch(
        {
            snapshot_path: json.dumps(
                {"historical_context_snapshot": snapshot},
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        }
    )
    try:
        return migrate_legacy_historical_context(
            root,
            scene_id,
            snapshot_prompt=snapshot_path.relative_to(root),
            packet_source=packet,
            trace_source=trace,
        )
    except Exception:
        snapshot_path.unlink(missing_ok=True)
        raise


def _legacy_context_source_errors(
    scene_id: str,
    prompt: dict[str, object],
    packet_rel: str,
    trace_rel: str,
    packet: Path,
    trace: Path,
) -> list[str]:
    errors: list[str] = []
    if not packet.is_file() or not packet.read_text(encoding="utf-8", errors="ignore").strip():
        errors.append("legacy context packet is missing or empty")
    if not trace.is_file():
        errors.append("legacy context trace is missing")
        return errors
    trace_payload = _read_json(trace)
    if trace_payload.get("schema") != "literary-engineering-workbench/context-trace/v2":
        errors.append("legacy context trace schema is invalid")
    if str(trace_payload.get("scene_id") or "") != scene_id:
        errors.append("legacy context trace scene_id mismatch")
    declared = {
        _normalized_relative(item.get("path")): item
        for item in prompt.get("sources", [])
        if isinstance(item, dict) and _normalized_relative(item.get("path"))
    }
    for relative, source in ((packet_rel, packet), (trace_rel, trace)):
        evidence = declared.get(relative)
        if not isinstance(evidence, dict):
            errors.append(f"legacy prompt source declaration is missing: {relative}")
            continue
        try:
            expected_chars = int(evidence.get("chars") or -1)
        except (TypeError, ValueError):
            expected_chars = -1
        actual_chars = len(source.read_text(encoding="utf-8", errors="ignore"))
        # Old manifests counted text before final-newline normalization.  This
        # is a coarse presence check; the resulting archive uses exact hashes.
        if expected_chars < 0 or abs(expected_chars - actual_chars) > 2:
            errors.append(f"legacy prompt source length mismatch: {relative}")
    return errors


def _normalized_relative(value: object) -> str:
    text = str(value or "").strip().replace("\\", "/")
    if not text or text.startswith("/") or ":" in text.split("/", 1)[0]:
        return ""
    parts = text.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return ""
    return "/".join(parts)


def _safe_project_path(root: Path, relative: str) -> Path | None:
    normalized = _normalized_relative(relative)
    if not normalized:
        return None
    candidate = (root / normalized).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def _dict(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _payload_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


__all__ = [
    "LEGACY_BOOTSTRAP_ASSURANCE",
    "LegacyContextBootstrapPlan",
    "bootstrap_legacy_historical_context",
    "legacy_context_migration_output_paths",
    "legacy_context_migration_plan",
]
