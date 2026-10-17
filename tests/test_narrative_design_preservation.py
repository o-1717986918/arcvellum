from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from literary_engineering_studio_engine.public.literary import (
    calculate_word_budget, normalize_initial_plan, render_outline, normalize_narrative_design,
)
from tests.test_lean_longform_plan import _scene


class NarrativeDesignPreservationTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'project.yaml').write_text(
            'target_length: 3000\ntarget_chapters: 1\ntarget_scenes: 1\n', encoding='utf-8')
        self.budget = calculate_word_budget(self.root)
        self.answer = {'premise': '旧信重现', 'central_question': '谁留下信？', 'ending_choice': '寄出信',
            'volume_obligations': ['重新认识旧友'], 'chapters': [{'title': '来信', 'dramatic_turn': '信重现',
                'obligation': '建立问题', 'reader_question': '谁留下信？'}], 'first_window': [_scene('旧信')]}

    def plan(self, design):
        return normalize_initial_plan({**self.answer, 'narrative_design': design}, self.budget, project_digest='test')

    def test_labelled_multiline_narrative_choices_survive_normalization_and_outline(self):
        text = ('**narrative_mode**：第一人称限知。\n\n'
                '**viewpoint_design**：林昭始终在场。\n其他人物仅通过观察呈现。\n\n'
                '**narrator_voice**：说话快，遇见旧友时停顿。')
        design = self.plan(text)['narrative_design']
        self.assertEqual(design, {'narrative_mode': '第一人称限知。',
            'viewpoint_design': '林昭始终在场。\n其他人物仅通过观察呈现。',
            'narrator_voice': '说话快，遇见旧友时停顿。'})
        for value in design.values():
            self.assertIn(value, render_outline(self.plan(text)))

    def test_freeform_and_additional_authored_fields_are_not_silently_erased(self):
        self.assertEqual(normalize_narrative_design('作者明确选择第三人称限知。'),
                         {'notes': '作者明确选择第三人称限知。'})
        self.assertEqual(self.plan('由三封信连接不同年代。')['narrative_design'],
                         {'notes': '由三封信连接不同年代。'})
        source = {'viewpoint_design': '第三人称限知', 'reader_distance': '从远处逐渐走近'}
        original = deepcopy(source)
        self.assertEqual(self.plan(source)['narrative_design'], source)
        self.assertEqual(source, original)

    def test_invalid_or_ambiguous_design_requires_explicit_repair(self):
        for value in ([], 3, {'narrator_voice': ['声音']}, {'viewpoint_design': None},
                      '**narrative_mode**：第一人称\n**narrative_mode**：第三人称'):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'narrative_design'):
                self.plan(value)

    def test_capacity_limit_is_not_bypassed_by_a_string_delivery(self):
        with self.assertRaisesRegex(ValueError, 'context capacity'):
            self.plan('文' * 8001)
