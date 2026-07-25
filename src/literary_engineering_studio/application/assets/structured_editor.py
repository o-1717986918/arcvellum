"""Registry-driven structured editing without bypassing formal asset Gates."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .contracts import AssetFieldDefinition, FieldKind
from .document_codec import parse_asset_document, render_asset_fields
from .loader import AssetLoader
from .registry import AssetViewRegistry
from .revisions import content_revision
from .validation import validate_asset_content


class StructuredDraftStaleError(RuntimeError):
    pass


class StructuredFieldError(ValueError):
    pass


class StructuredAssetService:
    def __init__(self, registry: AssetViewRegistry, loader: AssetLoader):
        self.registry = registry
        self.loader = loader

    def project(
        self,
        project_root: Path,
        asset_id: str,
        content: str,
    ) -> dict[str, object]:
        root = self.loader.project_root(project_root)
        self.loader.load(root, asset_id)
        definition, _ = self.registry.parse_asset_id(asset_id)
        parsed = parse_asset_document(definition, content)
        values = parsed.json_safe_mapping()
        return {
            "schema": "arcvellum/archive-structured-document/v1",
            "asset_id": asset_id,
            "editor_kind": definition.editor_kind.value,
            "document_format": parsed.document_format,
            "source_revision": content_revision(content),
            "fields": [
                {
                    **field.as_dict(),
                    "defined": field.name in values,
                    "value": values.get(field.name),
                }
                for field in definition.field_definitions
            ],
        }

    def render(
        self,
        project_root: Path,
        asset_id: str,
        content: str,
        source_revision: str,
        fields: Mapping[str, Any],
    ) -> dict[str, object]:
        root = self.loader.project_root(project_root)
        self.loader.load(root, asset_id)
        definition, local_id = self.registry.parse_asset_id(asset_id)
        if content_revision(content) != source_revision:
            raise StructuredDraftStaleError(
                "Structured editor source no longer matches the current draft."
            )
        field_contracts = {field.name: field for field in definition.field_definitions}
        unknown = sorted(set(fields) - set(field_contracts))
        if unknown:
            raise StructuredFieldError(
                f"Structured editor cannot write unregistered fields: {', '.join(unknown)}"
            )
        for name, value in fields.items():
            _validate_field_value(field_contracts[name], value)
        rendered = render_asset_fields(definition, content, fields)
        validation = validate_asset_content(root, definition, local_id, rendered)
        return {
            "schema": "arcvellum/archive-structured-render/v1",
            "asset_id": asset_id,
            "content": rendered,
            "source_revision": content_revision(rendered),
            "validation": validation.as_dict(),
            "structure": self.project(root, asset_id, rendered),
        }


def _validate_field_value(field: AssetFieldDefinition, value: Any) -> None:
    if value is None:
        if field.required:
            raise StructuredFieldError(f"{field.name} is required.")
        return
    valid = {
        FieldKind.TEXT: lambda item: isinstance(item, str),
        FieldKind.MARKDOWN: lambda item: isinstance(item, str),
        FieldKind.NUMBER: lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        FieldKind.CHOICE: lambda item: isinstance(item, str),
        FieldKind.STRING_LIST: lambda item: isinstance(item, list)
        and all(isinstance(child, str) for child in item),
        FieldKind.OBJECT: lambda item: isinstance(item, dict),
        FieldKind.TABLE: lambda item: isinstance(item, list),
    }[field.kind](value)
    if not valid:
        raise StructuredFieldError(
            f"{field.name} must use the registered {field.kind.value} value shape."
        )
    if field.options and value not in field.options:
        raise StructuredFieldError(
            f"{field.name} must be one of: {', '.join(field.options)}"
        )
    if field.required and isinstance(value, str) and not value.strip():
        raise StructuredFieldError(f"{field.name} is required.")
