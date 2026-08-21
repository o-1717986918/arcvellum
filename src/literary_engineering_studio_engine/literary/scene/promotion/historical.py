"""Tamper-evident evidence for prose that has crossed the promotion boundary."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from .context_archive import context_archive_errors, seal_context_archive


HISTORICAL_PROMOTION_LEGACY_SCHEMA = "arcvellum/historical-scene-promotion/v1"
HISTORICAL_PROMOTION_SCHEMA = "arcvellum/historical-scene-promotion/v2"


@dataclass(frozen=True)
class HistoricalPromotionValidation:
    """Validation result for an immutable promoted-scene evidence record."""

    status: str
    errors: tuple[str, ...]
    candidate_path: Path | None = None
    draft_path: Path | None = None
    current: bool = False

    @property
    def passed(self) -> bool:
        return self.status == "pass" and not self.errors


def build_historical_promotion_evidence(
    root: Path,
    *,
    scene_id: str,
    candidate_path: Path,
    draft_path: Path,
    generation_gate: dict[str, object],
    review_gate: dict[str, object],
    style_mount_snapshot: dict[str, object],
    context_archive: dict[str, object] | None = None,
    migration_predecessor: dict[str, object] | None = None,
) -> dict[str, object]:
    """Seal the exact prose, review, generation, and style evidence at promotion."""

    evidence: dict[str, object] = {
        "schema": HISTORICAL_PROMOTION_SCHEMA,
        "scene_id": scene_id,
        "candidate": _relative_path(root, candidate_path),
        "candidate_sha256": _file_sha256(candidate_path),
        "draft": _relative_path(root, draft_path),
        "draft_sha256": _file_sha256(draft_path),
        "style_mount_snapshot": style_mount_snapshot,
        "candidate_generation_gate_sha256": _payload_sha256(generation_gate),
        "candidate_review_gate_sha256": _payload_sha256(review_gate),
    }
    if context_archive:
        evidence["context_archive"] = context_archive
    if migration_predecessor:
        evidence["migration_predecessor"] = migration_predecessor
    evidence["evidence_sha256"] = _payload_sha256(evidence)
    return evidence


def seal_historical_promotion(
    root: Path,
    manifest: dict[str, object],
    candidate_path: Path,
    draft_path: Path,
    *,
    context_archive: dict[str, object] | None = None,
) -> dict[str, object]:
    """Attach machine-owned historical evidence to a passed promotion manifest."""

    generation_gate = manifest.get("candidate_generation")
    review_gate = manifest.get("candidate_review")
    if not isinstance(generation_gate, dict) or not isinstance(review_gate, dict):
        raise ValueError("promotion manifest requires generation and review gates")
    snapshot = manifest.get("style_mount_snapshot")
    archive = context_archive or seal_context_archive(
        root,
        str(manifest.get("scene_id") or ""),
        candidate_path,
    )
    manifest["historical_evidence"] = build_historical_promotion_evidence(
        root,
        scene_id=str(manifest.get("scene_id") or ""),
        candidate_path=candidate_path,
        draft_path=draft_path,
        generation_gate=generation_gate,
        review_gate=review_gate,
        style_mount_snapshot=snapshot if isinstance(snapshot, dict) else {},
        context_archive=archive,
    )
    return manifest


def validate_historical_promotion(
    root: Path,
    scene_id: str,
    manifest: dict[str, object] | None = None,
) -> HistoricalPromotionValidation:
    """Validate historical truth without comparing it to today's active style."""

    root = root.resolve()
    payload = manifest if manifest is not None else _read_json(
        root / "drafts" / "promotions" / f"{scene_id}_promotion.json"
    )
    evidence = payload.get("historical_evidence")
    if not isinstance(evidence, dict):
        return HistoricalPromotionValidation(
            status="legacy",
            errors=("promotion manifest has no historical_evidence",),
        )

    errors = _identity_errors(payload, evidence, scene_id)
    candidate_path = _safe_project_path(root, evidence.get("candidate"), "candidate", errors)
    draft_path = _safe_project_path(root, evidence.get("draft"), "draft", errors)
    errors.extend(_manifest_binding_errors(payload, evidence))
    errors.extend(_gate_digest_errors(payload, evidence))
    errors.extend(_context_archive_evidence_errors(root, evidence))
    _match_file_hash(candidate_path, evidence.get("candidate_sha256"), "candidate", errors)
    _match_file_hash(draft_path, evidence.get("draft_sha256"), "draft", errors)
    _match_candidate_style_snapshot(candidate_path, evidence.get("style_mount_snapshot"), errors)
    errors.extend(_evidence_digest_errors(evidence))

    current = not errors and not _has_newer_candidate(
        root,
        scene_id,
        candidate_path,
    )
    return HistoricalPromotionValidation(
        status="pass" if not errors else "invalid",
        errors=tuple(errors),
        candidate_path=candidate_path,
        draft_path=draft_path,
        current=current,
    )


def historical_promotion_archive_paths(
    root: Path,
    scene_id: str,
) -> tuple[str, ...]:
    """Return the exact archive files of a current valid promotion."""

    root = root.resolve()
    validation = validate_historical_promotion(root, scene_id)
    if not validation.passed or not validation.current:
        return ()
    payload = _read_json(
        root / "drafts" / "promotions" / f"{scene_id}_promotion.json"
    )
    evidence = payload.get("historical_evidence")
    archive = evidence.get("context_archive") if isinstance(evidence, dict) else None
    if context_archive_errors(root, archive):
        return ()
    paths: list[str] = []
    for key in (
        "archived_context_packet",
        "archived_context_trace",
        "archive_manifest",
    ):
        value = archive.get(key) if isinstance(archive, dict) else None
        resolved = _safe_project_path(root, value, key, [])
        if resolved is None or not resolved.is_file():
            return ()
        paths.append(_relative_path(root, resolved))
    return tuple(paths)


def _identity_errors(
    manifest: dict[str, object],
    evidence: dict[str, object],
    scene_id: str,
) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema") != "literary-engineering-workbench/candidate-promotion/v0.1":
        errors.append("promotion manifest has wrong or missing schema")
    if str(manifest.get("scene_id") or "") != scene_id:
        errors.append("promotion manifest scene_id mismatch")
    if evidence.get("schema") not in {
        HISTORICAL_PROMOTION_LEGACY_SCHEMA,
        HISTORICAL_PROMOTION_SCHEMA,
    }:
        errors.append("historical promotion evidence has wrong or missing schema")
    if str(evidence.get("scene_id") or "") != scene_id:
        errors.append("historical promotion evidence scene_id mismatch")
    if manifest.get("allow_unreviewed") is True or manifest.get("allow_review_notes") is True:
        errors.append("historical promotion evidence cannot seal a review bypass")
    return errors


def _context_archive_evidence_errors(
    root: Path,
    evidence: dict[str, object],
) -> list[str]:
    if evidence.get("schema") == HISTORICAL_PROMOTION_LEGACY_SCHEMA:
        return []
    return context_archive_errors(root, evidence.get("context_archive"))


def _manifest_binding_errors(
    manifest: dict[str, object],
    evidence: dict[str, object],
) -> list[str]:
    return [
        f"historical promotion {key} does not match promotion manifest"
        for key in (
            "candidate",
            "candidate_sha256",
            "draft",
            "draft_sha256",
            "style_mount_snapshot",
        )
        if manifest.get(key) != evidence.get(key)
    ]


def _gate_digest_errors(
    manifest: dict[str, object],
    evidence: dict[str, object],
) -> list[str]:
    errors: list[str] = []
    for gate_key, digest_key, label in (
        (
            "candidate_generation",
            "candidate_generation_gate_sha256",
            "candidate generation",
        ),
        ("candidate_review", "candidate_review_gate_sha256", "candidate review"),
    ):
        gate = manifest.get(gate_key)
        if not isinstance(gate, dict) or gate.get("status") != "pass":
            errors.append(f"sealed {label} gate was not pass")
        elif evidence.get(digest_key) != _payload_sha256(gate):
            errors.append(f"sealed {label} gate digest mismatch")
    return errors


def _evidence_digest_errors(evidence: dict[str, object]) -> list[str]:
    expected = str(evidence.get("evidence_sha256") or "").lower()
    unsigned = dict(evidence)
    unsigned.pop("evidence_sha256", None)
    if expected and expected == _payload_sha256(unsigned):
        return []
    return ["historical promotion evidence digest mismatch"]


def _match_file_hash(
    path: Path | None,
    expected: object,
    label: str,
    errors: list[str],
) -> None:
    digest = str(expected or "").lower()
    if path is None or not path.is_file():
        errors.append(f"historical promotion {label} is missing")
    elif not digest or _file_sha256(path) != digest:
        errors.append(f"historical promotion {label} digest mismatch")


def _match_candidate_style_snapshot(
    candidate_path: Path | None,
    expected: object,
    errors: list[str],
) -> None:
    if candidate_path is None:
        return
    manifest = _read_json(candidate_path.with_suffix(".json"))
    actual = (
        manifest.get("style_mount_snapshot")
        if isinstance(manifest.get("style_mount_snapshot"), dict)
        else {}
    )
    normalized_expected = expected if isinstance(expected, dict) else {}
    if actual != normalized_expected:
        errors.append("historical style snapshot does not match candidate manifest")


def _safe_project_path(
    root: Path,
    value: object,
    label: str,
    errors: list[str],
) -> Path | None:
    text = str(value or "").replace("\\", "/").strip()
    if not text:
        errors.append(f"historical promotion {label} path is missing")
        return None
    relative = Path(text)
    if relative.is_absolute():
        errors.append(f"historical promotion {label} path must be project-relative")
        return None
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        errors.append(f"historical promotion {label} path escapes project root")
        return None
    return resolved


def _has_newer_candidate(
    root: Path,
    scene_id: str,
    promoted_candidate: Path | None,
) -> bool:
    if promoted_candidate is None or not promoted_candidate.is_file():
        return False
    promoted_resolved = promoted_candidate.resolve()
    promoted_at = promoted_candidate.stat().st_mtime_ns
    for path in _formal_scene_candidates(root, scene_id):
        if path.resolve() != promoted_resolved and path.stat().st_mtime_ns > promoted_at:
            return True
    return False


def _formal_scene_candidates(root: Path, scene_id: str) -> tuple[Path, ...]:
    candidates = root / "drafts" / "candidates"
    revisions = root / "drafts" / "revisions"
    paths = (
        [
            path
            for path in candidates.glob(f"{scene_id}-*.md")
            if not path.name.endswith((".agent_tasks.md", ".prompt.md", "_report.md"))
        ]
        if candidates.is_dir()
        else []
    )
    revision_name = re.compile(
        rf"^{re.escape(scene_id)}_revision(?:_[0-9]+)?\.md$"
    )
    if revisions.is_dir():
        paths.extend(
            path
            for path in revisions.glob(f"{scene_id}_revision*.md")
            if revision_name.fullmatch(path.name)
        )
    return tuple(paths)


def _relative_path(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


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
    "HISTORICAL_PROMOTION_LEGACY_SCHEMA",
    "HISTORICAL_PROMOTION_SCHEMA",
    "HistoricalPromotionValidation",
    "build_historical_promotion_evidence",
    "historical_promotion_archive_paths",
    "seal_historical_promotion",
    "validate_historical_promotion",
]
