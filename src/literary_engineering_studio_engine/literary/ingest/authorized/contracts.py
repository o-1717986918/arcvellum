"""Truthful, serializable contracts for authorized literary sources."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
from pathlib import PurePosixPath
import re
from typing import Any, Iterable, Mapping


AUTHORIZED_WORK_SCHEMA = "arcvellum/authorized-literary-source/v1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_PLACEHOLDER_RE = re.compile(
    r"(?:your|example|sample|placeholder|changeme|replace|dummy|mock|test|fake|"
    r"todo|xxx|redacted|pending|待补|占位)",
    re.IGNORECASE,
)


class RightsBasis(str, Enum):
    AUTHOR_PERMISSION = "author_permission"
    PUBLISHER_LICENSE = "publisher_license"
    USER_OWNED = "user_owned"
    PUBLIC_DOMAIN = "public_domain"
    USER_ATTESTED_PRIVATE_RESEARCH = "user_attested_private_research"


class DistributionScope(str, Enum):
    LOCAL_ANALYSIS = "local_analysis"
    DESKTOP_DEMO_BUNDLE = "desktop_demo_bundle"
    GITHUB_RELEASE_ASSET = "github_release_asset"
    PUBLIC_DISTRIBUTION = "public_distribution"


@dataclass(frozen=True)
class AuthorizedSourceFile:
    source_id: str
    filename: str
    media_type: str
    sha256: str
    byte_size: int

    @classmethod
    def from_record(cls, payload: Mapping[str, Any]) -> "AuthorizedSourceFile":
        return cls(
            source_id=str(payload.get("source_id") or "").strip(),
            filename=str(payload.get("filename") or "").strip().replace("\\", "/"),
            media_type=str(payload.get("media_type") or "").strip(),
            sha256=str(payload.get("sha256") or "").strip().lower(),
            byte_size=_integer(payload.get("byte_size"), default=-1),
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "filename": self.filename,
            "media_type": self.media_type,
            "sha256": self.sha256,
            "byte_size": self.byte_size,
        }

    def validation_errors(self) -> list[str]:
        errors: list[str] = []
        if not self.source_id:
            errors.append("source file requires source_id")
        if not _safe_relative_path(self.filename):
            errors.append(f"source file path must be a safe relative path: {self.filename or '<empty>'}")
        if not self.media_type:
            errors.append(f"source file {self.source_id or '<unknown>'} requires media_type")
        if not _SHA256_RE.fullmatch(self.sha256):
            errors.append(f"source file {self.source_id or '<unknown>'} requires a lowercase SHA-256")
        if self.byte_size <= 0:
            errors.append(f"source file {self.source_id or '<unknown>'} requires a positive byte_size")
        return errors


@dataclass(frozen=True)
class AuthorizationGrant:
    basis: RightsBasis
    rights_holder: str
    licensee: str
    declaration: str
    evidence_ref: str
    evidence_sha256: str
    scopes: tuple[DistributionScope, ...]
    issued_on: str = ""
    expires_on: str = ""
    notes: str = ""

    @classmethod
    def from_record(cls, payload: Mapping[str, Any]) -> "AuthorizationGrant":
        return cls(
            basis=_enum_value(RightsBasis, payload.get("basis"), "authorization basis"),
            rights_holder=str(payload.get("rights_holder") or "").strip(),
            licensee=str(payload.get("licensee") or "").strip(),
            declaration=str(payload.get("declaration") or "").strip(),
            evidence_ref=str(payload.get("evidence_ref") or "").strip().replace("\\", "/"),
            evidence_sha256=str(payload.get("evidence_sha256") or "").strip().lower(),
            scopes=tuple(
                _enum_value(DistributionScope, item, "distribution scope")
                for item in _list_value(payload.get("scopes"))
            ),
            issued_on=str(payload.get("issued_on") or "").strip(),
            expires_on=str(payload.get("expires_on") or "").strip(),
            notes=str(payload.get("notes") or "").strip(),
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "basis": self.basis.value,
            "rights_holder": self.rights_holder,
            "licensee": self.licensee,
            "declaration": self.declaration,
            "evidence_ref": self.evidence_ref,
            "evidence_sha256": self.evidence_sha256,
            "scopes": [item.value for item in self.scopes],
            "issued_on": self.issued_on,
            "expires_on": self.expires_on,
            "notes": self.notes,
        }

    def validation_errors(
        self,
        *,
        required_scopes: Iterable[DistributionScope] = (),
    ) -> list[str]:
        errors: list[str] = []
        private_research = self.basis is RightsBasis.USER_ATTESTED_PRIVATE_RESEARCH
        if not private_research and not self.rights_holder:
            errors.append("authorization requires rights_holder")
        if not private_research and not self.licensee:
            errors.append("authorization requires licensee")
        if len(self.declaration) < 12 or _PLACEHOLDER_RE.search(self.declaration):
            errors.append("authorization declaration is missing or still contains a placeholder")
        errors.extend(self._evidence_errors(private_research=private_research))
        if not self.scopes:
            errors.append("authorization requires at least one distribution scope")
        if len(set(self.scopes)) != len(self.scopes):
            errors.append("authorization scopes must not contain duplicates")
        missing = sorted(set(required_scopes).difference(self.scopes), key=lambda item: item.value)
        if missing:
            errors.append(
                "authorization does not cover required scope(s): "
                + ", ".join(item.value for item in missing)
            )
        if private_research and set(self.scopes) != {DistributionScope.LOCAL_ANALYSIS}:
            errors.append("private research attestation is restricted to local_analysis")
        return errors

    def _evidence_errors(self, *, private_research: bool) -> list[str]:
        if private_research and not self.evidence_ref and not self.evidence_sha256:
            return []
        errors: list[str] = []
        if not _safe_relative_path(self.evidence_ref):
            errors.append("authorization evidence_ref must be a safe relative path")
        elif _PLACEHOLDER_RE.search(self.evidence_ref):
            errors.append("authorization evidence_ref still contains a placeholder")
        if not _SHA256_RE.fullmatch(self.evidence_sha256):
            errors.append("authorization evidence requires a lowercase SHA-256")
        return errors


@dataclass(frozen=True)
class AuthorizedWorkManifest:
    work_id: str
    title: str
    author: str
    edition: str
    language: str
    work_type: str
    source_files: tuple[AuthorizedSourceFile, ...]
    authorization: AuthorizationGrant
    schema: str = AUTHORIZED_WORK_SCHEMA

    @classmethod
    def from_record(cls, payload: Mapping[str, Any]) -> "AuthorizedWorkManifest":
        authorization = payload.get("authorization")
        if not isinstance(authorization, Mapping):
            raise ValueError("authorized work manifest requires an authorization object")
        raw_sources = payload.get("source_files")
        if not isinstance(raw_sources, list):
            raise ValueError("authorized work manifest requires a source_files array")
        return cls(
            schema=str(payload.get("schema") or "").strip(),
            work_id=str(payload.get("work_id") or "").strip(),
            title=str(payload.get("title") or "").strip(),
            author=str(payload.get("author") or "").strip(),
            edition=str(payload.get("edition") or "").strip(),
            language=str(payload.get("language") or "").strip(),
            work_type=str(payload.get("work_type") or "").strip(),
            source_files=tuple(
                AuthorizedSourceFile.from_record(item)
                for item in raw_sources
                if isinstance(item, Mapping)
            ),
            authorization=AuthorizationGrant.from_record(authorization),
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "work_id": self.work_id,
            "title": self.title,
            "author": self.author,
            "edition": self.edition,
            "language": self.language,
            "work_type": self.work_type,
            "source_files": [item.to_record() for item in self.source_files],
            "authorization": self.authorization.to_record(),
        }

    def validation_errors(
        self,
        *,
        required_scopes: Iterable[DistributionScope] = (),
    ) -> list[str]:
        errors: list[str] = []
        if self.schema != AUTHORIZED_WORK_SCHEMA:
            errors.append(f"unsupported authorized work schema: {self.schema or '<empty>'}")
        for field_name, value in (
            ("work_id", self.work_id),
            ("title", self.title),
            ("author", self.author),
            ("edition", self.edition),
            ("language", self.language),
            ("work_type", self.work_type),
        ):
            if not value:
                errors.append(f"authorized work manifest requires {field_name}")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", self.work_id):
            errors.append("work_id must be a lowercase slug")
        if not self.source_files:
            errors.append("authorized work manifest requires at least one source file")
        source_ids = [item.source_id for item in self.source_files]
        filenames = [item.filename.casefold() for item in self.source_files]
        if len(set(source_ids)) != len(source_ids):
            errors.append("source_id values must be unique")
        if len(set(filenames)) != len(filenames):
            errors.append("source filenames must be unique")
        for item in self.source_files:
            errors.extend(item.validation_errors())
        errors.extend(self.authorization.validation_errors(required_scopes=required_scopes))
        return errors

    def digest(self) -> str:
        import json

        serialized = json.dumps(
            self.to_record(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()


def _safe_relative_path(value: str) -> bool:
    if not value or "\x00" in value or re.match(r"^[A-Za-z]:", value):
        return False
    path = PurePosixPath(value.replace("\\", "/"))
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def _integer(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _list_value(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _enum_value(enum_type: type[Enum], value: Any, label: str):
    try:
        return enum_type(str(value or "").strip())
    except ValueError as error:
        allowed = ", ".join(item.value for item in enum_type)
        raise ValueError(f"unsupported {label}: {value!r}; expected one of {allowed}") from error
