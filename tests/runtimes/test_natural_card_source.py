"""Source-labelled recovery keeps real card wording and multiline dialogue intact."""
from copy import deepcopy
import unittest
from literary_engineering_studio_engine.public.literary import ACTOR_CARD_SECTIONS
from literary_engineering_studio.runtimes.natural_card_source import restore_labelled_card_sections


class CardSourceTests(unittest.TestCase):
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
