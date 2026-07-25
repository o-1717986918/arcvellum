"""Formal style-engineering sessions inside a creative work project.

The reusable style library is not a Literary Engineering work project, so the
formal Worker cannot execute a route there.  A session copies only selected,
rights-declared source evidence into a controlled project-local workspace.
The existing ``style-engineering`` route then owns every compile, Agent, review,
and build transition.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Iterable
from uuid import uuid4


STYLE_SESSION_SCHEMA = "arcvellum/style-engineering-session/v1"
_IDENTITY_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")


class StyleSessionError(ValueError):
    code = "style_session_invalid"


class StyleSessionConflictError(StyleSessionError):
    code = "style_session_conflict"


class StyleSessionSourceError(StyleSessionError):
    code = "style_session_source_invalid"


@dataclass(frozen=True)
class StyleSourceSelection:
    work_id: str
    source_id: str


@dataclass(frozen=True)
class StyleSessionResult:
    author_id: str
    profile_id: str
    profile_dir: Path
    manifest_path: Path
    request_digest: str
    created: bool


@dataclass(frozen=True)
class _ResolvedSource:
    work_id: str
    source_id: str
    content: str
    content_sha256: str
    rights_mode: str
    rights_declaration: str

    @property
    def identity(self) -> str:
        return f"{self.work_id}/{self.source_id}"


def prepare_style_engineering_session(
    project_root: Path,
    library_root: Path,
    *,
    author_id: str,
    profile_id: str,
    display_name: str,
    training_sources: Iterable[StyleSourceSelection],
    holdout_sources: Iterable[StyleSourceSelection],
) -> StyleSessionResult:
    """Create one immutable source selection for the formal style route."""

    project = project_root.expanduser().resolve()
    library = library_root.expanduser().resolve()
    if not (project / "project.yaml").is_file():
        raise StyleSessionError("project_root must contain project.yaml")
    if not (library / "library.json").is_file():
        raise StyleSessionError("style library is not initialized")

    stable_author = _stable_id(author_id, "author_id")
    stable_profile = _stable_id(profile_id, "profile_id")
    training = tuple(_resolve_sources(library, stable_author, training_sources))
    holdout = tuple(_resolve_sources(library, stable_author, holdout_sources))
    if not training:
        raise StyleSessionSourceError("at least one training source is required")
    if not holdout:
        raise StyleSessionSourceError("at least one holdout source is required")
    overlap = sorted({item.identity for item in training} & {item.identity for item in holdout})
    if overlap:
        raise StyleSessionSourceError(
            "training and holdout sources must be disjoint: " + ", ".join(overlap)
        )

    name = display_name.strip() or f"{stable_author}-{stable_profile}"
    request_digest = _request_digest(stable_author, stable_profile, name, training, holdout)
    profile_dir = project / "style" / "atelier" / stable_author / stable_profile
    _require_inside(project, profile_dir)
    if profile_dir.exists():
        return _existing_session_result(
            profile_dir,
            stable_author,
            stable_profile,
            request_digest,
        )
    return _create_session(
        project,
        profile_dir,
        stable_author,
        stable_profile,
        name,
        request_digest,
        training,
        holdout,
    )


def load_style_session(profile_dir: Path) -> dict[str, object]:
    path = profile_dir / "style_session.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def formal_style_profile_dirs(project_root: Path) -> tuple[Path, ...]:
    """Return project-local formal style profiles without exposing library layout."""

    root = project_root.expanduser().resolve()
    atelier = root / "style" / "atelier"
    if not atelier.is_dir():
        return ()
    profiles: list[Path] = []
    for manifest in sorted(atelier.glob("*/*/style_session.json")):
        profile = manifest.parent.resolve()
        if manifest.is_file() and profile.is_relative_to(root):
            profiles.append(profile)
    return tuple(profiles)


def style_session_source_paths(profile_dir: Path) -> tuple[Path, ...]:
    payload = load_style_session(profile_dir)
    paths: list[Path] = []
    for field in ("training_sources", "holdout_sources"):
        rows = payload.get(field)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            relative = str(row.get("path") or "")
            if not relative:
                continue
            try:
                target = _resolve_inside(profile_dir, relative)
            except StyleSessionSourceError:
                continue
            paths.append(target)
    return tuple(dict.fromkeys(paths))


def style_session_holdout_reference(profile_dir: Path) -> Path | None:
    payload = load_style_session(profile_dir)
    rows = payload.get("holdout_sources")
    if not isinstance(rows, list):
        return None
    for row in rows:
        if not isinstance(row, dict):
            continue
        relative = str(row.get("path") or "")
        if not relative:
            continue
        try:
            candidate = _resolve_inside(profile_dir, relative)
        except StyleSessionSourceError:
            continue
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate
    return None


def style_session_gate_errors(profile_dir: Path) -> list[str]:
    payload = load_style_session(profile_dir)
    if not payload:
        return ["style_session.json is missing or invalid"]
    errors: list[str] = []
    if payload.get("schema") != STYLE_SESSION_SCHEMA:
        errors.append("style session schema is invalid")
    training_ids, training_errors = _source_group_gate(profile_dir, payload, "training_sources")
    holdout_ids, holdout_errors = _source_group_gate(profile_dir, payload, "holdout_sources")
    errors.extend(training_errors)
    errors.extend(holdout_errors)
    overlap = sorted(training_ids & holdout_ids)
    if overlap:
        errors.append("training and holdout evidence overlap: " + ", ".join(overlap))
    return errors


def _resolve_sources(
    library: Path,
    author_id: str,
    selections: Iterable[StyleSourceSelection],
) -> list[_ResolvedSource]:
    results: list[_ResolvedSource] = []
    seen: set[str] = set()
    for selection in selections:
        work_id = _stable_id(selection.work_id, "work_id")
        source_id = _stable_id(selection.source_id, "source_id")
        identity = f"{work_id}/{source_id}"
        if identity in seen:
            raise StyleSessionSourceError(f"duplicate source selection: {identity}")
        seen.add(identity)
        results.append(_resolve_source(library, author_id, work_id, source_id))
    return results


def _existing_session_result(
    profile_dir: Path,
    author_id: str,
    profile_id: str,
    request_digest: str,
) -> StyleSessionResult:
    existing = load_style_session(profile_dir)
    if (
        existing.get("schema") != STYLE_SESSION_SCHEMA
        or str(existing.get("request_digest") or "") != request_digest
    ):
        raise StyleSessionConflictError(
            f"style session already exists with different source evidence: "
            f"{author_id}/{profile_id}"
        )
    return StyleSessionResult(
        author_id,
        profile_id,
        profile_dir,
        profile_dir / "style_session.json",
        request_digest,
        False,
    )


def _create_session(
    project: Path,
    profile_dir: Path,
    author_id: str,
    profile_id: str,
    display_name: str,
    request_digest: str,
    training: tuple[_ResolvedSource, ...],
    holdout: tuple[_ResolvedSource, ...],
) -> StyleSessionResult:
    profile_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = profile_dir.parent / f".{profile_id}.session-{uuid4().hex}"
    _require_inside(project, temporary)
    try:
        temporary.mkdir(parents=False, exist_ok=False)
        manifest = {
            "schema": STYLE_SESSION_SCHEMA,
            "version": 1,
            "session_id": f"{author_id}-{profile_id}",
            "author_id": author_id,
            "profile_id": profile_id,
            "display_name": display_name,
            "status": "prepared",
            "request_digest": request_digest,
            "training_sources": _materialize_sources(temporary, "corpus", training),
            "holdout_sources": _materialize_sources(
                temporary,
                "evaluation_inputs/holdout",
                holdout,
            ),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        (temporary / "style_session.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.rename(profile_dir)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return StyleSessionResult(
        author_id,
        profile_id,
        profile_dir,
        profile_dir / "style_session.json",
        request_digest,
        True,
    )


def _source_group_gate(
    profile_dir: Path,
    payload: dict[str, object],
    field: str,
) -> tuple[set[str], list[str]]:
    rows = payload.get(field)
    if not isinstance(rows, list) or not rows:
        return set(), [f"style session {field} must contain at least one source"]
    identities: set[str] = set()
    errors: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            errors.append(f"style session {field} contains a malformed source")
            continue
        identity = str(row.get("identity") or "")
        identities.add(identity)
        errors.extend(_source_row_gate(profile_dir, row))
    return identities, errors


def _source_row_gate(profile_dir: Path, row: dict[str, object]) -> list[str]:
    identity = str(row.get("identity") or "")
    relative = str(row.get("path") or "")
    rights = row.get("rights") if isinstance(row.get("rights"), dict) else {}
    errors: list[str] = []
    if not str(rights.get("mode") or "").strip() or not str(
        rights.get("declaration") or ""
    ).strip():
        errors.append(f"style source lacks rights evidence: {identity or relative}")
    try:
        source = _resolve_inside(profile_dir, relative)
    except StyleSessionSourceError as exc:
        return [*errors, str(exc)]
    if not source.is_file():
        return [*errors, f"style source file is missing: {relative}"]
    expected_sha = str(row.get("content_sha256") or "").lower()
    actual_sha = _content_sha(source.read_text(encoding="utf-8"))
    if not expected_sha or actual_sha != expected_sha:
        errors.append(f"style source digest mismatch: {relative}")
    return errors


def _resolve_source(
    library: Path,
    author_id: str,
    work_id: str,
    source_id: str,
) -> _ResolvedSource:
    identity = f"{work_id}/{source_id}"
    work_dir = library / "authors" / author_id / "works" / work_id
    manifest_path = work_dir / "sources" / f"{source_id}.source.json"
    _require_inside(library, manifest_path)
    manifest = _read_json(manifest_path)
    if not manifest or str(manifest.get("source_id") or "") != source_id:
        raise StyleSessionSourceError(f"style source does not exist or mismatches: {identity}")
    rights = manifest.get("rights") if isinstance(manifest.get("rights"), dict) else {}
    mode = str(rights.get("mode") or "").strip()
    declaration = str(rights.get("declaration") or "").strip()
    if not mode or not declaration:
        raise StyleSessionSourceError(f"style source lacks rights evidence: {identity}")
    normalized = _resolve_inside(work_dir, str(manifest.get("normalized") or ""))
    if not normalized.is_file():
        raise StyleSessionSourceError(f"normalized style source is missing: {identity}")
    content = normalized.read_text(encoding="utf-8").strip()
    actual_sha = _content_sha(content)
    expected_sha = str(manifest.get("content_sha256") or "").lower()
    if not content or not expected_sha or expected_sha != actual_sha:
        raise StyleSessionSourceError(f"style source content or digest is invalid: {identity}")
    return _ResolvedSource(
        work_id,
        source_id,
        content,
        actual_sha,
        mode,
        declaration,
    )


def _materialize_sources(
    temporary: Path,
    relative_dir: str,
    sources: tuple[_ResolvedSource, ...],
) -> list[dict[str, object]]:
    directory = temporary / Path(relative_dir)
    directory.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for index, source in enumerate(sources, start=1):
        filename = f"{index:04d}-{source.work_id}-{source.source_id}.txt"
        target = directory / filename
        target.write_text(source.content + "\n", encoding="utf-8")
        rows.append(
            {
                "identity": source.identity,
                "work_id": source.work_id,
                "source_id": source.source_id,
                "content_sha256": source.content_sha256,
                "path": target.relative_to(temporary).as_posix(),
                "rights": {
                    "mode": source.rights_mode,
                    "declaration": source.rights_declaration,
                },
            }
        )
    return rows


def _request_digest(
    author_id: str,
    profile_id: str,
    display_name: str,
    training: tuple[_ResolvedSource, ...],
    holdout: tuple[_ResolvedSource, ...],
) -> str:
    payload = {
        "author_id": author_id,
        "profile_id": profile_id,
        "display_name": display_name,
        "training": [(item.identity, item.content_sha256) for item in training],
        "holdout": [(item.identity, item.content_sha256) for item in holdout],
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _stable_id(value: str, field: str) -> str:
    stable = str(value or "").strip()
    if not _IDENTITY_RE.fullmatch(stable):
        raise StyleSessionError(f"{field} must match {_IDENTITY_RE.pattern}")
    return stable


def _resolve_inside(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise StyleSessionSourceError(f"style source path is invalid: {relative or 'missing'}")
    target = (root / Path(relative)).resolve()
    _require_inside(root, target)
    return target


def _require_inside(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise StyleSessionSourceError("style source path escapes its managed root") from exc


def _content_sha(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
