"""Source-labelled recovery keeps real card wording and multiline dialogue intact."""
from copy import deepcopy
import unittest
from literary_engineering_studio_engine.public.literary import ACTOR_CARD_SECTIONS
from literary_engineering_studio.runtimes.natural_card_source import restore_labelled_card_sections


class CardSourceTests(unittest.TestCase):
    def test_local_card_uses_declared_identity_when_core_mentions_another_character(self):
        from literary_engineering_studio.runtimes.natural_local_delivery import local_cards
        fields = {key: '这一节的完整原文' for key in ACTOR_CARD_SECTIONS}
        fields['CORE_IDENTITY'] = '代号：铜靴\n所属：眼下住在莓灯茶馆阁楼，暂属莓灯。'
        answer = '\n\n'.join('【' + key + '】\n' + text for key, text in fields.items())
        result = local_cards(answer, {'eligible_actors': ['莓灯', '铜靴']})
        self.assertEqual(set(result), {'铜靴'})
        self.assertEqual(result['铜靴']['sections'], fields)
        from literary_engineering_studio_engine.public.literary import parse_actor_character_card
        card = parse_actor_character_card(result['铜靴'], target='铜靴')
        self.assertTrue(card.source_refs[0].startswith('natural-source:'))
        bulleted = answer.replace('代号：铜靴', '- 代号：铜靴')
        self.assertEqual(local_cards(bulleted, {'eligible_actors': ['莓灯', '铜靴']})['铜靴']['target'], '铜靴')
        ambiguous = answer.replace('代号：铜靴\n', '这位旅客叫铜靴。\n')
        self.assertEqual(local_cards(ambiguous, {'eligible_actors': ['莓灯', '铜靴']}), {})
    def test_plain_card_source_is_a_repairable_contract_error(self):
        from literary_engineering_studio.runtimes.actor_card_transport import card_section_schema
        with self.assertRaisesRegex(ValueError, 'structured card object'):
            card_section_schema('【PERSONA_LOAD】完整卡原文')
    def test_restores_list_and_quotes_from_the_named_complete_card(self):
        fields={key:'这一节的原文' for key in ACTOR_CARD_SECTIONS}
        fields['CORE_IDENTITY']='陶婶，在食堂工作。'
        fields['SELF_CLAIM_EXAMPLES']='- "添不添？"\n- "坐。"'
        answer='\n\n'.join('**'+key+'**：'+value for key,value in fields.items())
        payload={'material_requests':[{'target':'陶婶','character_card':{'sections':{'SELF_CLAIM_EXAMPLES':'“添不添？”／“坐。”'}}}]}
        result=restore_labelled_card_sections(answer,payload)
        self.assertEqual(result['material_requests'][0]['character_card']['sections']['SELF_CLAIM_EXAMPLES'],fields['SELF_CLAIM_EXAMPLES'])

    def test_rejects_changed_words_wrong_target_and_incomplete_source(self):
        answer='**CORE_IDENTITY**：陶婶\n**SELF_CLAIM_EXAMPLES**：坐。'
        payload={'material_requests':[{'target':'陶婶','character_card':{'sections':{'SELF_CLAIM_EXAMPLES':'站。'}}}]}
        self.assertEqual(restore_labelled_card_sections(answer,deepcopy(payload)),payload)

    def test_chinese_section_headings_map_without_changing_card_words(self):
        sections = {key: '铜靴的原文' for key in ACTOR_CARD_SECTIONS}
        sections['核心身份与代号'] = sections.pop('CORE_IDENTITY')
        sections['私密空间行为模式'] = sections.pop('PRIVATE_BEHAVIOR_MODES')
        sections['私密互动关键词与动作库'] = sections.pop('INTERACTION_LIBRARY')
        payload = {'material_requests': [{'target': '铜靴', 'character_card': {'sections': sections}}]}
        result = restore_labelled_card_sections('铜靴的原文', payload)
        recovered = result['material_requests'][0]['character_card']['sections']
        self.assertEqual(set(recovered), set(ACTOR_CARD_SECTIONS))
        self.assertEqual(set(recovered.values()), {'铜靴的原文'})

    def test_named_section_array_maps_to_the_same_sixteen_card_fields(self):
        sections = [{'name': '【'+key+'】', 'text': '铜靴的完整原文'} for key in ACTOR_CARD_SECTIONS]
        payload = {'material_requests': [{'target': '铜靴', 'character_card': {'sections': sections}}]}
        card = restore_labelled_card_sections('铜靴的完整原文', payload)['material_requests'][0]['character_card']
        self.assertEqual(set(card['sections']), set(ACTOR_CARD_SECTIONS))
        self.assertEqual(set(card['sections'].values()), {'铜靴的完整原文'})

    def test_schema_metadata_is_canonical_for_a_complete_literal_card(self):
        fields = {key: '人物原文' for key in ACTOR_CARD_SECTIONS}
        payload = {'material_requests': [{'target': '铜靴', 'character_card': {'schema': 'actor_system_template', 'sections': fields}}]}
        result = restore_labelled_card_sections('人物原文', payload)['material_requests'][0]['character_card']
        self.assertEqual(result['schema'], 'arcvellum/actor-character-card/v2')
        self.assertEqual(result['sections'], fields)
        self.assertEqual(result['target'], '铜靴')
