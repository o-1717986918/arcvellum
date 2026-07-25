"""Deterministic structural validation for owner-edited assets."""

from __future__ import annotations

import json
from pathlib import Path

from literary_engineering_studio_engine.display_cleaner import list_from_yaml_text, scalar_from_yaml_text

from .contracts import AssetValidation, AssetViewDefinition, ValidationIssue


MAX_ASSET_BYTES = 4 * 1024 * 1024


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

    if definition.filename_template.endswith(".json"):
        try:
            payload = json.loads(content)
            if not isinstance(payload, dict):
                issues.append(ValidationIssue("json_root", "error", "JSON asset root must be an object."))
        except json.JSONDecodeError as exc:
            issues.append(ValidationIssue("invalid_json", "error", f"Invalid JSON at line {exc.lineno}."))
    elif definition.filename_template.endswith((".yaml", ".yml")):
        _validate_yaml_identity(definition, local_id, content, issues)
        _validate_yaml_references(project_root, definition, content, issues)

    return AssetValidation(not any(issue.severity == "error" for issue in issues), tuple(issues))


def _validate_yaml_identity(
    definition: AssetViewDefinition,
    local_id: str,
    content: str,
    issues: list[ValidationIssue],
) -> None:
    if not definition.id_field:
        return
    declared = scalar_from_yaml_text(content, definition.id_field)
    if not declared:
        issues.append(
            ValidationIssue(
                "missing_asset_id",
                "error",
                f"Asset must declare {definition.id_field}.",
                definition.id_field,
            )
        )
    elif declared != local_id:
        issues.append(
            ValidationIssue(
                "asset_id_mismatch",
                "error",
                f"Declared {definition.id_field} does not match stable asset id.",
                definition.id_field,
            )
        )


def _validate_yaml_references(
    project_root: Path,
    definition: AssetViewDefinition,
    content: str,
    issues: list[ValidationIssue],
) -> None:
    if definition.asset_type != "scene":
        return
    for character_id in list_from_yaml_text(content, "participant_refs", limit=80):
        if not (project_root / "characters" / f"{character_id}.yaml").is_file():
            issues.append(
                ValidationIssue(
                    "broken_character_reference",
                    "error",
                    f"Scene participant reference does not resolve: {character_id}",
                    "participant_refs",
                )
            )
