"""Meaningful regression for acceptance fixtures, replay billing, budget and report safety."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tests.acceptance.creative_cases import CASES, prepare_case
from tests.acceptance.creative_ledger import AcceptanceGateway, AcceptanceBudgetReached, summarize_calls
from tests.acceptance.creative_report import readable_report
from tests.acceptance.creative_lease import case_lease
from tests.acceptance.creative_evidence import failures


class CreativeAcceptanceTests(unittest.TestCase):
    def test_editor_separate_system_argument_is_classified_for_cost_reporting(self):
        from tests.acceptance.creative_ledger import invocation_phase
        self.assertEqual(invocation_phase(('project','请回看本场正文'),
            {'system_prompt':'文学编辑\n【十一种局部观察】'},'revision-needed'),'tone.revision-needed')

    def test_style_gate_rewrites_count_as_literary_and_review_on_same_draft_is_one_revision(self):
        from tests.acceptance.creative_runner import literary_revisions
        with TemporaryDirectory() as tmp:
            folder = Path(tmp); evidence = folder / 'evidence/scene_0001'; evidence.mkdir(parents=True)
            for index, code in enumerate(('style-mechanical-contrast-frame', 'punctuation-western-quotes-in-chinese', 'punctuation-dash-overuse')):
                (evidence / f'verify-{index}.json').write_text(json.dumps({'issues': [{'code': code, 'severity': 'hard'}]}), encoding='utf-8')
            (evidence / 'review-0.json').write_text(json.dumps({'decision': 'revise'}), encoding='utf-8')
            self.assertEqual(literary_revisions(folder, 'scene_0001', 3), 2)
            self.assertEqual(literary_revisions(folder, 'scene_0001', 1), 1)

    def test_new_persona_template_gets_new_cache_while_matching_comparison_reuses_source(self):
        from tests.acceptance.creative_runner import ensure_persona
        with TemporaryDirectory() as tmp:
            parent = Path(tmp) / 'fantasy-world'
            parent.mkdir()
            legacy = parent / 'persona.json'
            legacy.write_text(json.dumps({'text': '旧模板的细节与对白偏好人格'}), encoding='utf-8')
            calls = []
            class Gateway:
                def run(self, *args, **kwargs):
                    calls.append(args)
                    return SimpleNamespace(answer='你热爱开阔的世界讲述，愿意让风俗、岁月与群体经验充分展开。', run_id='real-port-test', model='test')
            gateway = Gateway()
            spec = SimpleNamespace(default_text='第一版正向人格模板', package_version=1)
            with patch('tests.acceptance.creative_runner.prompt_layer_spec', return_value=spec):
                for variant in ('first', 'comparison'):
                    folder = parent / variant
                    project = prepare_case(folder, 'fantasy-world')
                    container = SimpleNamespace(config={'application': {'data_root': str(folder / 'data')}})
                    ensure_persona(container, gateway, project, folder, 'fantasy-world')
                self.assertEqual(len(calls), 1)
                spec.default_text = '新版世界、抒情与时间人格模板'
                spec.package_version = 2
                folder = parent / 'new-template'
                project = prepare_case(folder, 'fantasy-world')
                container = SimpleNamespace(config={'application': {'data_root': str(folder / 'data')}})
                ensure_persona(container, gateway, project, folder, 'fantasy-world')
                self.assertEqual(len(calls), 2)
                ensure_persona(container, gateway, project, folder, 'fantasy-world')
                self.assertEqual(len(calls), 2)
            self.assertEqual(len(list(parent.glob('persona-*.json'))), 2)
            self.assertEqual(json.loads(legacy.read_text(encoding='utf-8'))['text'], '旧模板的细节与对白偏好人格')

    def test_later_scene_failure_is_not_assigned_to_a_committed_earlier_scene(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / 'worker/runs/later'; run.mkdir(parents=True)
            (run/'conversation.prompt.md').write_text(json.dumps({'material_root':'data/scene-transactions/tx-later/v2'}), encoding='utf-8')
            (run/'runtime.output.log').write_text(json.dumps({'event':'runner.worker.result','data':{
                'status':'blocked','providerError':'terminated','failureKind':'transient_network'}}), encoding='utf-8')
            self.assertEqual(failures(root,'tx-earlier'),[])
            self.assertEqual(failures(root,'tx-later')[0]['failure_kind'],'transient_network')

    def test_concurrent_writer_is_rejected_before_second_model_work(self):
        with TemporaryDirectory() as tmp:
            with case_lease(Path(tmp)):
                with self.assertRaisesRegex(RuntimeError,'已有验收进程'):
                    with case_lease(Path(tmp)):
                        self.fail('lease should reject the second writer')
            with case_lease(Path(tmp)):
                pass
    def test_four_original_two_scene_cases_are_resumable_and_do_not_seed_prose(self):
        with TemporaryDirectory() as tmp:
            for name, case in CASES.items():
                root = prepare_case(Path(tmp)/name, name)
                self.assertEqual(len(list((root/'scenes').glob('*.yaml'))),2)
                self.assertGreaterEqual(len(case['people']),2)
                self.assertFalse(list((root/'drafts/scenes').glob('*.md')))
                self.assertEqual(root,prepare_case(Path(tmp)/name,name))

    def test_replayed_usage_is_not_charged_twice_and_missing_cost_is_disclosed(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/'calls.jsonl'
            rows=[{'phase':'review','role':'reviewer','seconds':1,'usage_events':[{'usage_id':'one','usage':{'total_tokens':10},'cost_usd':0.1}]}]*2
            rows += [{'phase':'create','role':'worker','seconds':2,'usage_events':[{'usage_id':'two','usage':{'total_tokens':20}}]}]
            path.write_text('\n'.join(json.dumps(row) for row in rows),encoding='utf-8')
            cost=summarize_calls(path)
            self.assertEqual(cost['reported_cost_usd'],0.1)
            self.assertEqual(cost['distinct_usage_updates'],2)
            self.assertEqual(cost['missing_usage'],1)
            self.assertEqual(cost['groups']['review:reviewer']['tokens'],10)

    def test_budget_prevents_another_real_invocation(self):
        class Gateway:
            def run(self,*args,**kwargs):
                raise RuntimeError('failure')
        with TemporaryDirectory() as tmp:
            gateway=AcceptanceGateway(Gateway(),Path(tmp),max_calls=1)
            with self.assertRaisesRegex(RuntimeError,'failure'):
                gateway.run(Path(tmp),'probe',role='worker')
            with self.assertRaises(AcceptanceBudgetReached):
                gateway.run(Path(tmp),'probe',role='worker')
            self.assertEqual(summarize_calls(gateway.path)['invocations'],1)

    def test_unbudgeted_acceptance_preserves_real_call_and_usage_records(self):
        class Gateway:
            def run(self, *args, **kwargs):
                kwargs['event_sink']('usage.updated', {
                    'usage_id': 'arcvellum-conversation-' + str(args[1]),
                    'usage': {'total_tokens': 10}, 'cost_usd': .01,
                })
                return SimpleNamespace(run_id=str(args[1]), model='test')
        with TemporaryDirectory() as tmp:
            gateway = AcceptanceGateway(Gateway(), Path(tmp), max_calls=None, max_minutes=None)
            for index in range(3):
                gateway.run(Path(tmp), str(index), role='transport')
            result = summarize_calls(gateway.path)
            self.assertEqual(result['invocations'], 3)
            self.assertEqual(result['distinct_usage_updates'], 3)
            self.assertAlmostEqual(result['reported_cost_usd'], .03)

    def test_same_prompt_reexecuted_is_a_new_charge_even_with_legacy_usage_id(self):
        with TemporaryDirectory() as tmp:
            row={'phase':'transport','role':'reviewer','seconds':1,'usage_events':[{'usage_id':'legacy','usage':{'total_tokens':10},'cost_usd':0.1}]}
            second={**row,'seconds':2,'batch_id':'second'}
            path=Path(tmp)/'calls.jsonl'
            path.write_text(json.dumps(row)+'\n'+json.dumps(second),encoding='utf-8')
            self.assertEqual(summarize_calls(path)['reported_cost_usd'],0.2)

    def test_report_preserves_prose_as_text_and_does_not_assert_literary_success(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp); folder=root/'daily/baseline'; folder.mkdir(parents=True)
            prose=folder/'prose.md'; prose.write_text('<script>alert(1)</script>',encoding='utf-8')
            (folder/'acceptance.json').write_text(json.dumps({'case_id':'daily','variant':'baseline','status':'needs-analysis','scenes':[{'scene_id':'one','status':'revision-needed','prose_path':str(prose)}]}),encoding='utf-8')
            html=readable_report(root).read_text(encoding='utf-8')
            self.assertIn('&lt;script&gt;',html)
            self.assertNotIn('<script>alert',html)
            self.assertIn('文学结论待细读',html)

    def test_runtime_usage_recovery_across_invocations_is_one_charge(self):
        with TemporaryDirectory() as tmp:
            usage = {'usage_id': 'arcvellum-conversation-run-attempt-1', 'usage': {'total_tokens': 15}, 'cost_usd': .2}
            rows = [{'phase': 'create', 'role': 'worker', 'seconds': 1, 'invocation_id': ident, 'status': 'completed', 'usage_events': [usage]} for ident in ('first', 'recovery')]
            rows.append({'phase': 'create', 'role': 'worker', 'seconds': 2, 'invocation_id': 'failed', 'status': 'failed',
                         'usage_events': [{'usage_id': 'arcvellum-conversation-error-attempt-1', 'usage': {'total_tokens': 0}, 'cost_usd': 0}]})
            path = Path(tmp)/'calls.jsonl'; path.write_text('\n'.join(json.dumps(row) for row in rows), encoding='utf-8')
            cost = summarize_calls(path)
            self.assertEqual(cost['reported_cost_usd'], .2)
            self.assertEqual(cost['groups']['create:worker']['tokens'], 15)
            self.assertEqual(cost['missing_usage'], 1)
