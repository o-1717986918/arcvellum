"""A transport quote substitution must restore the author's words, never approximate them."""
from copy import deepcopy
import unittest
from literary_engineering_studio.runtimes.commission_source_format import restore_commission_source, restore_tone_source


class QuotePresentationRecoveryTests(unittest.TestCase):
    def test_commission_terminal_punctuation_is_restored_to_unique_source(self):
        source = '本场需要四类伙伴分工，再借两位人物的活口：\n\n下面列出委托。'
        payload = {'material_requests': [{'working_context': '本场需要四类伙伴分工，再借两位人物的活口。'}]}
        recovered = restore_commission_source(source, payload)
        self.assertEqual(recovered['material_requests'][0]['working_context'], source.split('\n')[0])
        entry = recovered['commission_format_recovery'][0]
        self.assertEqual(entry['projection'], 'terminal-punctuation-only')
        self.assertEqual(source[entry['start']:entry['end']], recovered['material_requests'][0]['working_context'])

    def test_terminal_recovery_rejects_ambiguity_words_and_card_sections(self):
        text = '本场需要四类伙伴分工，再借两位人物的活口。'
        for source in (text[:-1] + '：\n' + text[:-1] + '；', text.replace('四类', '三类')):
            payload = {'material_requests': [{'working_context': text}]}
            self.assertEqual(restore_commission_source(source, deepcopy(payload)), payload)
        payload = {'material_requests': [{'character_card': {'sections': {'CORE_IDENTITY': text}}}]}
        self.assertEqual(restore_commission_source(text[:-1] + '：', deepcopy(payload)), payload)

    def test_editor_quote_markers_are_removed_for_actual_body_edits(self):
        prose = '那根细的是四个字。\n井绳还没有名字。'
        source = '> 那根细的是四个字。\n> 井绳还没有名字。\n\n替换：\n> 镇上人用四个字叫井绳。'
        payload = {'edits': [{'rule_id': '1', 'before': '> 那根细的是四个字。\n> 井绳还没有名字。',
                              'after': '> 镇上人用四个字叫井绳。'}]}
        result = restore_tone_source(source, payload, prose)
        self.assertEqual(result['edits'][0]['before'], prose)
        self.assertEqual(result['edits'][0]['after'], '镇上人用四个字叫井绳。')

    def test_body_quote_marks_are_preserved_when_they_belong_to_prose(self):
        prose = '> 名字记在墙上。'
        payload = {'edits': [{'rule_id': '1', 'before': prose, 'after': '> 名字写在墙上。'}]}
        self.assertEqual(restore_tone_source(prose, deepcopy(payload), prose), payload)

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
