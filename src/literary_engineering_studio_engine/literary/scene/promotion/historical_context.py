"""Tamper-evident context snapshots for revisions of promoted prose."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .context_archive import archived_context_paths, context_archive_errors
from .historical import validate_historical_promotion


HISTORICAL_REVISION_CONTEXT_SCHEMA = (
    "arcvellum/historical-revision-context/v1"
)


def historical_revision_source_paths(
    root: Path,
    scene_id: str,
    source_path: Path,
) -> tuple[str, ...]:
    """Return the exact files needed to prove a promoted source snapshot."""

    proof = _historical_source_proof(root, scene_id, source_path, require_current=True)
    if proof is None:
        return ()
    return tuple(
        dict.fromkeys(
            (
                str(proof["promotion_manifest"]),
                str(proof["promoted_candidate"]),
                str(proof["candidate_manifest"]),
                str(proof["source_prompt_manifest"]),
                *archived_context_paths(proof.get("context_archive")),
                str(
                    (proof.get("context_archive") or {}).get("archive_manifest")
                    if isinstance(proof.get("context_archive"), dict)
                    else ""
                ),
            )
        )
    )


def historical_revision_reading_paths(
    root: Path,
    scene_id: str,
    source_path: Path,
) -> tuple[str, ...]:
    """Return the archived packet and trace a revision Agent may read."""

    proof = _historical_source_proof(root, scene_id, source_path, require_current=True)
    return archived_context_paths(proof.get("context_archive")) if proof else ()


def build_historical_revision_context_snapshot(
    root: Path,
    scene_id: str,
    source_path: Path,
) -> dict[str, object]:
    """Seal the scene-time context used by an exact promoted source draft."""

    proof = _historical_source_proof(root, scene_id, source_path, require_current=True)
    if proof is None:
        return {}
    archive = proof.get("context_archive")
    if not isinstance(archive, dict) or context_archive_errors(root, archive):
        return {}
    context_rel, trace_rel = archived_context_paths(archive)
    context_path = _safe_project_path(root, context_rel)
    trace_path = _safe_project_path(root, trace_rel)
    if context_path is None or trace_path is None:
        return {}
    if not context_path.is_file() or not trace_path.is_file():
        return {}
    trace = _read_json(trace_path)
    if str(trace.get("scene_id") or "") != scene_id:
        return {}

    snapshot: dict[str, object] = {
        "schema": HISTORICAL_REVISION_CONTEXT_SCHEMA,
        "scene_id": scene_id,
        "source_draft": str(proof["source_draft"]),
        "source_draft_sha256": str(proof["source_draft_sha256"]),
        "promotion_manifest": str(proof["promotion_manifest"]),
        "promotion_manifest_sha256": str(proof["promotion_manifest_sha256"]),
        "promotion_evidence_sha256": str(proof["promotion_evidence_sha256"]),
        "promoted_candidate": str(proof["promoted_candidate"]),
        "promoted_candidate_sha256": str(proof["promoted_candidate_sha256"]),
        "candidate_manifest": str(proof["candidate_manifest"]),
        "candidate_manifest_sha256": str(proof["candidate_manifest_sha256"]),
        "source_prompt_manifest": str(proof["source_prompt_manifest"]),
        "source_prompt_manifest_sha256": str(proof["source_prompt_manifest_sha256"]),
        "context_packet": context_rel,
        "context_packet_sha256": _file_sha256(context_path),
        "context_trace": trace_rel,
        "context_trace_sha256": _file_sha256(trace_path),
        "context_revisions": {
            key: str(trace.get(key) or "")
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
    }
    snapshot["snapshot_sha256"] = _payload_sha256(snapshot)
    return snapshot


def historical_revision_context_errors(
    root: Path,
    scene_id: str,
    *,
    source_rel: object,
    source_sha256: object,
    snapshot: object,
) -> list[str]:
    """Validate a stale trace against an exact promoted-scene snapshot."""

    if not isinstance(snapshot, dict):
        return ["historical revision context snapshot is missing"]
    normalized_source = _normalized_relative(source_rel)
    errors = _snapshot_identity_errors(scene_id, normalized_source, source_sha256, snapshot)
    proof = _historical_source_proof(
        root,
        scene_id,
        root / normalized_source,
        require_current=False,
    )
    if proof is None:
        errors.append("historical revision source promotion is not valid")
        return errors
    errors.extend(_snapshot_proof_errors(snapshot, proof))
    errors.extend(_snapshot_file_errors(root, snapshot, proof))
    errors.extend(_snapshot_prompt_errors(root, snapshot, proof))
    return errors


def _snapshot_identity_errors(
    scene_id: str,
    source_rel: str,
    source_sha256: object,
    snapshot: dict[str, object],
) -> list[str]:
    errors: list[str] = []
    if snapshot.get("schema") != HISTORICAL_REVISION_CONTEXT_SCHEMA:
        errors.append("historical revision context schema is invalid")
    if str(snapshot.get("scene_id") or "") != scene_id:
        errors.append("historical revision context scene_id mismatch")
    unsigned = dict(snapshot)
    expected_digest = str(unsigned.pop("snapshot_sha256", "") or "").lower()
    if not expected_digest or expected_digest != _payload_sha256(unsigned):
        errors.append("historical revision context digest mismatch")
    if source_rel != _normalized_relative(snapshot.get("source_draft")):
        errors.append("historical revision source path mismatch")
    if str(source_sha256 or "").strip().lower() != str(
        snapshot.get("source_draft_sha256") or ""
    ).lower():
        errors.append("historical revision source digest mismatch")
    return errors


def _snapshot_proof_errors(
    snapshot: dict[str, object],
    proof: dict[str, object],
) -> list[str]:
    errors: list[str] = []
    for key in (
        "source_draft",
        "source_draft_sha256",
        "promotion_manifest",
        "promotion_manifest_sha256",
        "promotion_evidence_sha256",
        "promoted_candidate",
        "promoted_candidate_sha256",
        "candidate_manifest",
        "candidate_manifest_sha256",
        "source_prompt_manifest",
        "source_prompt_manifest_sha256",
    ):
        if _proof_value_matches(snapshot, proof, key):
            continue
        else:
            errors.append(f"historical revision context {key} mismatch")
    return errors


def _proof_value_matches(
    snapshot: dict[str, object],
    proof: dict[str, object],
    key: str,
) -> bool:
    expected = str(snapshot.get(key) or "").lower()
    if expected == str(proof.get(key) or "").lower():
        return True
    predecessor = proof.get("migration_predecessor")
    if not isinstance(predecessor, dict):
        return False
    migration_key = {
        "promotion_manifest_sha256": "promotion_manifest_sha256",
        "promotion_evidence_sha256": "promotion_evidence_sha256",
    }.get(key)
    return bool(migration_key and expected == str(predecessor.get(migration_key) or "").lower())


def _snapshot_file_errors(
    root: Path,
    snapshot: dict[str, object],
    proof: dict[str, object],
) -> list[str]:
    errors: list[str] = []
    archive = proof.get("context_archive")
    archive_errors = context_archive_errors(root, archive)
    if archive_errors:
        return archive_errors
    for path_key, digest_key in (
        ("context_packet", "context_packet_sha256"),
        ("context_trace", "context_trace_sha256"),
    ):
        relative = _normalized_relative(snapshot.get(path_key))
        path = _safe_project_path(root, relative)
        expected_digest = str(snapshot.get(digest_key) or "").lower()
        if path is not None and path.is_file() and _file_sha256(path) == expected_digest:
            continue
        if _archive_carries_snapshot(archive, relative, expected_digest, path_key):
            continue
        if path is None or not path.is_file():
            errors.append(f"historical revision {path_key} is missing")
        else:
            errors.append(f"historical revision {path_key} digest mismatch")
    return errors


def _archive_carries_snapshot(
    archive: object,
    snapshot_path: str,
    snapshot_digest: str,
    path_key: str,
) -> bool:
    if not isinstance(archive, dict):
        return False
    packet = path_key == "context_packet"
    archived_path_key = "archived_context_packet" if packet else "archived_context_trace"
    source_path_key = "source_context_packet" if packet else "source_context_trace"
    digest_key = "context_packet_sha256" if packet else "context_trace_sha256"
    valid_paths = {
        _normalized_relative(archive.get(archived_path_key)),
        _normalized_relative(archive.get(source_path_key)),
    }
    return snapshot_path in valid_paths and snapshot_digest == str(archive.get(digest_key) or "").lower()


def _snapshot_prompt_errors(
    root: Path,
    snapshot: dict[str, object],
    proof: dict[str, object],
) -> list[str]:
    errors: list[str] = []
    prompt = _read_json(root / str(proof["source_prompt_manifest"]))
    archive = proof.get("context_archive")
    if not isinstance(archive, dict):
        return ["historical revision context archive is missing"]
    if _normalized_relative(prompt.get("context")) != _normalized_relative(archive.get("source_context_packet")):
        errors.append("source prompt historical context packet mismatch")
    if _normalized_relative(prompt.get("context_trace")) != _normalized_relative(archive.get("source_context_trace")):
        errors.append("source prompt historical context trace mismatch")
    for snapshot_key, archived_key, source_key in (
        ("context_packet", "archived_context_packet", "source_context_packet"),
        ("context_trace", "archived_context_trace", "source_context_trace"),
    ):
        value = _normalized_relative(snapshot.get(snapshot_key))
        if value not in {
            _normalized_relative(archive.get(archived_key)),
            _normalized_relative(archive.get(source_key)),
        }:
            errors.append(f"historical revision {snapshot_key} is not carried by archive")
    return errors


def _historical_source_proof(
    root: Path,
    scene_id: str,
    source_path: Path,
    *,
    require_current: bool,
) -> dict[str, object] | None:
    root = root.resolve()
    validation = validate_historical_promotion(root, scene_id)
    if not validation.passed or (require_current and not validation.current):
        return None
    if validation.draft_path is None or validation.candidate_path is None:
        return None
    identity = _historical_source_identity(
        root, source_path, validation.draft_path, validation.candidate_path
    )
    if identity is None:
        return None
    source, source_rel, candidate_rel = identity
    promotion_path = root / "drafts" / "promotions" / f"{scene_id}_promotion.json"
    promotion = _read_json(promotion_path)
    evidence = promotion.get("historical_evidence")
    if not isinstance(evidence, dict):
        return None
    source_sha = _file_sha256(source) if source.is_file() else ""
    if source_sha != str(evidence.get("draft_sha256") or "").lower():
        return None
    candidate_path = validation.candidate_path.resolve()
    candidate_manifest_path = candidate_path.with_suffix(".json")
    candidate_manifest = _read_json(candidate_manifest_path)
    prompt_path = _candidate_prompt_path(root, candidate_path, candidate_manifest)
    required = (promotion_path, candidate_path, candidate_manifest_path, prompt_path)
    if prompt_path is None or not all(path.is_file() for path in required):
        return None
    return {
        "source_draft": source_rel,
        "source_draft_sha256": source_sha,
        "promotion_manifest": promotion_path.relative_to(root).as_posix(),
        "promotion_manifest_sha256": _file_sha256(promotion_path),
        "promotion_evidence_sha256": str(evidence.get("evidence_sha256") or "").lower(),
        "promoted_candidate": candidate_rel,
        "promoted_candidate_sha256": _file_sha256(candidate_path),
        "candidate_manifest": candidate_manifest_path.relative_to(root).as_posix(),
        "candidate_manifest_sha256": _file_sha256(candidate_manifest_path),
        "source_prompt_manifest": prompt_path.relative_to(root).as_posix(),
        "source_prompt_manifest_sha256": _file_sha256(prompt_path),
        "context_archive": evidence.get("context_archive"),
        "migration_predecessor": evidence.get("migration_predecessor"),
    }


def _historical_source_identity(
    root: Path,
    source_path: Path,
    draft_path: Path,
    candidate_path: Path,
) -> tuple[Path, str, str] | None:
    try:
        source = source_path.resolve()
        if source != draft_path.resolve():
            return None
        return (
            source,
            source.relative_to(root).as_posix(),
            candidate_path.resolve().relative_to(root).as_posix(),
        )
    except ValueError:
        return None


def _candidate_prompt_path(
    root: Path,
    candidate_path: Path,
    candidate_manifest: dict[str, object],
) -> Path | None:
    prompt_rel = _normalized_relative(candidate_manifest.get("prompt_manifest"))
    if not prompt_rel:
        try:
            prompt_rel = candidate_path.with_suffix(".prompt.json").relative_to(root).as_posix()
        except ValueError:
            return None
    return _safe_project_path(root, prompt_rel)


def _normalized_relative(value: object) -> str:
    return str(value or "").replace("\\", "/").strip()


def _safe_project_path(root: Path, relative: str) -> Path | None:
    candidate = Path(relative)
    if not relative or candidate.is_absolute():
        return None
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    return resolved


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
    "HISTORICAL_REVISION_CONTEXT_SCHEMA",
    "build_historical_revision_context_snapshot",
    "historical_revision_context_errors",
    "historical_revision_reading_paths",
    "historical_revision_source_paths",
]
