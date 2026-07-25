"""Archive asset-detail projection."""

from __future__ import annotations

from ...application.assets.contracts import AssetRecord
from ...application.assets.registry import AssetViewRegistry


def project_asset_detail(record: AssetRecord, registry: AssetViewRegistry) -> dict[str, object]:
    definition = registry.definition(record.asset_type)
    return {
        "schema": "arcvellum/archive-asset-detail/v1",
        "asset": {
            "asset_id": record.asset_id,
            "asset_type": record.asset_type,
            "title": record.title,
            "revision": record.revision,
            "content": record.content,
            "media_type": record.media_type,
            "source_path": record.relative_path,
            "schema_id": definition.schema_id,
            "editor_kind": definition.editor_kind.value,
            "writable_fields": list(definition.writable_fields),
            "field_definitions": [
                field.as_dict() for field in definition.field_definitions
            ],
            "reference_fields": list(definition.reference_fields),
            "supports_create": definition.supports_create,
            "supports_promotion": definition.supports_promotion,
            "supports_archive": definition.supports_archive,
        },
    }
