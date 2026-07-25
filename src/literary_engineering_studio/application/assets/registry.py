"""Asset view definitions and stable identity parsing."""

from __future__ import annotations

from .contracts import AssetFieldDefinition, AssetViewDefinition, EditorKind, FieldKind


def _field(
    name: str,
    label: str,
    kind: FieldKind,
    section: str,
    *,
    required: bool = False,
    help_text: str = "",
    options: tuple[str, ...] = (),
) -> AssetFieldDefinition:
    return AssetFieldDefinition(
        name=name,
        label=label,
        kind=kind,
        section=section,
        required=required,
        help_text=help_text,
        options=options,
    )


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
        supports_create=True,
        supports_promotion=True,
        supports_archive=True,
        field_definitions=(
            _field("name", "姓名", FieldKind.TEXT, "身份", required=True),
            _field("aliases", "别名", FieldKind.STRING_LIST, "身份"),
            _field(
                "importance",
                "叙事级别",
                FieldKind.CHOICE,
                "身份",
                required=True,
                options=("major", "secondary", "minor"),
            ),
            _field("role", "故事职能", FieldKind.TEXT, "身份"),
            _field(
                "background_story",
                "背景故事",
                FieldKind.OBJECT,
                "深层动机",
                help_text="不会被正文直接说明，但必须通过选择、回避和误判影响行为。",
            ),
            _field("psychology", "心理结构", FieldKind.OBJECT, "深层动机"),
            _field("bdi", "信念、欲望与意图", FieldKind.OBJECT, "深层动机"),
            _field("state", "当前状态", FieldKind.OBJECT, "动态状态"),
        ),
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
        supports_create=True,
        supports_promotion=False,
        supports_archive=True,
        field_definitions=(
            _field("chapter_id", "所属章节", FieldKind.TEXT, "定位", required=True),
            _field("location", "地点", FieldKind.TEXT, "定位"),
            _field("participants", "参与角色", FieldKind.STRING_LIST, "定位"),
            _field(
                "participant_refs",
                "角色资产引用",
                FieldKind.STRING_LIST,
                "定位",
                help_text="必须对应已有角色资产的稳定 ID。",
            ),
            _field("scene_goal", "场景目标", FieldKind.MARKDOWN, "戏剧任务"),
            _field("conflict", "冲突结构", FieldKind.OBJECT, "戏剧任务"),
            _field(
                "reader_experience",
                "读者体验契约",
                FieldKind.OBJECT,
                "读者体验",
            ),
            _field(
                "word_count_target",
                "目标字数",
                FieldKind.NUMBER,
                "篇幅",
                required=True,
            ),
        ),
    ),
    AssetViewDefinition(
        asset_type="world-rule",
        schema_id="literary-engineering-workbench/world-rules/v1",
        id_field="",
        title_field="world_name",
        editor_kind=EditorKind.FORM,
        relative_directory="canon",
        filename_template="world_rules.yaml",
        writable_fields=("world_name", "rules", "constraints", "taboos", "open_questions"),
        reference_fields=(),
        supports_create=True,
        supports_promotion=True,
        supports_archive=False,
        fixed_id="world_rules",
        field_definitions=(
            _field("world_name", "世界名称", FieldKind.TEXT, "总览"),
            _field("rules", "世界规则", FieldKind.TABLE, "规则"),
            _field("constraints", "硬约束", FieldKind.TABLE, "规则"),
            _field("taboos", "禁区", FieldKind.TABLE, "规则"),
            _field("open_questions", "待定问题", FieldKind.TABLE, "演化"),
        ),
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
        supports_create=True,
        supports_promotion=True,
        supports_archive=False,
        fixed_id="locations",
        field_definitions=(
            _field("locations", "地点目录", FieldKind.TABLE, "地点"),
        ),
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
        supports_create=True,
        supports_promotion=True,
        supports_archive=False,
        fixed_id="organizations",
        field_definitions=(
            _field("organizations", "组织目录", FieldKind.TABLE, "组织"),
        ),
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
        supports_create=True,
        supports_promotion=False,
        supports_archive=False,
        fixed_id="ledger",
        field_definitions=(
            _field("promises", "承诺与兑现", FieldKind.TABLE, "读者承诺"),
        ),
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
        supports_create=True,
        supports_promotion=False,
        supports_archive=False,
        fixed_id="ledger",
        field_definitions=(
            _field(
                "reader_questions",
                "读者问题",
                FieldKind.TABLE,
                "读者问题",
            ),
        ),
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
