"""Asset view definitions and stable identity parsing."""

from __future__ import annotations

from .contracts import AssetViewDefinition, EditorKind


_DEFAULT_DEFINITIONS = (
    AssetViewDefinition(
        asset_type="character",
        schema_id="literary-engineering-workbench/character/v1",
        id_field="character_id",
        title_field="name",
        editor_kind=EditorKind.FORM,
        relative_directory="characters",
        filename_template="{id}.yaml",
        writable_fields=(
            "name",
            "aliases",
            "importance",
            "role",
            "background_story",
            "psychology",
            "bdi",
            "state",
        ),
        reference_fields=(),
        supports_promotion=True,
        supports_archive=True,
    ),
    AssetViewDefinition(
        asset_type="scene",
        schema_id="literary-engineering-workbench/scene/v1",
        id_field="scene_id",
        title_field="scene_id",
        editor_kind=EditorKind.FORM,
        relative_directory="scenes",
        filename_template="{id}.yaml",
        writable_fields=(
            "chapter_id",
            "location",
            "participants",
            "participant_refs",
            "scene_goal",
            "conflict",
            "reader_experience",
            "word_count_target",
        ),
        reference_fields=("participant_refs",),
        supports_promotion=False,
        supports_archive=True,
    ),
    AssetViewDefinition(
        asset_type="world-rule",
        schema_id="literary-engineering-workbench/world-rules/v1",
        id_field="",
        title_field="world_name",
        editor_kind=EditorKind.YAML_ADVANCED,
        relative_directory="canon",
        filename_template="world_rules.yaml",
        writable_fields=("world_name", "rules", "constraints", "taboos", "open_questions"),
        reference_fields=(),
        supports_promotion=True,
        supports_archive=False,
        fixed_id="world_rules",
    ),
    AssetViewDefinition(
        asset_type="location-catalog",
        schema_id="literary-engineering-workbench/location-catalog/v1",
        id_field="",
        title_field="",
        editor_kind=EditorKind.TABLE,
        relative_directory="canon",
        filename_template="locations.yaml",
        writable_fields=("locations",),
        reference_fields=(),
        supports_promotion=True,
        supports_archive=False,
        fixed_id="locations",
    ),
    AssetViewDefinition(
        asset_type="organization-catalog",
        schema_id="literary-engineering-workbench/organization-catalog/v1",
        id_field="",
        title_field="",
        editor_kind=EditorKind.TABLE,
        relative_directory="canon",
        filename_template="organizations.yaml",
        writable_fields=("organizations",),
        reference_fields=(),
        supports_promotion=True,
        supports_archive=False,
        fixed_id="organizations",
    ),
    AssetViewDefinition(
        asset_type="promise-ledger",
        schema_id="literary-engineering-workbench/promise-ledger/v1",
        id_field="",
        title_field="",
        editor_kind=EditorKind.TABLE,
        relative_directory="plot/promises",
        filename_template="ledger.json",
        writable_fields=("promises",),
        reference_fields=("scene_id", "character_id"),
        supports_promotion=False,
        supports_archive=False,
        fixed_id="ledger",
    ),
    AssetViewDefinition(
        asset_type="reader-question-ledger",
        schema_id="literary-engineering-workbench/reader-question-ledger/v1",
        id_field="",
        title_field="",
        editor_kind=EditorKind.TABLE,
        relative_directory="plot/reader_questions",
        filename_template="ledger.json",
        writable_fields=("reader_questions",),
        reference_fields=("scene_id",),
        supports_promotion=False,
        supports_archive=False,
        fixed_id="ledger",
    ),
)


class AssetViewRegistry:
    def __init__(self, definitions: tuple[AssetViewDefinition, ...]):
        self._definitions = {definition.asset_type: definition for definition in definitions}
        if len(self._definitions) != len(definitions):
            raise ValueError("asset type definitions must be unique")

    @classmethod
    def default(cls) -> "AssetViewRegistry":
        return cls(_DEFAULT_DEFINITIONS)

    def definitions(self) -> tuple[AssetViewDefinition, ...]:
        return tuple(self._definitions.values())

    def definition(self, asset_type: str) -> AssetViewDefinition:
        try:
            return self._definitions[asset_type]
        except KeyError as exc:
            raise ValueError(f"unsupported archive asset type: {asset_type}") from exc

    def parse_asset_id(self, asset_id: str) -> tuple[AssetViewDefinition, str]:
        if asset_id.count(":") != 1:
            raise ValueError("asset_id must use <asset-type>:<stable-id>")
        asset_type, local_id = asset_id.split(":", 1)
        definition = self.definition(asset_type)
        if not _valid_local_id(local_id):
            raise ValueError("invalid archive asset stable id")
        if definition.fixed_id and local_id != definition.fixed_id:
            raise ValueError(f"{asset_type} uses fixed id {definition.fixed_id}")
        return definition, local_id

    @staticmethod
    def asset_id(definition: AssetViewDefinition, local_id: str) -> str:
        return f"{definition.asset_type}:{local_id}"


def _valid_local_id(local_id: str) -> bool:
    """Accept project-native Unicode names without accepting path syntax."""

    if not 1 <= len(local_id) <= 120 or ".." in local_id or not local_id[0].isalnum():
        return False
    return all(character.isalnum() or character in "_.-" for character in local_id)
