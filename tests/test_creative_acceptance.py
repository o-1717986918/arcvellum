"""Meaningful regression for acceptance fixtures, replay billing, budget and report safety."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tests.acceptance.creative_cases import CASES, prepare_case
from tests.acceptance.creative_ledger import AcceptanceGateway, AcceptanceBudgetReached, summarize_calls
from tests.acceptance.creative_report import readable_report
from tests.acceptance.creative_lease import case_lease
from tests.acceptance.creative_evidence import failures


class CreativeAcceptanceTests(unittest.TestCase):
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
