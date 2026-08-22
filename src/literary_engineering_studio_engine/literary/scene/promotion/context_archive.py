"""Content-addressed scene context archives created at prose promotion."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ....foundation.atomic_io import atomic_write_text


CONTEXT_ARCHIVE_SCHEMA = "arcvellum/scene-context-archive/v1"


def context_archive_output_paths(
    root: Path,
    scene_id: str,
    candidate_path: Path,
) -> tuple[str, ...]:
    """Predict the deterministic files written by formal promotion."""

    plan = context_archive_plan(root, scene_id, candidate_path)
    if not plan:
        return ()
    return (
        str(plan["archived_context_packet"]),
        str(plan["archived_context_trace"]),
        str(plan["archive_manifest"]),
    )


def context_archive_plan(
    root: Path,
    scene_id: str,
    candidate_path: Path,
    *,
    packet_source: Path | None = None,
    trace_source: Path | None = None,
) -> dict[str, object]:
    """Describe an archive without mutating the work project."""

    root = root.resolve()
    candidate = candidate_path.resolve()
    candidate_manifest = _read_json(candidate.with_suffix(".json"))
    prompt_path = _candidate_prompt_path(root, candidate, candidate_manifest)
    if prompt_path is None or not prompt_path.is_file():
        return {}
    prompt = _read_json(prompt_path)
    packet_rel = _normalized_relative(prompt.get("context"))
    trace_rel = _normalized_relative(prompt.get("context_trace"))
    declared_packet = _safe_project_path(root, packet_rel)
    declared_trace = _safe_project_path(root, trace_rel)
    packet = packet_source.resolve() if packet_source is not None else declared_packet
    trace = trace_source.resolve() if trace_source is not None else declared_trace
    if packet is None or trace is None or not packet.is_file() or not trace.is_file():
        return {}
    packet_bytes = packet.read_bytes()
    trace_bytes = trace.read_bytes()
    packet_sha = _bytes_sha256(packet_bytes)
    trace_sha = _bytes_sha256(trace_bytes)
    identity = {
        "schema": CONTEXT_ARCHIVE_SCHEMA,
        "scene_id": scene_id,
        "context_packet_sha256": packet_sha,
        "context_trace_sha256": trace_sha,
    }
    archive_id = _payload_sha256(identity)
    archive_dir = Path("memory") / "context_history" / scene_id / archive_id
    archive: dict[str, object] = {
        **identity,
        "archive_id": archive_id,
        "source_prompt_manifest": _relative_path(root, prompt_path),
        "source_prompt_manifest_sha256": _file_sha256(prompt_path),
        "source_context_packet": packet_rel,
        "source_context_trace": trace_rel,
        "archived_context_packet": (archive_dir / "context.md").as_posix(),
        "archived_context_trace": (archive_dir / "context.trace.json").as_posix(),
        "archive_manifest": (archive_dir / "archive.json").as_posix(),
    }
    archive["archive_identity_sha256"] = _payload_sha256(archive)
    archive["_packet_text"] = packet_bytes.decode("utf-8")
    archive["_trace_text"] = trace_bytes.decode("utf-8")
    return archive


def seal_context_archive(
    root: Path,
    scene_id: str,
    candidate_path: Path,
    *,
    packet_source: Path | None = None,
    trace_source: Path | None = None,
) -> dict[str, object]:
    """Write or verify the immutable archive for one promoted candidate."""

    root = root.resolve()
    plan = context_archive_plan(
        root,
        scene_id,
        candidate_path,
        packet_source=packet_source,
        trace_source=trace_source,
    )
    if not plan:
        raise ValueError("formal promotion requires candidate-bound context packet and trace")
    manifest_path = root / str(plan["archive_manifest"])
    if manifest_path.is_file():
        existing = _read_json(manifest_path)
        errors = context_archive_errors(root, existing)
        identity_keys = (
            "schema",
            "scene_id",
            "archive_id",
            "context_packet_sha256",
            "context_trace_sha256",
            "archived_context_packet",
            "archived_context_trace",
            "archive_manifest",
        )
        if not errors and all(existing.get(key) == plan.get(key) for key in identity_keys):
            return existing
        if errors:
            raise ValueError("invalid existing immutable context archive: " + "; ".join(errors))
        raise ValueError(f"refusing to overwrite immutable context archive: {manifest_path}")
    packet_text = str(plan.pop("_packet_text"))
    trace_text = str(plan.pop("_trace_text"))
    entries = (
        (root / str(plan["archived_context_packet"]), packet_text),
        (root / str(plan["archived_context_trace"]), trace_text),
        (manifest_path, json.dumps(plan, ensure_ascii=False, indent=2) + "\n"),
    )
    for path, text in entries:
        _write_immutable(path, text)
    errors = context_archive_errors(root, plan)
    if errors:
        raise ValueError("invalid sealed context archive: " + "; ".join(errors))
    return plan


def context_archive_errors(root: Path, archive: object) -> list[str]:
    """Validate archive identity, paths, source prompt, and immutable bytes."""

    if not isinstance(archive, dict):
        return ["historical context archive is missing"]
    errors = _archive_identity_errors(archive)
    _validate_archive_file(root, archive, "archived_context_packet", "context_packet_sha256", errors)
    _validate_archive_file(root, archive, "archived_context_trace", "context_trace_sha256", errors)
    errors.extend(_archive_manifest_errors(root, archive))
    errors.extend(_archive_prompt_errors(root, archive))
    return errors


def _archive_identity_errors(archive: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if archive.get("schema") != CONTEXT_ARCHIVE_SCHEMA:
        errors.append("historical context archive schema is invalid")
    scene_id = str(archive.get("scene_id") or "").strip()
    archive_id = str(archive.get("archive_id") or "").strip().lower()
    expected_id = _payload_sha256(
        {
            "schema": CONTEXT_ARCHIVE_SCHEMA,
            "scene_id": scene_id,
            "context_packet_sha256": str(archive.get("context_packet_sha256") or "").lower(),
            "context_trace_sha256": str(archive.get("context_trace_sha256") or "").lower(),
        }
    )
    if not scene_id or archive_id != expected_id:
        errors.append("historical context archive id mismatch")
    unsigned = dict(archive)
    expected_identity = str(unsigned.pop("archive_identity_sha256", "") or "").lower()
    if not expected_identity or expected_identity != _payload_sha256(unsigned):
        errors.append("historical context archive identity digest mismatch")
    return errors


def _archive_manifest_errors(root: Path, archive: dict[str, object]) -> list[str]:
    manifest = _safe_project_path(root, archive.get("archive_manifest"))
    if manifest is None or not manifest.is_file():
        return ["historical context archive manifest is missing"]
    return [] if _read_json(manifest) == archive else ["historical context archive manifest mismatch"]


def _archive_prompt_errors(root: Path, archive: dict[str, object]) -> list[str]:
    prompt = _safe_project_path(root, archive.get("source_prompt_manifest"))
    if prompt is None or not prompt.is_file():
        return ["historical context source prompt is missing"]
    if _file_sha256(prompt) != str(archive.get("source_prompt_manifest_sha256") or "").lower():
        return ["historical context source prompt digest mismatch"]
    prompt_payload = _read_json(prompt)
    errors: list[str] = []
    if _normalized_relative(prompt_payload.get("context")) != _normalized_relative(archive.get("source_context_packet")):
        errors.append("historical context source packet path mismatch")
    if _normalized_relative(prompt_payload.get("context_trace")) != _normalized_relative(archive.get("source_context_trace")):
        errors.append("historical context source trace path mismatch")
    return errors


def archived_context_paths(archive: object) -> tuple[str, ...]:
    if not isinstance(archive, dict):
        return ()
    return tuple(
        value
        for value in (
            _normalized_relative(archive.get("archived_context_packet")),
            _normalized_relative(archive.get("archived_context_trace")),
        )
        if value
    )


def _validate_archive_file(
    root: Path,
    archive: dict[str, object],
    path_key: str,
    digest_key: str,
    errors: list[str],
) -> None:
    path = _safe_project_path(root, archive.get(path_key))
    if path is None or not path.is_file():
        errors.append(f"historical context {path_key} is missing")
    elif _file_sha256(path) != str(archive.get(digest_key) or "").lower():
        errors.append(f"historical context {path_key} digest mismatch")


def _write_immutable(path: Path, text: str) -> None:
    encoded = text.encode("utf-8")
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError(f"refusing to overwrite immutable context archive: {path}")
        return
    atomic_write_text(path, text)


def _candidate_prompt_path(
    root: Path,
    candidate_path: Path,
    candidate_manifest: dict[str, object],
) -> Path | None:
    relative = _normalized_relative(candidate_manifest.get("prompt_manifest"))
    if not relative:
        relative = _relative_path(root, candidate_path.with_suffix(".prompt.json"))
    return _safe_project_path(root, relative)


def _safe_project_path(root: Path, value: object) -> Path | None:
    relative = _normalized_relative(value)
    candidate = Path(relative)
    if not relative or candidate.is_absolute():
        return None
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    return resolved


def _relative_path(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _normalized_relative(value: object) -> str:
    return str(value or "").replace("\\", "/").strip()


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
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


__all__ = [
    "CONTEXT_ARCHIVE_SCHEMA",
    "archived_context_paths",
    "context_archive_errors",
    "context_archive_output_paths",
    "context_archive_plan",
    "seal_context_archive",
]
