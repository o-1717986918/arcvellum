"""Versioned technical card extraction; literary wording stays in the source."""
from literary_engineering_studio_engine.public.literary import (
    ACTOR_CARD_SCHEMA, LEGACY_ACTOR_CARD_SCHEMA, actor_card_section_names, actor_card_schema_for_template,
)


def actor_card_contract(context):
    template = context.get('actor_system_template') or context.get('template')
    schema = (actor_card_schema_for_template(template) if template
              else context.get('actor_card_schema') or ACTOR_CARD_SCHEMA)
    return {'schema': schema, 'target': 'target from context',
        'sections': {key: 'verbatim card section' for key in actor_card_section_names(schema)},
        'source_refs': [], 'design_notes': ''}


def card_presence_instruction(context):
    card = actor_card_contract(context)
    return (f"完整人物卡使用 {card['schema']} 的 {len(card['sections'])} 个区块。"
            '按原文区块逐字提取，保留 LAYER、TRAIT、MODE、行为与台词、RULE、EXAMPLE、PREFER、BEHAVIOR 的分项原文；'
            'target 对应目标人物，source_refs 使用原文来源路径。未出现卡时 character_card 为 null。')


def card_section_schema(card):
    if not isinstance(card, dict):
        raise ValueError('card extraction needs a structured card object, not a source text string')
    sections = card.get('sections')
    if isinstance(sections, dict):
        for schema in (ACTOR_CARD_SCHEMA, LEGACY_ACTOR_CARD_SCHEMA):
            if set(sections) == set(actor_card_section_names(schema)):
                return schema
    raise ValueError('card extraction needs all sections of its eleven- or sixteen-section version')
