"""Self-contained integrity checks for immutable style-version packages."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from ...style_prompt import style_prompt_quality_report
from .version_contracts import (
    COMPATIBLE_STYLE_SKILL_SCHEMA,
    STYLE_VERSION_BUILDER,
    STYLE_VERSION_SCHEMA,
)


@dataclass(frozen=True)
class _PackagePaths:
    root: Path
    manifest: Path
    compatibility: Path
    prompt: Path
    artifacts: tuple[Path, ...]


def inspect_style_version_directory(
    version_dir: Path,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Validate one immutable package without consulting current profile state."""

    paths = _package_paths(version_dir.resolve())
    manifest = _read_object(paths.manifest)
    errors: list[str] = []
    errors.extend(_manifest_contract_errors(paths, manifest))
    errors.extend(_source_evidence_errors(manifest.get("source_evidence")))
    errors.extend(_content_identity_errors(manifest))
    errors.extend(_artifact_integrity_errors(paths, manifest))
    errors.extend(_compatibility_errors(paths, manifest))
    return manifest, tuple(dict.fromkeys(errors))


def _manifest_contract_errors(
    paths: _PackagePaths,
    manifest: dict[str, Any],
) -> list[str]:
    errors = [
        f"style version manifest has invalid {field}"
        for field, expected in {
            "schema": STYLE_VERSION_SCHEMA,
            "builder": STYLE_VERSION_BUILDER,
            "review_status": "pass",
        }.items()
        if manifest.get(field) != expected
    ]
    content_hash = str(manifest.get("content_hash") or "")
    version_id = str(manifest.get("version_id") or "")
    if not _is_sha256(content_hash):
        errors.append("style version manifest has invalid content_hash")
    elif version_id != f"v1-{content_hash[:20]}":
        errors.append("style version manifest version_id is not content-addressed")
    if version_id and paths.root.name != version_id:
        errors.append("style version directory does not match version_id")
    if not str(manifest.get("style_id") or ""):
        errors.append("style version manifest style_id is missing")
    if not isinstance(manifest.get("review_evidence"), dict):
        errors.append("style version review evidence is missing")
    if not isinstance(manifest.get("prompt_quality"), dict):
        errors.append("style version prompt quality is missing")
    return errors


def _source_evidence_errors(value: object) -> list[str]:
    if not isinstance(value, list) or not value:
        return ["style version source evidence is missing"]
    errors: list[str] = []
    for index, row in enumerate(value):
        if not isinstance(row, dict) or not _source_row_complete(row):
            errors.append(f"style version source evidence row {index} is incomplete")
    return errors


def _source_row_complete(row: dict[str, object]) -> bool:
    rights = row.get("rights")
    return bool(
        str(row.get("identity") or "")
        and _is_sha256(str(row.get("content_sha256") or ""))
        and isinstance(rights, dict)
        and str(rights.get("mode") or "")
        and str(rights.get("declaration") or "")
    )


def _content_identity_errors(manifest: dict[str, Any]) -> list[str]:
    inputs = _identity_inputs(manifest)
    if inputs is None:
        return []
    source_evidence, review_evidence, prompt_quality, content_hash = inputs
    basis = _identity_basis(
        manifest,
        source_evidence,
        review_evidence,
        prompt_quality,
    )
    if _object_sha256(basis) != content_hash:
        return ["style version content hash does not match manifest evidence"]
    return []


def _identity_inputs(
    manifest: dict[str, Any],
) -> tuple[list[object], dict[str, Any], dict[str, Any], str] | None:
    source_evidence = manifest.get("source_evidence")
    review_evidence = manifest.get("review_evidence")
    prompt_quality = manifest.get("prompt_quality")
    content_hash = str(manifest.get("content_hash") or "")
    if (
        not isinstance(source_evidence, list)
        or not isinstance(review_evidence, dict)
        or not isinstance(prompt_quality, dict)
        or not _is_sha256(content_hash)
    ):
        return None
    return source_evidence, review_evidence, prompt_quality, content_hash


def _identity_basis(
    manifest: dict[str, Any],
    source_evidence: list[object],
    review_evidence: dict[str, Any],
    prompt_quality: dict[str, Any],
) -> dict[str, object]:
    return {
        "builder": str(manifest.get("builder") or ""),
        "style_id": str(manifest.get("style_id") or ""),
        "author_id": str(manifest.get("author_id") or ""),
        "profile_id": str(manifest.get("profile_id") or ""),
        "session_id": str(manifest.get("session_id") or ""),
        "session_request_digest": str(
            manifest.get("session_request_digest") or ""
        ),
        "source_evidence": source_evidence,
        "artifact_digests": {
            key: value
            for key, value in review_evidence.items()
            if key.endswith("_sha256")
        },
        "prompt_detail_chars": int(prompt_quality.get("detail_chars") or 0),
        "prompt_detail_count_unit": str(
            prompt_quality.get("detail_count_unit") or ""
        ),
    }


def _artifact_integrity_errors(
    paths: _PackagePaths,
    manifest: dict[str, Any],
) -> list[str]:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        return ["style version manifest artifacts are missing"]
    expected = {
        path.relative_to(paths.root).as_posix() for path in paths.artifacts
    }
    if set(artifacts) != expected:
        return [
            "style version manifest artifact inventory is incomplete or unexpected"
        ]
    actual = {
        path.relative_to(paths.root).as_posix()
        for path in paths.root.rglob("*")
        if path.is_file() and path != paths.manifest
    }
    if actual != expected:
        return ["style version directory contains undeclared or missing artifacts"]
    return [
        f"style version artifact is missing or stale: {relative}"
        for relative in sorted(expected)
        if not _artifact_matches(paths.root, relative, str(artifacts[relative]))
    ]


def _compatibility_errors(
    paths: _PackagePaths,
    manifest: dict[str, Any],
) -> list[str]:
    payload = _read_object(paths.compatibility)
    errors = [
        f"compatible style skill has invalid {field}"
        for field, expected in {
            "schema": COMPATIBLE_STYLE_SKILL_SCHEMA,
            "style_id": str(manifest.get("style_id") or ""),
            "version_id": str(manifest.get("version_id") or ""),
            "content_hash": str(manifest.get("content_hash") or ""),
            "review_status": "pass",
        }.items()
        if payload.get(field) != expected
    ]
    quality = _prompt_quality(paths.prompt)
    if not quality.get("length_ok") or not quality.get("structure_ok"):
        errors.append("compatible style skill prompt fails quality gates")
    expected_quality = manifest.get("prompt_quality")
    if isinstance(expected_quality, dict) and not _quality_matches(
        expected_quality,
        quality,
    ):
        errors.append("style version prompt quality does not match packaged prompt")
    return errors


def _quality_matches(
    expected: dict[str, Any],
    actual: dict[str, object],
) -> bool:
    return (
        int(expected.get("detail_chars") or 0)
        == int(actual.get("detail_chars") or 0)
        and str(expected.get("detail_count_unit") or "")
        == str(actual.get("detail_count_unit") or "")
    )


def _package_paths(root: Path) -> _PackagePaths:
    evaluation = root / "evaluation_results" / "formal"
    artifacts = (
        root / "style_skill.json",
        root / "prompt.md",
        root / "style-profile.md",
        root / "style_metrics.json",
        root / "style_prompt.agent.json",
        root / "corpus_manifest.yaml",
        root / "STYLE.md",
        evaluation / "style_eval_current.json",
        evaluation / "style_eval_current.md",
        evaluation / "style_semantic_review.json",
        evaluation / "style_semantic_review.md",
    )
    return _PackagePaths(
        root,
        root / "style_version.json",
        root / "style_skill.json",
        root / "prompt.md",
        artifacts,
    )


def _artifact_matches(root: Path, relative: str, expected: str) -> bool:
    path = _safe_path(root, relative)
    return path.is_file() and _sha256(path) == expected


def _safe_path(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        return root / ".invalid-artifact-path"
    path = (root / relative).resolve()
    return path if path.is_relative_to(root) else root / ".escaped-artifact-path"


def _prompt_quality(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    return style_prompt_quality_report(
        path.read_text(encoding="utf-8", errors="ignore")
    )


def _read_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _object_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )
