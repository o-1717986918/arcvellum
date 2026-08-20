"""Controlled author, work, and source transactions for Style Atelier."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import threading
from typing import Any
import uuid

from literary_engineering_studio_engine.public.literary import (
    create_author_project,
    create_author_work,
    ensure_style_library,
    import_work_source,
)
from literary_engineering_studio_engine.public.literary import (
    source_content_digest,
)

from .contracts import RightsMode, SourceMediaType


_IDENTITY_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
_SOURCE_SUFFIXES = {SourceMediaType.TEXT: ".txt", SourceMediaType.MARKDOWN: ".md"}
_MAX_SOURCE_CHARACTERS = 5_000_000
_WRITE_LOCK = threading.RLock()


class StyleTransactionError(ValueError):
    code = "style_transaction_invalid"


class StyleIdentityConflictError(StyleTransactionError):
    code = "style_identity_conflict"


class StyleRightsRequiredError(StyleTransactionError):
    code = "style_rights_required"


class StyleSourceDuplicateError(StyleTransactionError):
    code = "style_source_duplicate"

    def __init__(self, message: str, *, existing: dict[str, str]):
        super().__init__(message)
        self.existing = existing


class StyleAuthoringService:
    def create_author(
        self,
        library_root: Path | None,
        *,
        author_id: str,
        name: str,
        rights_mode: str,
        rights_declaration: str,
    ) -> dict[str, object]:
        stable_id = _stable_identity(author_id, "author_id")
        mode, declaration = _rights(rights_mode, rights_declaration)
        library = ensure_style_library(library_root)
        target = library / "authors" / stable_id / "author.json"
        with _WRITE_LOCK:
            _require_inside(library, target)
            if target.exists():
                raise StyleIdentityConflictError(f"style author already exists: {stable_id}")
            receipt, prepared = _start_receipt(
                library,
                operation="create-author",
                subject={"author_id": stable_id},
                evidence={"rights_mode": mode.value, "rights_declaration": declaration},
            )
            try:
                result = create_author_project(
                    library,
                    name=name.strip() or stable_id,
                    author_id=stable_id,
                    mode=mode.value,
                    source_note=declaration,
                )
            except Exception as exc:
                _fail_receipt(receipt, prepared, exc)
                raise
            return _commit_receipt(receipt, prepared, subject={"author_id": result.author_id})

    def create_work(
        self,
        library_root: Path | None,
        *,
        author_id: str,
        work_id: str,
        title: str,
        year: str = "",
        notes: str = "",
    ) -> dict[str, object]:
        stable_author = _stable_identity(author_id, "author_id")
        stable_work = _stable_identity(work_id, "work_id")
        library = ensure_style_library(library_root)
        target = library / "authors" / stable_author / "works" / stable_work / "work.json"
        with _WRITE_LOCK:
            _require_inside(library, target)
            if target.exists():
                raise StyleIdentityConflictError(f"style work already exists: {stable_author}/{stable_work}")
            receipt, prepared = _start_receipt(
                library,
                operation="create-work",
                subject={"author_id": stable_author, "work_id": stable_work},
                evidence={},
            )
            try:
                result = create_author_work(
                    library,
                    author_id=stable_author,
                    title=title.strip() or stable_work,
                    work_id=stable_work,
                    year=year.strip(),
                    notes=notes.strip(),
                )
            except Exception as exc:
                _fail_receipt(receipt, prepared, exc)
                raise
            return _commit_receipt(
                receipt,
                prepared,
                subject={"author_id": result.author_id, "work_id": result.work_id},
            )

    def import_source(
        self,
        library_root: Path | None,
        *,
        author_id: str,
        work_id: str,
        filename: str,
        media_type: str,
        content: str,
        rights_mode: str,
        rights_declaration: str,
    ) -> dict[str, object]:
        stable_author = _stable_identity(author_id, "author_id")
        stable_work = _stable_identity(work_id, "work_id")
        mode, declaration = _rights(rights_mode, rights_declaration)
        resolved_media = _media_type(media_type)
        body = _source_body(content)
        content_sha = source_content_digest(body)
        library = ensure_style_library(library_root)
        with _WRITE_LOCK:
            duplicate = _find_duplicate(library, content_sha)
            if duplicate:
                raise StyleSourceDuplicateError(
                    "the same normalized source content already exists",
                    existing=duplicate,
                )
            safe_filename = _source_filename(filename, resolved_media, content_sha)
            evidence: dict[str, object] = {
                "content_sha256": content_sha,
                "media_type": resolved_media.value,
                "rights_mode": mode.value,
                "rights_declaration": declaration,
            }
            receipt, prepared = _start_receipt(
                library,
                operation="import-source",
                subject={"author_id": stable_author, "work_id": stable_work},
                evidence=evidence,
            )
            try:
                result = import_work_source(
                    library,
                    author_id=stable_author,
                    work_id=stable_work,
                    text=body,
                    filename=safe_filename,
                    chunk_chars=4000,
                )
                subject, evidence = _record_source_manifest(
                    result,
                    filename=filename,
                    media_type=resolved_media,
                    content_sha=content_sha,
                    rights_mode=mode,
                    rights_declaration=declaration,
                    evidence=evidence,
                )
            except Exception as exc:
                _fail_receipt(receipt, prepared, exc)
                raise
            return _commit_receipt(
                receipt,
                prepared,
                subject=subject,
                evidence=evidence,
            )


def _stable_identity(value: str, field: str) -> str:
    stable = value.strip()
    if not _IDENTITY_RE.fullmatch(stable):
        raise StyleTransactionError(f"{field} must match {_IDENTITY_RE.pattern}")
    return stable


def _record_source_manifest(
    result: Any,
    *,
    filename: str,
    media_type: SourceMediaType,
    content_sha: str,
    rights_mode: RightsMode,
    rights_declaration: str,
    evidence: dict[str, object],
) -> tuple[dict[str, str], dict[str, object]]:
    manifest = _read_json(result.manifest_path)
    manifest.update(
        {
            "schema": "arcvellum/style-source/v1",
            "original_filename": _display_filename(filename, media_type),
            "media_type": media_type.value,
            "content_sha256": content_sha,
            "rights": {
                "mode": rights_mode.value,
                "declaration": rights_declaration,
            },
        }
    )
    _write_json(result.manifest_path, manifest)
    updated_evidence = {
        **evidence,
        "character_count": result.char_count,
        "chunk_count": result.chunk_count,
    }
    return {
        "author_id": result.author_id,
        "work_id": result.work_id,
        "source_id": result.source_id,
    }, updated_evidence


def _start_receipt(
    library: Path,
    *,
    operation: str,
    subject: dict[str, str],
    evidence: dict[str, object],
) -> tuple[Path, dict[str, object]]:
    transaction_id = f"style-{uuid.uuid4().hex}"
    payload: dict[str, object] = {
        "schema": "arcvellum/style-author-transaction/v1",
        "version": 1,
        "transaction_id": transaction_id,
        "operation": operation,
        "status": "prepared",
        "subject": subject,
        "evidence": evidence,
        "source": "studio-owner-transaction",
        "created_at": _now(),
    }
    receipt = library / "transactions" / transaction_id / "receipt.json"
    _require_inside(library, receipt)
    receipt.parent.mkdir(parents=True, exist_ok=False)
    _write_json(receipt, payload)
    return receipt, payload


def _commit_receipt(
    receipt: Path,
    prepared: dict[str, object],
    *,
    subject: dict[str, str],
    evidence: dict[str, object] | None = None,
) -> dict[str, object]:
    payload = {
        **prepared,
        "status": "committed",
        "subject": subject,
        "evidence": evidence if evidence is not None else prepared["evidence"],
        "committed_at": _now(),
    }
    _write_json(receipt, payload)
    return payload


def _fail_receipt(receipt: Path, prepared: dict[str, object], exc: Exception) -> None:
    _write_json(
        receipt,
        {
            **prepared,
            "status": "failed",
            "failed_at": _now(),
            "error_type": type(exc).__name__,
        },
    )


def _rights(mode: str, declaration: str) -> tuple[RightsMode, str]:
    try:
        resolved = RightsMode(mode.strip())
    except ValueError as exc:
        allowed = ", ".join(item.value for item in RightsMode)
        raise StyleRightsRequiredError(f"rights_mode must be one of: {allowed}") from exc
    text = declaration.strip()
    if len(text) < 12:
        raise StyleRightsRequiredError("rights_declaration must contain at least 12 characters")
    return resolved, text


def _media_type(value: str) -> SourceMediaType:
    try:
        return SourceMediaType(value.strip())
    except ValueError as exc:
        allowed = ", ".join(item.value for item in SourceMediaType)
        raise StyleTransactionError(f"media_type must be one of: {allowed}") from exc


def _source_body(content: str) -> str:
    body = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not body:
        raise StyleTransactionError("source content is required")
    if "\ufffd" in body or "\x00" in body:
        raise StyleTransactionError(
            "source content contains invalid replacement (U+FFFD) or NUL characters; "
            "convert the text to UTF-8 and remove NUL padding before importing"
        )
    if len(body) > _MAX_SOURCE_CHARACTERS:
        raise StyleTransactionError(f"source content exceeds {_MAX_SOURCE_CHARACTERS} characters")
    return body


def _source_filename(filename: str, media_type: SourceMediaType, content_sha: str) -> str:
    display = _display_filename(filename, media_type)
    stem = re.sub(r"[^a-zA-Z0-9-]+", "-", Path(display).stem).strip("-").lower() or "source"
    return f"{stem[:40]}-{content_sha[:12]}{_SOURCE_SUFFIXES[media_type]}"


def _display_filename(filename: str, media_type: SourceMediaType) -> str:
    value = filename.strip() or f"source{_SOURCE_SUFFIXES[media_type]}"
    if Path(value).name != value or "/" in value or "\\" in value:
        raise StyleTransactionError("source filename must not contain a path")
    if len(value) > 180:
        raise StyleTransactionError("source filename is too long")
    suffix = Path(value).suffix.lower()
    if suffix not in {".txt", ".md", ".markdown"}:
        raise StyleTransactionError("source filename must use .txt, .md, or .markdown")
    return value


def _find_duplicate(library: Path, content_sha: str) -> dict[str, str]:
    for path in sorted((library / "authors").glob("*/works/*/sources/*.source.json")):
        payload = _read_json(path)
        existing_sha = str(payload.get("content_sha256") or "")
        if not existing_sha:
            normalized = _managed_file(path.parents[1], str(payload.get("normalized") or ""))
            existing_sha = hashlib.sha256(normalized.read_text(encoding="utf-8").strip().encode("utf-8")).hexdigest() if normalized else ""
        if existing_sha == content_sha:
            return {
                "author_id": str(payload.get("author_id") or ""),
                "work_id": str(payload.get("work_id") or ""),
                "source_id": str(payload.get("source_id") or ""),
            }
    return {}


def _managed_file(root: Path, relative: str) -> Path | None:
    if not relative:
        return None
    target = (root / relative).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return None
    return target if target.is_file() else None


def _require_inside(root: Path, path: Path) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise StyleTransactionError("style transaction path escapes the library root") from exc


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
