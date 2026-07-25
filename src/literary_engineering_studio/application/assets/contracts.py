"""Stable Archive asset and owner-transaction contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import uuid


class EditorKind(str, Enum):
    FORM = "form"
    MARKDOWN = "markdown"
    TABLE = "table"
    YAML_ADVANCED = "yaml-advanced"


class SemanticReview(str, Enum):
    REQUIRED = "required"
    WAIVED = "waived"


@dataclass(frozen=True)
class AssetViewDefinition:
    asset_type: str
    schema_id: str
    id_field: str
    title_field: str
    editor_kind: EditorKind
    relative_directory: str
    filename_template: str
    writable_fields: tuple[str, ...]
    reference_fields: tuple[str, ...]
    supports_create: bool
    supports_promotion: bool
    supports_archive: bool
    fixed_id: str = ""


@dataclass(frozen=True)
class AssetRecord:
    asset_id: str
    asset_type: str
    local_id: str
    relative_path: str
    revision: str
    title: str
    content: str
    media_type: str


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: str
    message: str
    field: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "field": self.field,
        }


@dataclass(frozen=True)
class AssetValidation:
    valid: bool
    issues: tuple[ValidationIssue, ...]

    def as_dict(self) -> dict[str, object]:
        return {"valid": self.valid, "issues": [issue.as_dict() for issue in self.issues]}


@dataclass(frozen=True)
class OwnerOverrideTransaction:
    transaction_id: str
    asset_id: str
    asset_type: str
    base_revision: str
    patch: tuple[dict[str, object], ...]
    authority: str
    semantic_review: SemanticReview
    reason: str
    expected_impacts: tuple[str, ...]

    @classmethod
    def create(
        cls,
        *,
        asset_id: str,
        asset_type: str,
        base_revision: str,
        content: str,
        semantic_review: SemanticReview,
        reason: str,
        expected_impacts: tuple[str, ...] = (),
    ) -> "OwnerOverrideTransaction":
        return cls(
            transaction_id=f"owner-{uuid.uuid4().hex}",
            asset_id=asset_id,
            asset_type=asset_type,
            base_revision=base_revision,
            patch=({"op": "replace", "path": "/content", "value": content},),
            authority="owner",
            semantic_review=semantic_review,
            reason=reason.strip(),
            expected_impacts=expected_impacts,
        )

    def replacement_content(self) -> str:
        if len(self.patch) != 1:
            raise ValueError("owner transaction must contain exactly one content replacement")
        operation = self.patch[0]
        if operation.get("op") != "replace" or operation.get("path") != "/content":
            raise ValueError("owner transaction only supports replace /content")
        value = operation.get("value")
        if not isinstance(value, str):
            raise ValueError("owner transaction replacement content must be text")
        return value

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": "arcvellum/owner-override/v1",
            "operation": "replace",
            "transaction_id": self.transaction_id,
            "asset_id": self.asset_id,
            "asset_type": self.asset_type,
            "base_revision": self.base_revision,
            "patch": list(self.patch),
            "authority": self.authority,
            "semantic_review": self.semantic_review.value,
            "reason": self.reason,
            "expected_impacts": list(self.expected_impacts),
        }


@dataclass(frozen=True)
class OwnerAssetCreation:
    transaction_id: str
    asset_id: str
    asset_type: str
    content: str
    authority: str
    semantic_review: SemanticReview
    reason: str
    expected_impacts: tuple[str, ...]

    @classmethod
    def create(
        cls,
        *,
        asset_id: str,
        asset_type: str,
        content: str,
        semantic_review: SemanticReview,
        reason: str,
        expected_impacts: tuple[str, ...] = (),
    ) -> "OwnerAssetCreation":
        return cls(
            transaction_id=f"owner-create-{uuid.uuid4().hex}",
            asset_id=asset_id,
            asset_type=asset_type,
            content=content,
            authority="owner",
            semantic_review=semantic_review,
            reason=reason.strip(),
            expected_impacts=expected_impacts,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": "arcvellum/owner-asset-creation/v1",
            "operation": "create",
            "transaction_id": self.transaction_id,
            "asset_id": self.asset_id,
            "asset_type": self.asset_type,
            "precondition": "absent",
            "authority": self.authority,
            "semantic_review": self.semantic_review.value,
            "reason": self.reason,
            "expected_impacts": list(self.expected_impacts),
        }
