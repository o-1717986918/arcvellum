from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from literary_engineering_studio_engine.public.literary import CONSISTENCY_CONTRACT
from literary_engineering_studio.runtimes.scene_natural_output import NaturalOutputProcessor
from literary_engineering_studio.runtimes.scene_integrity import (
    validate_current_material_choices, current_review_context, save_consistency_record, checked_creation_cache,
)
from literary_engineering_studio.runtimes.natural_field_repair import apply_field_patch, field_repair_task
from literary_engineering_studio.runtimes.evidence_patch_source import resolve_evidence_patches, prose_evidence_source
from literary_engineering_studio.runtimes.natural_transport_repair import NaturalSourceClarificationError
from literary_engineering_studio.runtimes.material_need import related_candidates, validate_need
from tests.test_scene_consistency_contract import creator, review


class CurrentCreationIntegrityTests(unittest.TestCase):
    def test_source_field_repair_stops_after_four_distinct_failed_values(self):
        from literary_engineering_studio.runtimes.natural_repair_progress import SourceRepairProgress
        progress=SourceRepairProgress()
        for index in range(4):
            error=NaturalSourceClarificationError('仍无准确证据',fields=('/scene_delta',),
                payload={'scene_delta':{'canon_candidates':[{'summary':str(index)}]}})
            progress.register(error)
        with self.assertRaises(NaturalSourceClarificationError):
            progress.register(NaturalSourceClarificationError('仍无准确证据',fields=('/scene_delta',),
                payload={'scene_delta':{'canon_candidates':[{'summary':'第五次'}]}}))

    def test_direct_author_field_reply_is_used_locally_and_revalidated(self):
        row=creator();body=row.pop('prose');row['scene_delta']=[{'summary':'未分组'}]
        source='本轮阶段：完成正文\n\n## 正文\n'+body+'\n\n## 创作札记\n```json\n'+json.dumps({'creator_record':row},ensure_ascii=False)+'\n```'
        context={'creation_integrity_contract':CONSISTENCY_CONTRACT,
                 'briefing':{'scene_brief':{'participants':['许钉']}},'eligible_actors':['许钉']}
        with TemporaryDirectory() as temporary:
            processor=NaturalOutputProcessor(Path(temporary),'transport',lambda *_:self.fail('direct author reply needs no formatter'))
            with self.assertRaises(NaturalSourceClarificationError) as caught:
                processor.process(source,kind='creator',context=context)
            self.assertEqual(caught.exception.fields,('/scene_delta',))
            reply='```json\n'+json.dumps({'scene_delta':{}},ensure_ascii=False)+'\n```'
            first=processor.process_field_repair(source,reply,kind='creator',context=context,
                payload=caught.exception.payload,fields=caught.exception.fields)
            warm=processor.process_field_repair(source,reply,kind='creator',context=context,
                payload=caught.exception.payload,fields=caught.exception.fields)
            self.assertEqual(first['scene_delta'],{'next_handoff':[]})
            self.assertEqual(first['prose'],body)
            self.assertEqual(first['__transport']['model_calls'],0)
            self.assertEqual(warm['__transport']['mode'],'reused')

    def test_authored_preparation_with_incompatible_fields_returns_only_record_paths_to_author(self):
        row = {'material_plan': [{'partner_type': 'actor'}],
               'material_requests': [{'partner_type': 'actor', 'character': '陶婶',
                                      'invitation_text': '陶婶，请说出退碗时的第一句话。'}],
               'creative_intent': '借退碗写挽留。'}
        source = '本轮阶段：准备邀请\n\n```json\n' + json.dumps({'creator_record': row}, ensure_ascii=False) + '\n```'
        context = {'creation_integrity_contract': CONSISTENCY_CONTRACT,
                   'briefing': {'scene_brief': {'participants': ['陶婶']}},
                   'eligible_actors': ['陶婶']}
        with TemporaryDirectory() as temporary:
            processor = NaturalOutputProcessor(Path(temporary), 'transport',
                lambda *_: self.fail('the technical formatter must not invent author requests'))
            with self.assertRaises(NaturalSourceClarificationError) as caught:
                processor.process(source, kind='creator', context=context)
        self.assertEqual(caught.exception.fields,
            ('/material_requests', '/material_plan', '/creative_intent'))
        self.assertEqual(caught.exception.payload['material_requests'], row['material_requests'])
        contract = field_repair_task(source, caught.exception.payload, caught.exception.fields, context)
        self.assertEqual(contract['response_contract']['patches'][0]['path'], '/material_requests')
        self.assertIn('author_prompt', contract['response_contract']['patches'][0]['value'][0])

    def test_malformed_author_choice_is_returned_to_author_without_formatter(self):
        row=creator();body=row.pop('prose');row['decision_summary']='完成。'
        row['material_decisions']=['错误类型']
        source='## 正文\n'+body+'\n\n```json\n'+json.dumps({'creator_record':row},ensure_ascii=False)+'\n```'
        with TemporaryDirectory() as temporary:
            processor=NaturalOutputProcessor(Path(temporary),'transport',lambda *_:self.fail('author repair must stay author-owned'))
            with self.assertRaises(NaturalSourceClarificationError) as caught:
                processor.process(source,kind='creator',context={'creation_integrity_contract':CONSISTENCY_CONTRACT})
            self.assertEqual(caught.exception.fields,('/material_decisions',))

    def test_nested_review_repair_selects_current_block_and_rejects_old_hash(self):
        body='新稿第一段。\n\n新稿第二段。';source=prose_evidence_source(body)
        reference={'prose_sha256':source['sha256'],'prose_block':'p0002'}
        reply={'patches':[{'path':'/consistency_checks','value':[{'category':'space','evidence':[reference]}]}]}
        result=resolve_evidence_patches(reply,body,('/consistency_checks',))
        self.assertEqual(result['patches'][0]['value'][0]['evidence'],['新稿第二段。'])
        reference['prose_sha256']='old'
        with self.assertRaises(ValueError): resolve_evidence_patches(reply,body,('/consistency_checks',))
        task=field_repair_task('source',review(),('/strengths/0',),{
            'creation_integrity_contract':CONSISTENCY_CONTRACT,'prose':body})
        self.assertIsInstance(task['response_contract']['patches'][0]['value'],dict)

    def test_explicit_author_records_and_body_are_preserved_without_a_formatter_call(self):
        row=creator();body=row.pop('prose');row['decision_summary']='修桌子已经完成。'
        source='本轮阶段：完成正文\n\n## 正文\n'+body+'\n\n## 创作札记\n```json\n'+json.dumps({'creator_record':row},ensure_ascii=False)+'\n```'
        with TemporaryDirectory() as temporary:
            processor=NaturalOutputProcessor(Path(temporary),'transport',lambda *_:self.fail('no formatter call needed'))
            payload=processor.process(source,kind='creator',context={'creation_integrity_contract':CONSISTENCY_CONTRACT})
            self.assertEqual(payload['prose'],body)
            self.assertEqual(payload['consistency_record'],row['consistency_record'])
            self.assertEqual(payload['__transport']['model_calls'],0)

    def test_source_reviewer_can_retract_a_stale_issue_and_update_verdict_without_rewriting_body(self):
        body='他在桌边端起了碗。';old=review();old.update(decision='revise',major_issues=[{
            'title':'路径错误','evidence':body,'problem_excerpt':'走到灶台边'}])
        context={'prose':body,'creation_integrity_contract':CONSISTENCY_CONTRACT,'review_continuity':{'open_issues':[]}}
        with TemporaryDirectory() as temporary:
            processor=NaturalOutputProcessor(Path(temporary),'transport',lambda *_:self.fail('no formatter call needed'))
            source='```json\n'+json.dumps({'review_record':old},ensure_ascii=False)+'\n```'
            with self.assertRaises(NaturalSourceClarificationError) as caught: processor.process(source,kind='review',context=context)
            fixed=apply_field_patch(caught.exception.payload, {'patches':[
                {'path':'/major_issues/0','op':'remove'}, {'path':'/decision','value':'pass'},
                {'path':'/summary','value':'旧路径问题已修正。'}]}, caught.exception.fields)
            self.assertEqual(fixed['decision'],'pass');self.assertEqual(fixed['major_issues'],[])
            self.assertEqual(context['prose'],body)
            reply=json.dumps({'patches':[{'path':'/major_issues/0','op':'remove'},{'path':'/decision','value':'pass'},{'path':'/summary','value':'旧路径问题已修正。'}]},ensure_ascii=False)
            cold=processor.process_field_repair(source,reply,kind='review',context=context,payload=caught.exception.payload,fields=caught.exception.fields)
            warm=processor.process_field_repair(source,reply,kind='review',context=context,payload=caught.exception.payload,fields=caught.exception.fields)
            self.assertEqual(warm['__transport']['mode'],'reused')
            self.assertEqual(cold['__transport']['model_calls'],0)
            self.assertEqual(warm['__transport']['model_calls'],0)

    def test_history_projection_keeps_identifiers_without_old_summary_and_instructions(self):
        history={'previous':{'prose_sha256':'old','review':{'summary':'OLD','revision_instructions':['OLD']}},
                 'open_issues':[{'issue_id':'issue-1','title':'路径','evidence':'旧句','direction':'OLD'}]}
        original=deepcopy(history);projected=current_review_context(history)
        self.assertEqual(history,original);self.assertEqual(projected['open_issues'][0]['issue_id'],'issue-1')
        self.assertNotIn('OLD',json.dumps(projected))

    def test_cached_current_body_requires_matching_integrity_evidence(self):
        row=creator();snapshot={'creation_integrity_contract':CONSISTENCY_CONTRACT}
        with TemporaryDirectory() as temporary:
            root=Path(temporary)
            with self.assertRaises(RuntimeError): checked_creation_cache(row,snapshot,root)
            save_consistency_record(root,row);self.assertEqual(checked_creation_cache(row,snapshot,root),row)
            changed={**row,'prose':'改变过的正文'}
            with self.assertRaises(RuntimeError): checked_creation_cache(changed,snapshot,root)

    def test_material_choice_rechecks_current_landing_and_allows_deferral(self):
        sources={'a':{'text':'材料中的碗。'},'b':{'text':'另一材料。'}}
        row={'prose':'本稿的汤碗。','material_decisions':[{'candidate_id':'a','decision':'adapt','reason':'物件',
            'source_excerpt':'材料中的碗','prose_excerpt':'旧稿碗'}]}
        with self.assertRaises(NaturalSourceClarificationError): validate_current_material_choices(row,sources)
        row['material_decisions'][0]['prose_excerpt']='本稿的汤碗。'
        row['material_decisions'].append({'candidate_id':'b','decision':'defer','reason':'留到后场'})
        validate_current_material_choices(row,sources)

    def test_reordered_group_targets_do_not_hide_existing_related_materials(self):
        sources={'a':{'kind':'character-description','target':'陶婶、许钉','text':'手部'},
                 'b':{'kind':'character-description','target':'许钉,陶婶','text':'步态'}}
        request={'kind':'character-description','target':'许钉、陶婶'}
        self.assertEqual(related_candidates(sources,request),{'a','b'})
        need={'gap':'缺口','why_existing_insufficient':'不够','expected_use':'开头',
              'reviewed_candidate_ids':['a'],'existing_material_evidence':{'a':'手部'},'mount_reasons':{}}
        with self.assertRaises(ValueError): validate_need(need,request,set(sources),sources,complete_review=True)
        need['reviewed_candidate_ids'].append('b');need['existing_material_evidence']['b']='步态'
        validate_need(need,request,set(sources),sources,complete_review=True)
