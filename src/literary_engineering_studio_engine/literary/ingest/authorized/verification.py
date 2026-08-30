"""Filesystem verification for authorized source bundles."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Iterable

from .contracts import AuthorizedWorkManifest, DistributionScope, RightsBasis


@dataclass(frozen=True)
class AuthorizedSourceVerification:
    manifest_digest: str
    verified_files: tuple[str, ...]
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def require_valid(self) -> "AuthorizedSourceVerification":
        if self.errors:
            raise ValueError("authorized source bundle is invalid: " + "; ".join(self.errors))
        return self


def verify_authorized_source_bundle(
    manifest: AuthorizedWorkManifest,
    source_root: Path | str,
    *,
    required_scopes: Iterable[DistributionScope] = (),
) -> AuthorizedSourceVerification:
    """Verify declared files without making a legal sufficiency judgment."""

    root = Path(source_root).expanduser().resolve()
    errors = manifest.validation_errors(required_scopes=required_scopes)
    verified: list[str] = []
    if not root.is_dir():
        errors.append(f"authorized source root does not exist: {root}")
        return AuthorizedSourceVerification(manifest.digest(), (), tuple(errors))

    for source in manifest.source_files:
        _verify_file(
            root,
            source.filename,
            source.byte_size,
            source.sha256,
            f"source file {source.source_id or '<unknown>'}",
            errors,
            verified,
        )
    evidence = manifest.authorization
    if evidence.basis is not RightsBasis.USER_ATTESTED_PRIVATE_RESEARCH or evidence.evidence_ref:
        _verify_file(
            root,
            evidence.evidence_ref,
            None,
            evidence.evidence_sha256,
            "authorization evidence",
            errors,
            verified,
        )
    return AuthorizedSourceVerification(
        manifest_digest=manifest.digest(),
        verified_files=tuple(verified),
        errors=tuple(dict.fromkeys(errors)),
    )


def _verify_file(
    root: Path,
    relative_path: str,
    expected_size: int | None,
    expected_hash: str,
    label: str,
    errors: list[str],
    verified: list[str],
) -> None:
    if not relative_path:
        return
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        errors.append(f"{label} resolves outside the authorized source root")
        return
    if not path.is_file():
        errors.append(f"{label} is missing: {relative_path}")
        return
    payload = path.read_bytes()
    if expected_size is not None and len(payload) != expected_size:
        errors.append(
            f"{label} byte size mismatch: expected {expected_size}, found {len(payload)}"
        )
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected_hash:
        errors.append(f"{label} SHA-256 mismatch")
        return
    verified.append(relative_path)
