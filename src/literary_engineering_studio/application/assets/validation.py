"""Deterministic structural validation for owner-edited assets."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .contracts import AssetValidation, AssetViewDefinition, ValidationIssue
from .document_codec import AssetDocumentError, parse_asset_document


MAX_ASSET_BYTES = 4 * 1024 * 1024

_CREATION_REQUIRED_FIELDS = {
    "character": ("character_id", "name", "importance"),
    "scene": ("scene_id", "chapter_id", "status", "word_count_target"),
    "world-rule": ("rules", "constraints", "open_questions"),
    "location-catalog": ("locations",),
    "organization-catalog": ("organizations",),
    "promise-ledger": ("promises",),
    "reader-question-ledger": ("reader_questions",),
}

_CREATION_NONEMPTY_FIELDS = {
    "character": ("name",),
    "scene": ("chapter_id", "status", "word_count_target"),
}


def validate_asset_content(
    project_root: Path,
    definition: AssetViewDefinition,
    local_id: str,
    content: str,
) -> AssetValidation:
    issues: list[ValidationIssue] = []
    encoded = content.encode("utf-8")
    if "\0" in content:
        issues.append(ValidationIssue("nul_byte", "error", "Asset text must not contain NUL bytes."))
    if not content.strip():
        issues.append(ValidationIssue("empty_content", "error", "Asset content must not be empty."))
    if len(encoded) > MAX_ASSET_BYTES:
        issues.append(ValidationIssue("asset_too_large", "error", "Asset exceeds the 4 MB editing limit."))

    try:
        payload = parse_asset_document(definition, content).mapping
    except AssetDocumentError as exc:
        code = "invalid_json" if definition.filename_template.endswith(".json") else "invalid_yaml"
        issues.append(ValidationIssue(code, "error", str(exc)))
        return AssetValidation(False, tuple(issues))
    _validate_identity(definition, local_id, payload, issues)
    _validate_references(project_root, definition, payload, issues)

    return AssetValidation(not any(issue.severity == "error" for issue in issues), tuple(issues))


def validate_asset_creation(
    project_root: Path,
    definition: AssetViewDefinition,
    local_id: str,
    content: str,
) -> AssetValidation:
    base = validate_asset_content(project_root, definition, local_id, content)
    issues = list(base.issues)
    required = _CREATION_REQUIRED_FIELDS.get(definition.asset_type, ())
    try:
        payload = parse_asset_document(definition, content).mapping
    except AssetDocumentError:
        payload = {}
    missing = [field for field in required if field not in payload]
    for field in missing:
        issues.append(
            ValidationIssue(
                "missing_creation_field",
                "error",
                f"New {definition.asset_type} asset must declare {field}.",
                field,
            )
        )
    for field in _CREATION_NONEMPTY_FIELDS.get(definition.asset_type, ()):
        if field not in missing and not _has_value(payload.get(field)):
            issues.append(
                ValidationIssue(
                    "empty_creation_field",
                    "error",
                    f"New {definition.asset_type} asset must provide {field}.",
                    field,
                )
            )
    return AssetValidation(not any(issue.severity == "error" for issue in issues), tuple(issues))


def _validate_identity(
    definition: AssetViewDefinition,
    local_id: str,
    payload: Mapping[str, Any],
    issues: list[ValidationIssue],
) -> None:
    if not definition.id_field:
        return
    declared = payload.get(definition.id_field)
    if not _has_value(declared):
        issues.append(
            ValidationIssue(
                "missing_asset_id",
                "error",
                f"Asset must declare {definition.id_field}.",
                definition.id_field,
            )
        )
    elif not isinstance(declared, (str, int, float)) or str(declared) != local_id:
        issues.append(
            ValidationIssue(
                "asset_id_mismatch",
                "error",
                f"Declared {definition.id_field} does not match stable asset id.",
                definition.id_field,
            )
        )


def _validate_references(
    project_root: Path,
    definition: AssetViewDefinition,
    payload: Mapping[str, Any],
    issues: list[ValidationIssue],
) -> None:
    if definition.asset_type != "scene":
        return
    references = payload.get("participant_refs", [])
    if not isinstance(references, list) or not all(isinstance(item, str) for item in references):
        issues.append(
            ValidationIssue(
                "invalid_character_references",
                "error",
                "Scene participant_refs must be a list of character IDs.",
                "participant_refs",
            )
        )
        return
    for character_id in references[:80]:
        if not (project_root / "characters" / f"{character_id}.yaml").is_file():
            issues.append(
                ValidationIssue(
                    "broken_character_reference",
                    "error",
                    f"Scene participant reference does not resolve: {character_id}",
                    "participant_refs",
                )
            )


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True
