import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from literary_engineering_studio.application.lean_longform_planning import LeanLongformPlanningService
from literary_engineering_studio.application.lean_source_context import current_story_context
from tests.test_lean_longform_plan import _scene
from tests.test_lean_longform_planning_service import _Gateway
from tests.test_planning_count_recovery import _plan


class PlanningStorySourcesTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'project.yaml').write_text(
            'target_length: 30000\ntarget_chapters: 3\ntarget_scenes: 9\n', encoding='utf-8')
        self.character = self.root / 'characters/lin.yaml'
        self.character.parent.mkdir()
        self.character.write_text('name: 林昭\nbackground: 母亲离家后寄过一封信。\n', encoding='utf-8')
        self.canon = self.root / 'canon/facts.json'
        self.canon.parent.mkdir()
        self.canon.write_text(json.dumps({'facts': [{'summary': '林昭是弟弟'}],
            'candidates': [{'summary': '姐姐可能离乡', 'status': 'pending'}]}, ensure_ascii=False), encoding='utf-8')

    def service(self, answers):
        gateway = _Gateway(answers)
        return LeanLongformPlanningService({}, data_root=self.root / 'data', gateway=gateway), gateway

    def test_initial_and_single_repair_receive_full_unchanged_archives(self):
        invalid = _plan()
        invalid['first_window'] = invalid['first_window'][:1]
        service, gateway = self.service([invalid, _plan()])
        before = {path: path.read_bytes() for path in (self.character, self.canon)}
        service.ensure_initial(self.root)
        self.assertEqual(len(gateway.calls), 2)
        for _, prompt, _ in gateway.calls:
            self.assertIn('characters/lin.yaml', prompt)
            self.assertIn('母亲离家后寄过一封信。', prompt)
            self.assertIn('林昭是弟弟', prompt)
            self.assertIn('姐姐可能离乡', prompt)
            self.assertIn('候选不因出现在资料中而生效', prompt)
        self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_next_window_and_repair_receive_current_assets_instead_of_old_planning_biography(self):
        service, gateway = self.service([_plan(), {'scenes': []}, {'scenes': [_scene(str(i)) for i in range(3)]}])
        service.ensure_initial(self.root)
        self.character.write_text('name: 林昭\nbackground: 母亲刚刚来信约定周六见面。\n', encoding='utf-8')
        self.assertTrue(service.expand_next_window(self.root))
        for _, prompt, _ in gateway.calls[1:]:
            self.assertIn('母亲刚刚来信约定周六见面。', prompt)
            self.assertIn('优先于规划中的人物简介', prompt)

    def test_oversize_sources_stop_before_any_gateway_call(self):
        self.character.write_text('文' * 120001, encoding='utf-8')
        service, gateway = self.service([_plan()])
        with self.assertRaisesRegex(ValueError, 'context capacity'):
            service.ensure_initial(self.root)
        self.assertEqual(gateway.calls, [])
        self.assertFalse((self.root / 'plot/lean_project_plan.json').exists())

    def test_sources_changed_during_author_turn_cannot_commit_a_stale_plan(self):
        service, gateway = self.service([_plan()])
        run = gateway.run
        def changing_run(*args, **kwargs):
            result = run(*args, **kwargs)
            self.character.write_text('name: 林昭\nbackground: 作者已更正的经历。\n', encoding='utf-8')
            return result
        gateway.run = changing_run
        with self.assertRaisesRegex(ValueError, 'sources changed'):
            service.ensure_initial(self.root)
        self.assertFalse((self.root / 'plot/lean_project_plan.json').exists())
        self.assertFalse((self.root / 'scenes').exists())

    def test_escaped_archive_source_is_rejected_and_templates_are_excluded(self):
        (self.character.parent / '_template.yaml').write_text('SECRET TEMPLATE', encoding='utf-8')
        self.assertNotIn('SECRET TEMPLATE', current_story_context(self.root))
        original_resolve = Path.resolve
        def escaped(path, *args, **kwargs):
            return self.root.parent / 'outside.yaml' if path == self.character else original_resolve(path, *args, **kwargs)
        with patch.object(Path, 'resolve', escaped), self.assertRaisesRegex(ValueError, 'escapes'):
            current_story_context(self.root)
