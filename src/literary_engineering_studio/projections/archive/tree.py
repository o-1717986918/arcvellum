"""Archive asset-tree projection."""

from __future__ import annotations

from ...application.assets.contracts import AssetRecord
from ...application.assets.registry import AssetViewRegistry


def project_asset_tree(
    records: tuple[AssetRecord, ...],
    registry: AssetViewRegistry,
) -> dict[str, object]:
    groups: list[dict[str, object]] = []
    items: list[dict[str, object]] = []
    by_type: dict[str, list[dict[str, object]]] = {}
    for record in records:
        definition = registry.definition(record.asset_type)
        item = {
            "asset_id": record.asset_id,
            "asset_type": record.asset_type,
            "title": record.title,
            "revision": record.revision,
            "editor_kind": definition.editor_kind.value,
            "supports_create": definition.supports_create,
            "supports_promotion": definition.supports_promotion,
            "supports_archive": definition.supports_archive,
        }
        items.append(item)
        by_type.setdefault(record.asset_type, []).append(item)
    for definition in registry.definitions():
        group_items = by_type.get(definition.asset_type, [])
        groups.append(
            {
                "asset_type": definition.asset_type,
                "schema_id": definition.schema_id,
                "editor_kind": definition.editor_kind.value,
                "supports_create": definition.supports_create,
                "count": len(group_items),
                "items": group_items,
            }
        )
    return {
        "schema": "arcvellum/archive-tree/v1",
        "groups": groups,
        "items": items,
        "count": len(items),
    }
