"""Recover technical selection/plan metadata while retaining authored prose."""
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest
from types import SimpleNamespace
from literary_engineering_studio.application.creator_persona import CreatorPersonaStore
from literary_engineering_studio.runtime.role_conversation import RoleConversationResult
from literary_engineering_studio.runtimes.pi_scene_transaction import PiSceneTransactionRuntime
from literary_engineering_studio.runtimes.scene_creator_material_policy import material_selection_error
from literary_engineering_studio.runtimes.scene_natural_output import NaturalOutputProcessor
from literary_engineering_studio_engine.public.literary import (
    LengthTarget, RhythmDirective, SceneBrief, SceneRisk, SceneRiskLevel, StyleMountRef,
)
from tests.runtimes.test_scene_natural_output import NaturalGateway, PROSE, REQUEST


class DeliveryRecoveryTests(unittest.TestCase):
    def test_explicit_scratch_selection_receipt_is_frozen_without_inventing_choices(self):
        from literary_engineering_studio.runtimes.natural_turn_store import NaturalTurnStore
        with TemporaryDirectory() as tmp:
            journal=NaturalTurnStore(Path(tmp),'creator-selection')
            receipt='记录已存进工作室：`choices.md`。'
            text='采用 v2:actual:1，让水声接住重逢。'
            reads=[]
            def read(relative):
                reads.append(relative)
                self.assertEqual(relative,'choices.md')
                return text
            source=journal.referenced_scratch_source('task',receipt,read)
            self.assertIn(text,source)
            self.assertTrue(source.startswith(receipt))
            self.assertEqual(journal.referenced_scratch_source('task',receipt,lambda _:self.fail('frozen source drifted')),source)
            self.assertEqual(reads,['choices.md'])
            self.assertEqual(journal.referenced_scratch_source('new task','未指向任何札记',read),'未指向任何札记')

    def test_selection_source_reuse_is_bound_to_actual_body_and_candidate_task(self):
        from literary_engineering_studio.runtimes.natural_turn_store import NaturalTurnStore
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / 'tx/v2/literary-originals'
            store = NaturalTurnStore(root, 'creator-selection')
            task = '已提供的候选 ID：["v2:abc:1"]\n已记录的正文：\n原正文。'
            prompt = '原准备语境\n' + task
            store.answer(prompt, lambda: '改写 v2:abc:1，使光进入叙述。')
            sent = root.parent.parent / 'sent-prompts'; sent.mkdir()
            (sent / 'one.json').write_text(json.dumps({'role': 'worker', 'prompt': json.dumps({'prompt': prompt})}), encoding='utf-8')
            answer, reused = store.answer('恢复后的语境\n' + task, lambda: self.fail('same selection must reuse the preserved creator note'))
            self.assertTrue(reused)
            self.assertIn('v2:abc:1', answer)
            answer, reused = store.answer('恢复后的语境\n' + task.replace('原正文', '修订正文'), lambda: '新的取舍')
            self.assertFalse(reused)
            self.assertEqual(answer, '新的取舍')

    def test_failed_technical_extraction_resumes_latest_original_without_new_creator_preparation(self):
        from literary_engineering_studio.runtimes.natural_transport_repair import NaturalExtractionError
        class Gateway(NaturalGateway):
            fail_extraction = True
            def run(self, root, prompt, **kwargs):
                envelope = json.loads(prompt)
                if 'task_contract' in envelope['prompt']:
                    task = json.loads(envelope['prompt'])
                    if self.fail_extraction and task['operation'] == 'creator':
                        self.extract_calls += 1
                        return RoleConversationResult('pi-worker', 'extract', 'test/model', json.dumps({
                            'material_plan': {'required_kinds': ['environment'], 'reason': '借水声延续等待'},
                            'material_requests': [{**REQUEST, 'author_prompt': '整理器改写的邀请'}]}, ensure_ascii=False))
                return super().run(root, prompt, **kwargs)
        with TemporaryDirectory() as tmp:
            gateway = Gateway(); runtime, brief = self.runtime(tmp, gateway)
            with self.assertRaises(NaturalExtractionError):
                runtime.create_scene('tx-technical-source', brief)
            self.assertEqual(gateway.creator_calls, 1)
            gateway.fail_extraction = False
            calls = gateway.extract_calls
            with self.assertRaises(NaturalExtractionError):
                runtime.create_scene('tx-technical-source', brief)
            self.assertEqual(gateway.extract_calls, calls)
            self.assertEqual(gateway.creator_calls, 1)
            # A changed processor is a new recovery identity; the original author turn survives.
            from unittest.mock import patch
            with patch('literary_engineering_studio.runtimes.natural_transport_pipeline.PROCESSOR_VERSION', 'fixed-parser'):
                result = runtime.create_scene('tx-technical-source', brief)
            self.assertEqual(result.prose, PROSE)
            self.assertEqual(gateway.creator_calls, 2)
            self.assertEqual(gateway.material_calls, 1)

    def test_explicit_handoff_field_label_is_restored_and_other_unknown_targets_remain(self):
        from literary_engineering_studio.runtimes.handoff_transport import restore_handoff_targets
        handoff = {'target_ref': 'next_handoff', 'summary': '下一场从借月的各家生活展开。', 'evidence': '保留原交接'}
        unknown = {'target_ref': 'invented/path.yaml', 'summary': '未知档案'}
        payload = {'prose': PROSE, 'scene_delta': {'next_handoff': ['已经记录的交接'], 'continuity_changes': [handoff, unknown]}}
        restore_handoff_targets(payload)
        self.assertEqual(payload['prose'], PROSE)
        self.assertEqual(payload['scene_delta']['next_handoff'], ['已经记录的交接', handoff['summary']])
        self.assertEqual(payload['scene_delta']['continuity_changes'], [unknown])
        self.assertEqual(payload['handoff_target_resolution'][0]['original_record'], handoff)

    def test_macro_recovery_uses_selected_frozen_cards_without_loading_card_design(self):
        from literary_engineering_studio.runtimes.scene_creator_memory import SceneCreatorMemoryV1
        from literary_engineering_studio.runtimes.scene_creator_natural import _creator_context, _needs_card_design
        with TemporaryDirectory() as tmp:
            cards = {'frozen_scene_cards': [{'card': {'target': '阿青'}}],
                     'work_cards': [{'card': {'target': '阿青'}}, {'card': {'target': '未选角色'}}],
                     'stable_persona_sources': {}}
            coordinator = SimpleNamespace(root=Path(tmp), material_scope={'actor_targets': ['阿青', '未选角色']},
                plan_context=lambda: None, creator_card_context=lambda: cards)
            context = _creator_context(SceneCreatorMemoryV1('s1'), coordinator, {'scene_brief': {'participants': []}}, None)
            self.assertEqual([row['card']['target'] for row in context['actor_card_context']['work_cards']], ['阿青'])
            self.assertFalse(_needs_card_design(context, {'issue': 'extraction changed selected material candidate ID'}))
            self.assertTrue(_needs_card_design(context, {'issue': '为角色补充人格卡'}))
            runtime = PiSceneTransactionRuntime.__new__(PiSceneTransactionRuntime)
            runtime._require_actor_cards([SimpleNamespace(kind='actor', target='阿青', character_card=None)], coordinator)

    def runtime(self, tmp, gateway):
        root, data = Path(tmp) / 'work', Path(tmp) / 'data'
        root.mkdir()
        (root / 'project.yaml').write_text('title: 雨信\n', encoding='utf-8')
        CreatorPersonaStore(data).save(root, '你热爱讲述声音、时间与日常的变化，让人物的愿望获得自己的表达。', reason='作者创作意图')
        brief = SceneBrief('s1', '寻找信', '让等待可感', ('阿青',), (), (), (),
            RhythmDirective(), LengthTarget(), StyleMountRef(), SceneRisk(SceneRiskLevel.LOW), ())
        runtime = PiSceneTransactionRuntime({'application': {'scene_creator_v2': {'enabled': True}}},
            project_root=root, data_root=data, gateway=gateway)
        return runtime, brief

    def test_natural_selection_without_literal_ids_gets_only_selection_repair(self):
        class Gateway(NaturalGateway):
            def run(self, root, prompt, **kwargs):
                envelope = json.loads(prompt)
                if envelope['schema'] == 'arcvellum/scene-creator/v2' and '已提供的候选 ID' in envelope['prompt']:
                    self.creator_calls += 1
                    identifier = re.search(r'v2:[a-f0-9]+:1', self.context['material_index'])[0]
                    return RoleConversationResult('pi-worker', 'choice', 'test/model', '取舍补充：改写 ' + identifier + '，让水滴成为回应的时点。')
                if 'task_contract' in envelope['prompt']:
                    task = json.loads(envelope['prompt'])
                    if task['source_text'].startswith('取舍补充'):
                        self.extract_calls += 1
                        identifier = re.search(r'v2:[a-f0-9]+:1', task['source_text'])[0]
                        return RoleConversationResult('pi-worker', 'extract', 'test/model', json.dumps({
                            'material_decisions': [{'candidate_id': identifier, 'decision': 'adapt', 'reason': '成为回应的时点'}]}))
                result = super().run(root, prompt, **kwargs)
                if 'task_contract' in envelope['prompt']:
                    task = json.loads(envelope['prompt'])
                    if task['operation'] == 'creator' and task['source_text'].startswith(PROSE):
                        result = RoleConversationResult('pi-worker', 'wrapped-extraction', 'test/model',
                            json.dumps({'operation': 'creator', 'task_contract': json.loads(result.answer)}, ensure_ascii=False))
                if envelope['schema'] == 'arcvellum/scene-creator/v2' and self.creator_calls == 2:
                    return RoleConversationResult('pi-worker', 'draft', 'test/model', PROSE + '\n札记：改写水滴素材，让它成为回应的时点。')
                return result
        with TemporaryDirectory() as tmp:
            gateway = Gateway(); runtime, brief = self.runtime(tmp, gateway)
            result = runtime.create_scene('tx-choice', brief)
            self.assertEqual(result.prose, PROSE)
            self.assertEqual(result.scene_delta.next_handoff, ('信的去向仍待揭晓',))
            self.assertEqual((gateway.creator_calls, gateway.material_calls), (3, 1))
            runtime.create_scene('tx-choice', brief)
            self.assertEqual(gateway.creator_calls, 3)

    def test_pending_invitations_recover_missing_required_plan_before_material_call(self):
        class Gateway(NaturalGateway):
            def run(self, root, prompt, **kwargs):
                envelope = json.loads(prompt)
                if envelope['schema'] == 'arcvellum/scene-creator/v2' and '当前补充它们的取材计划' in envelope['prompt']:
                    self.creator_calls += 1
                    return RoleConversationResult('pi-worker', 'plan', 'test/model', '必用 environment。文学理由：借水声延续等待。')
                if 'task_contract' in envelope['prompt']:
                    task = json.loads(envelope['prompt'])
                    if task['operation'] == 'material-plan':
                        self.extract_calls += 1
                        return RoleConversationResult('pi-worker', 'extract-plan', 'test/model', json.dumps({
                            'material_plan': {'required_kinds': ['environment'], 'reason': '借水声延续等待'}}))
                    if task['operation'] == 'creator' and task['source_text'].startswith('本场'):
                        self.extract_calls += 1
                        return RoleConversationResult('pi-worker', 'extract-invitation', 'test/model', json.dumps({'material_requests': [REQUEST]}, ensure_ascii=False))
                return super().run(root, prompt, **kwargs)
        with TemporaryDirectory() as tmp:
            gateway = Gateway(); runtime, brief = self.runtime(tmp, gateway)
            result = runtime.create_scene('tx-plan', brief)
            self.assertEqual(result.prose, PROSE)
            self.assertEqual((gateway.creator_calls, gateway.material_calls), (3, 1))
            plan = Path(tmp) / 'data/scene-transactions/tx-plan/v2/material_plan.json'
            self.assertEqual(json.loads(plan.read_text(encoding='utf-8'))['required_kinds'], ['environment'])

    def test_unconfirmed_mapping_still_blocks_and_body_mutation_is_rejected(self):
        self.assertIn('需要核对', material_selection_error({'material_selection_pending': '需要核对', 'material_decisions': []}, ['v2:abc:1'], [{'candidate_id': 'v2:abc:1', 'decision': 'use'}]))
        with TemporaryDirectory() as tmp:
            processor = NaturalOutputProcessor(Path(tmp), '整理', lambda *args: json.dumps({
                'prose': '整理器改写了正文', 'decision_summary': '采用水声',
                'material_decisions': [{'candidate_id': 'v2:abc:1', 'decision': 'use'}]}, ensure_ascii=False))
            with self.assertRaisesRegex(ValueError, 'changed prose'):
                processor.process(PROSE, kind='creator', context={'material_index': 'v2:abc:1'})
