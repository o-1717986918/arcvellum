"""A transport quote substitution must restore the author's words, never approximate them."""
from copy import deepcopy
import unittest
from literary_engineering_studio.runtimes.commission_source_format import restore_commission_source, restore_tone_source


class QuotePresentationRecoveryTests(unittest.TestCase):
    def test_real_editor_heading_keeps_number_and_restores_literal_quotation(self):
        source = '规则8（已有材料的表达）｜原文：她说“好”。替换：她说“行”。'
        payload = {'edits': [{'rule_id': '规则8（已有材料的表达）', 'before': '她说"好”。', 'after': '她说"行”。'}]}
        result = restore_tone_source(source, payload)
        self.assertEqual(result['edits'], [{'rule_id': '8', 'before': '她说“好”。', 'after': '她说“行”。'}])
        self.assertEqual(result['tone_rule_recovery'][0]['original'], '规则8（已有材料的表达）')

    def test_restores_unique_card_source_and_keeps_exact_author_punctuation(self):
        source = '**SELF_CLAIM_RULES**：说走是"去挣钱"，不是"逃"。\n\n**CORE_IDENTITY**：其他内容。'
        payload = {'material_requests':[{'character_card':{'sections':{'SELF_CLAIM_RULES':"说走是'去挣钱'，不是'逃'。"}}}]}
        recovered = restore_commission_source(source, payload)
        self.assertEqual(recovered['material_requests'][0]['character_card']['sections']['SELF_CLAIM_RULES'],'说走是"去挣钱"，不是"逃"。')
        span = recovered['commission_format_recovery'][0]
        self.assertEqual(source[span['start']:span['end']], '说走是"去挣钱"，不是"逃"。')

    def test_keeps_ambiguous_or_rewritten_text_for_original_validation(self):
        for source in ('他说“记着”。她说"记着"。', '他说“忘了”。'):
            payload={'material_requests':[{'author_prompt':"说'记着'"}]}
            self.assertEqual(restore_commission_source(source,deepcopy(payload)),payload)

    def test_identical_repeated_source_is_still_literal(self):
        source = '文风："物件"承担。\n再次："物件"承担。'
        payload={'material_requests':[{'style_direction':'“物件”承担。'}]}
        recovered=restore_commission_source(source,payload)
        self.assertEqual(recovered['material_requests'][0]['style_direction'],'"物件"承担。')
