from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from literary_engineering_studio.application.creator_persona import CreatorPersonaStore
from literary_engineering_studio.runtimes.scene_creator_briefing import build_scene_creator_briefing
from literary_engineering_studio.runtimes.scene_creator_workspace import SceneCreatorWorkspace
from literary_engineering_studio.runtimes.runtime_model_identity import runtime_model_identity
from literary_engineering_studio.runtimes.natural_transport_task import extraction_task
from literary_engineering_studio.runtimes.style_choice_prompt import style_choice_prompt, reference_source_summary
from literary_engineering_studio.runtimes.material_usage_evidence import save_material_usage_audit
from literary_engineering_studio_engine.public.projects import InitOptions, init_work_project
from tests.runtimes.test_less_ai_tone_experiment import brief, runtime


def common_prefix(first, second):
    return next((i for i, (a, b) in enumerate(zip(first, second)) if a != b), min(len(first), len(second)))


class CreationContextIntegrityTests(unittest.TestCase):
    def test_full_previous_sources_preserve_early_facts_and_pending_status(self):
        with TemporaryDirectory() as directory:
            root = Path(directory); project = root / 'project'
            init_work_project(InitOptions(project, title='连续性来源合同测试'))
            sources = {'drafts/scenes/s1.md': '开头确立三口缸。' + '长段叙述。' * 1200 + '结尾有脚步。',
                       'workflow/scene_deltas/s1.json': json.dumps({'canon_candidates': ['前段事实'], 'next_handoff': ['交接']}, ensure_ascii=False),
                       'canon/facts.json': json.dumps({'facts': [{'statement':'已确认'}],
                           'candidates':[{'statement':'待确认的传言','status':'pending_confirmation'}]},ensure_ascii=False)}
            for name, text in sources.items():
                path = project / name; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(text,encoding='utf-8')
            store = CreatorPersonaStore(root / 'data'); store.save(project, '用鲜明的人物声音组织生活与长期记忆。' * 4,reason='连续性合同回归测试')
            packet = build_scene_creator_briefing(replace(brief(), source_refs=tuple(sources)), SceneCreatorWorkspace(project,root/'data'),store)
            previous = next(row for row in packet['source_entries'] if row['name']=='previous_committed_prose')
            self.assertEqual(previous['content'],sources['drafts/scenes/s1.md']); self.assertTrue(previous['complete'])
            canon = packet['canon_sources'][0]
            self.assertEqual(json.loads(canon['content'])['candidates'][0]['status'],'pending_confirmation')
            self.assertTrue(canon['complete'])
            self.assertEqual(canon['file_sha256'],sha256((project/'canon/facts.json').read_bytes()).hexdigest())

    def test_record_repairs_keep_source_prefix_and_all_requested_fields(self):
        source = '同一份必须完整保留的原文。' * 500
        context = {'prose': '正文', 'target': '甲'}
        index = {'sha256':'a'*64,'blocks':[{'id':'b1','beginning':0,'ending':len(source)}]}
        contract = {'changes': [], 'reason':'原作者判断'}
        first = extraction_task('tone',contract,context,index,source,{}, {},paths=['/changes'],issue='first')
        second = extraction_task('tone',contract,context,index,source,{}, {},paths=['/reason'],issue='second')
        self.assertEqual(first['source_text'],source)
        self.assertEqual(second['task_contract'],{'reason':'原作者判断'})
        self.assertGreater(common_prefix(json.dumps(first,ensure_ascii=False),json.dumps(second,ensure_ascii=False)),len(source))

    def test_style_catalog_precedes_changing_scene_without_dropping_references(self):
        catalog = {'revision':1,'reference_catalog':{'references':[{'unit_id':'S1','source_title':'作品甲','text':'完整样段。'*300}]},'presets':[]}
        original = deepcopy(catalog)
        first = style_choice_prompt(brief(),catalog)
        second = style_choice_prompt(replace(brief(),scene_id='next'),catalog)
        self.assertGreater(common_prefix(first,second),len('完整样段。'*300))
        self.assertEqual(catalog,original)
        self.assertEqual(reference_source_summary(catalog)['作品甲']['units'],1)

    def test_model_and_endpoint_changes_invalidate_but_price_updates_do_not(self):
        with TemporaryDirectory() as directory:
            root=Path(directory); definition={'id':'model-a','reasoning':False,'maxTokens':100,'contextWindow':1000,'cost':{'input':1}}
            models={'providers':{'custom':{'api':'openai-completions','baseUrl':'https://first.test/v1','models':[definition]}}}
            path=root/'models.json'; path.write_text(json.dumps(models),encoding='utf-8')
            config={'agent_runners':{'pi-worker':{'model':'custom/model-a','auth_path':str(root/'auth.json')}}}
            before=runtime_model_identity(config)
            definition['cost']['input']=2; path.write_text(json.dumps(models),encoding='utf-8')
            self.assertEqual(runtime_model_identity(config),before)
            models['providers']['custom']['baseUrl']='https://second.test/v1'; path.write_text(json.dumps(models),encoding='utf-8')
            self.assertNotEqual(runtime_model_identity(config),before)
            config['agent_runners']['pi-worker']['model']='custom/model-b'
            self.assertNotEqual(runtime_model_identity(config),before)

    def test_new_transaction_rejects_a_model_switch_before_returning_cached_result(self):
        with TemporaryDirectory() as directory:
            adapter=runtime(Path(directory)); adapter._v2_prompt_snapshot('frozen-model')
            adapter._config.setdefault('agent_runners',{}).setdefault('pi-worker',{})['model']='different/model'
            with self.assertRaisesRegex(RuntimeError,'model binding changed'):
                adapter._v2_context('frozen-model',brief())

    def test_usage_audit_rechecks_current_body_and_keeps_original_choice_evidence(self):
        with TemporaryDirectory() as directory:
            root=Path(directory); library=root/'materials'; library.mkdir()
            (library/'index.json').write_text(json.dumps({'entries':[{'candidate_id':'a','file':'a.json'},{'candidate_id':'b','file':'b.json'}]}),encoding='utf-8')
            (library/'a.json').write_text(json.dumps({'content':{'text':'原材料片段'}}),encoding='utf-8')
            decisions=[{'candidate_id':'a','decision':'adapt','reason':'人物声音','source_excerpt':'原材料','prose_excerpt':'旧正文'}]
            original=deepcopy(decisions)
            report=save_material_usage_audit('新正文',library,decisions,root/'audit')
            self.assertEqual(decisions,original)
            self.assertFalse(report['decisions'][0]['prose_excerpt_verified'])
            self.assertEqual(report['unjudged_candidate_ids'],['b'])
            self.assertEqual(report['evidence_counts'],{'anchors-unverified':1})


if __name__=='__main__':
    unittest.main()
