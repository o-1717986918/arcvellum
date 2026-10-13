"""Representations observed in fresh paid acceptance; original meaning stays fixed."""
import json
import unittest
from hashlib import sha256
from literary_engineering_studio.runtimes.natural_reference_delivery import decode_reference_delivery
from literary_engineering_studio.runtimes.archive_partition_transport import require_source_partition_choice, normalize_archive_partitions
from literary_engineering_studio.runtimes.natural_transport_repair import NaturalSourceClarificationError, repair_paths

class LiveTransportRegressions(unittest.TestCase):
    def test_inherited_author_question_is_preserved_without_an_unrelated_editor_request(self):
        from literary_engineering_studio.runtimes.natural_editor_focus import recover_creator_editor_focus
        question='章末余味尚待作者确定，暂留开口。'
        payload={'prose':'铜鱼挪到第五拱。','editor_focus':[{'issue':'bad'}]}
        recover_creator_editor_focus('**继承待答的问题（editor_focus）**：'+question,payload,'creator')
        self.assertEqual(payload['editor_focus'],[])
        self.assertEqual(payload['deferred_editor_focus'][0]['issue'],question)

    def test_review_technical_fields_are_repaired_before_unrelated_semantic_quotes(self):
        from literary_engineering_studio.runtimes.scene_review_validation import validate_review_extraction
        from literary_engineering_studio.runtimes.natural_transport_repair import NaturalExtractionError
        payload={'strengths':[{'claim':'成立','evidence':'审读标题'}],
                 'issue_progress':[{'issue_id':'old','status':'resolved','evidence':'桥上的灯亮了。'}]}
        context={'prose':'桥头的灯亮了。','review_continuity':{'open_issues':[{'issue_id':'old'}]}}
        with self.assertRaises(NaturalExtractionError) as caught:
            validate_review_extraction(payload,context,'审读标题\n证据：桥上的灯亮了。')
        self.assertEqual(caught.exception.fields,('/strengths/0/evidence',))
        payload['strengths'][0]['evidence']=context['prose']
        with self.assertRaises(NaturalSourceClarificationError) as caught:
            validate_review_extraction(payload,context,'审读标题\n证据：桥上的灯亮了。')
        self.assertEqual(caught.exception.fields,('/issue_progress/0/evidence',))

    def test_number_ranges_recover_only_explicit_selected_members(self):
        from literary_engineering_studio.runtimes.natural_selection_pending import shared_prefix_source
        source='`v2:abcd:1-2,4-5`'
        self.assertEqual(shared_prefix_source(source,'v2:abcd:5')['form'],'explicit-number-range')
        self.assertIsNone(shared_prefix_source(source,'v2:abcd:3'))
        self.assertIsNone(shared_prefix_source('`v2:abcd:5-2`','v2:abcd:3'))

    def test_need_repair_receives_only_actual_reviewed_candidate_texts(self):
        from literary_engineering_studio.runtimes.material_need import repair_candidate_sources
        payload={'material_requests':[{'kind':'actor','target':'莓灯','need_evidence':{'reviewed_candidate_ids':['c1']}}]}
        sources={'c1':{'kind':'actor','target':'莓灯','text':'抬高簿子验银票。'},
                 'c2':{'kind':'environment','target':'河','text':'其他资料。'}}
        selected=repair_candidate_sources(payload,['/material_requests/0/need_evidence'],sources)
        self.assertEqual(list(selected),['c1'])
        self.assertEqual(selected['c1']['text'],sources['c1']['text'])

    def test_field_correction_feedback_is_cached_and_never_rewrites_review_or_body(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from literary_engineering_studio.runtimes.scene_creator_natural import NaturalCreatorMixin
        from literary_engineering_studio.runtimes.scene_natural_output import NaturalOutputProcessor
        from literary_engineering_studio.runtimes.natural_turn_store import NaturalTurnStore
        source='审读通过。证据：旧的字句。'
        body='新的字句。'
        frozen={'decision':'pass','summary':'审读通过','strengths':[{'claim':'节奏成立','evidence':'旧的字句。'}]}
        calls=[]
        with TemporaryDirectory() as temporary:
            root=Path(temporary)
            class Driver(NaturalCreatorMixin):
                def _preserved_natural_answer(self,_tx,kind,prompt,invoke):
                    return NaturalTurnStore(root/'originals',kind).answer(prompt,invoke)[0]
            processor=NaturalOutputProcessor(root,'transport',lambda *_:self.fail('technical model unnecessary'))
            def invoke(task):
                parsed=json.loads(task);calls.append(parsed)
                value=body if parsed.get('validation_feedback') else '旧的字句。'
                return json.dumps({'patches':[{'path':'/strengths/0/evidence','value':value}]},ensure_ascii=False)
            for _ in range(2):
                error=NaturalSourceClarificationError('引句不匹配',fields=['/strengths/0/evidence'],payload=frozen)
                result=Driver()._source_field_repair('tx',processor,source,'review',{'prose':body},error,invoke)
                self.assertEqual(result['decision'],'pass')
                self.assertEqual(result['summary'],'审读通过')
                self.assertEqual(result['strengths'][0]['evidence'],body)
            self.assertEqual(len(calls),2)
            self.assertIn('旧的字句。',calls[1]['validation_feedback']['failed_reply'])
            self.assertEqual(body,'新的字句。')

    def test_same_line_candidate_suffixes_are_supported_without_cross_line_guesses(self):
        from literary_engineering_studio.runtimes.natural_selection_pending import shared_prefix_source
        source='- `v2:abcd:7`、`:8`、`:10` — use。'
        self.assertEqual(shared_prefix_source(source,'v2:abcd:8')['source'],'v2:abcd:7`、`:8`、`:10`')
        self.assertIsNone(shared_prefix_source(source,'v2:abcd:9'))
        self.assertIsNone(shared_prefix_source('`v2:abcd:7`\n`:8`','v2:abcd:8'))

    def test_commission_text_failures_are_batched_without_reopening_complete_requests(self):
        from literary_engineering_studio.runtimes.scene_natural_output import _commission_provenance
        from literary_engineering_studio.runtimes.natural_transport_repair import NaturalExtractionError
        payload={'material_requests':[{'author_prompt':'请写河风','working_context':'被改写一'},
                                     {'author_prompt':'请写河风','working_context':'被改写二'}]}
        with self.assertRaises(NaturalExtractionError) as caught:_commission_provenance('请写河风',payload)
        self.assertEqual(caught.exception.fields,('/material_requests/0/working_context','/material_requests/1/working_context'))

    def test_formatter_does_not_open_an_editor_call_that_review_source_never_requested(self):
        from literary_engineering_studio.runtimes.natural_editor_focus import recover_creator_editor_focus
        payload={'decision':'revise','major_issues':[{'title':'收束','direction':'缩短第十节'}],
                 'editor_focus':[{'issue':'整理器自行追加的问题'}]}
        recover_creator_editor_focus('主要问题：第十节过长，缩短它。',payload,'review')
        self.assertEqual(payload['editor_focus'],[])
        self.assertEqual(payload['major_issues'][0]['direction'],'缩短第十节')
        self.assertEqual(payload['decision'],'revise')
        self.assertEqual(payload['unrequested_editor_focus'][0]['issue'],'整理器自行追加的问题')

    def test_body_with_explicit_unexecuted_invitations_is_saved_pending_without_rewriting(self):
        from literary_engineering_studio.runtimes.natural_local_delivery import local_creator_fields
        source='### 委托一 · 环境作家\n请写河风。\n\n## 正文\n铜鱼挪到了第五拱。\n\n## 创作札记\n交接。'
        pending=local_creator_fields(source,'creator',{'available_material_ids':[]})
        self.assertEqual(pending['prose'],'')
        self.assertEqual(pending['pending_body_source'],'铜鱼挪到了第五拱。')
        completed=local_creator_fields(source,'creator',{'available_material_ids':['c1']})
        self.assertEqual(completed['prose'],'铜鱼挪到了第五拱。')

    def test_bad_nested_reference_freezes_judgment_and_repairs_only_evidence(self):
        from literary_engineering_studio.runtimes.natural_reference_delivery import PartialReferenceError
        from literary_engineering_studio.runtimes.natural_transport_repair import apply_repair
        raw={'decision':'revise','summary':'节奏需要修订','strengths':[{'claim':'桥有年月',
            'evidence':{'$source':{'first_block':'b0001','start_anchor':'不存在','end_anchor':'也不存在'}}}]}
        with self.assertRaises(PartialReferenceError) as caught:decode_reference_delivery(raw,'审读原文。')
        self.assertEqual(caught.exception.paths,['/strengths/0/evidence'])
        frozen=caught.exception.payload
        result=apply_repair(frozen,{'patches':[{'path':'/strengths/0/evidence','value':'木缝里的旧果核。'}]},caught.exception.paths)
        self.assertEqual(result['summary'],raw['summary'])
        self.assertEqual(result['strengths'][0]['claim'],raw['strengths'][0]['claim'])
        self.assertEqual(result['strengths'][0]['evidence'],'木缝里的旧果核。')

    def test_wrong_block_numbers_recover_only_with_two_unique_same_original_anchors(self):
        source='审读标题\n引文：铜鱼挪到了第五拱。\n其他判断。'
        ref={'first_block':'b0001','last_block':'b0001','start_anchor':'铜鱼挪','end_anchor':'第五拱。'}
        raw={'evidence':{'$source':ref}}
        result=decode_reference_delivery(raw,source)
        self.assertEqual(result['evidence'],'铜鱼挪到了第五拱。')
        self.assertEqual(result['source_block_recovery'][0]['corrected_first'],'b0002')
        with self.assertRaises(ValueError):decode_reference_delivery({**raw,'source_sha256':'0'*64},source)
        with self.assertRaises(ValueError):decode_reference_delivery(raw,source+'\n铜鱼挪到了第五拱。')

    def test_review_blank_line_format_recovers_exact_body_without_changing_judgment(self):
        from literary_engineering_studio.runtimes.commission_source_format import restore_review_evidence
        body='河底那条鱼没有动。\n\n它绿着。'
        payload={'strengths':[{'claim':'余韵干净','evidence':body.replace('\n\n','\n')}]}
        restore_review_evidence(body,payload)
        self.assertEqual(payload['strengths'][0]['evidence'],body)
        self.assertEqual(payload['review_format_recovery'][0]['body_start'],0)

    def test_review_recovery_uses_verified_legacy_prompt_and_invalidates_on_context_changes(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from literary_engineering_studio.runtimes.natural_turn_store import NaturalTurnStore
        from literary_engineering_studio.runtimes.natural_review_recovery import saved_review_answer,review_context_digest
        with TemporaryDirectory() as temporary:
            tx=Path(temporary);journal=NaturalTurnStore(tx/'v2/literary-originals','review')
            context={'prose':'铜鱼挪到了第五拱。','material_index':['c1'],'style':'热情','review_continuity':{}}
            prompt='protocol\n\n本次审读资料：\n'+json.dumps(context,ensure_ascii=False)
            source='结论：返修。原判断已保存。'
            journal.answer('system'+prompt,lambda:source)
            journal.reject('system'+prompt,ValueError('引句错误'))
            (tx/'sent-prompts').mkdir()
            (tx/'sent-prompts/original.json').write_text(json.dumps({'role':'reviewer','prompt':json.dumps({'system_prompt':'system','prompt':prompt})}),encoding='utf-8')
            self.assertEqual(saved_review_answer(journal,'system','protocol',{**context,'delivery_feedback':{}}),source)
            for changed in ({**context,'prose':'第二稿。'},{**context,'style':'冷峻'},{**context,'material_index':['c2']}):
                self.assertIsNone(saved_review_answer(journal,'system','protocol',changed))
            journal.reject('changed',ValueError('仅字段'),answer=source,context_digest=review_context_digest('system','protocol',context))
            self.assertEqual(saved_review_answer(journal,'system','protocol',context),source)
            self.assertIsNone(saved_review_answer(journal,'system','new-contract',context))

    def test_inline_editor_note_stays_saved_without_requiring_a_whole_body_edit(self):
        from literary_engineering_studio.runtimes.natural_editor_focus import recover_creator_editor_focus
        issue='对白只作亮点；抒情段落保留长呼吸。'
        payload={'prose':'月亮降到屋檐。','editor_focus':[{'issue':'bad'}]}
        recover_creator_editor_focus('正文。\n**editor_focus（继续把守）。** '+issue,payload,'creator')
        self.assertEqual(payload['editor_focus'],[])
        self.assertEqual(payload['deferred_editor_focus'][0]['issue'],issue)

    def test_decorated_selected_reference_labels_recover_all_literal_available_ids(self):
        from literary_engineering_studio.runtimes.creator_delivery_labels import recover_style_reference_ids
        value='**R18（酒馆/密谈）**：取热闹中的暗流。'
        payload={'reference_ids':[value,value]}
        recover_style_reference_ids(value,payload,{'reference_ids':['R18']})
        self.assertEqual(payload['reference_ids'],['R18'])

    def test_review_commentary_cites_only_unique_explicit_body_quote_and_keeps_full_comment(self):
        from literary_engineering_studio.runtimes.commission_source_format import restore_review_evidence
        body='浮月镇的夏末，是从月光变酸开始的。'
        comment='“'+body+'”这句开场使世界有了身体感。'
        payload={'strengths':[{'claim':'世界可感','evidence':comment}]}
        restore_review_evidence(body,payload)
        self.assertEqual(payload['strengths'][0]['evidence'],body)
        self.assertEqual(payload['review_format_recovery'][0]['original'],comment)
        self.assertEqual(payload['strengths'][0]['claim'],'世界可感')

    def test_review_bad_evidence_repairs_all_bad_quotes_without_reopening_judgments(self):
        from literary_engineering_studio.runtimes.scene_review_validation import validate_review_extraction
        payload={'decision':'revise','summary':'原判断','strengths':[{'claim':'桥有年月','evidence':'没有这句'}],
                 'major_issues':[{'title':'节奏','evidence':'也没有这句'}]}
        with self.assertRaises(NaturalSourceClarificationError) as caught:
            validate_review_extraction(payload,{'prose':'木缝里嵌着旧果核。'},'{"evidence":"没有这句"}\n{"evidence":"也没有这句"}')
        self.assertEqual(caught.exception.fields,('/strengths/0/evidence','/major_issues/0/evidence'))
        self.assertEqual(caught.exception.payload['summary'],'原判断')

    def test_technical_preface_unique_json_recovers_but_two_blocks_do_not(self):
        from literary_engineering_studio.runtimes.natural_transport_pipeline import _extraction_payload
        source='记录如下。\n```json\n{"editor_focus":[]}\n```\n记录已保留。'
        self.assertEqual(_extraction_payload(source),{'editor_focus':[]})
        with self.assertRaises(ValueError):_extraction_payload(source+'\n```json\n{"editor_focus":[1]}\n```')

    def test_explicit_editor_notes_keep_source_and_defer_unanchored_questions(self):
        from literary_engineering_studio.runtimes.scene_natural_output import validate_extracted_text
        body='攒姓是他一生的愿望。船什么时候开？'
        source=body+'\n\n## editor_focus（局部问题）\n1. **字义**：保留“攒姓”，不能改成攒盘缠。\n2. 群像节奏须复查。\n\n---\n交接。'
        payload={'prose':body,'material_requests':[],'editor_focus':{'wrong':True}}
        validate_extracted_text(source,payload,'creator')
        self.assertEqual(payload['editor_focus'][0]['excerpt'],'攒姓')
        self.assertIn('**字义**',payload['editor_focus'][0]['issue'])
        self.assertEqual(payload['deferred_editor_focus'][0]['issue'],'群像节奏须复查。')
        self.assertEqual(payload['prose'],body)

    def test_empty_revision_intention_keeps_prior_but_initial_or_partial_invalid_still_fails(self):
        from literary_engineering_studio.runtimes.scene_creator_memory import SceneCreatorMemoryV1
        from literary_engineering_studio_engine.public.literary import CreativeIntentV1
        original=CreativeIntentV1('桥上的复调','铜鱼在第五拱','倒影误认','后续钩子',2)
        empty={key:'' for key in ('reader_experience','reader_knows','reader_misreads','withheld')}
        memory=SceneCreatorMemoryV1('s',intent=original,intent_source='creator')
        memory.record_creator({'creative_intent':empty},None,prompt='返修沿用意图')
        self.assertEqual(memory.intent,original)
        self.assertEqual(memory.intent_source,'creator')
        with self.assertRaises(ValueError):
            SceneCreatorMemoryV1('s').record_creator({'creative_intent':empty},None,prompt='首次交付')
        with self.assertRaises(ValueError):
            memory.record_creator({'creative_intent':{**empty,'reader_knows':'新的事实'}},None,prompt='非法部分更新')

    def test_sdk_attempt_events_survive_runtime_projection_and_secret_filtering(self):
        from literary_engineering_studio.runtimes.pi_worker import PiWorkerRuntime
        runtime=PiWorkerRuntime.__new__(PiWorkerRuntime)
        for suffix in ('started','completed','failed'):
            name='runner.http.attempt.'+suffix
            events=runtime.normalize_output_line(json.dumps({'event':name,'data':{
                'http_attempt_id':'attempt-1','model_request_id':'request-1','status':200,'api_key':'secret'}}))
            self.assertEqual(events[0][0],name)
            self.assertEqual(events[0][1]['http_attempt_id'],'attempt-1')
            self.assertNotIn('api_key',events[0][1])

    def test_encoded_nested_reference_resolves_exact_original_and_hash(self):
        source='月亮贴近屋檐。'
        raw={'source_sha256':sha256(source.encode()).hexdigest(),
             'literary_mode':json.dumps({'$source':{'first_block':'b0001','last_block':'b0001'}})}
        self.assertEqual(decode_reference_delivery(raw,source)['literary_mode'],source)
        raw['source_sha256']='0'*64
        with self.assertRaises(ValueError):decode_reference_delivery(raw,source)

    def test_literal_or_unrecognized_json_is_not_reinterpreted(self):
        literal='{"$source":{"first_block":"b0001"}}'
        self.assertEqual(decode_reference_delivery({'prose':literal},literal)['prose'],literal)
        unknown='{"text":"新文学判断"}'
        self.assertEqual(decode_reference_delivery({'reason':unknown},'原文')['reason'],unknown)
        duplicate='{"$source":{"first_block":"b0001","first_block":"b0002"}}'
        self.assertEqual(decode_reference_delivery({'reason':duplicate},'原文')['reason'],duplicate)

    def test_explicit_partition_alias_is_accepted_but_ambiguity_stays_blocked(self):
        payload={'material_requests':[{'kind':'actor','archive_attachments':[
            {'path':'a','knowledge':'角色可知'},{'path':'b','knowledge':'参考'}]}]}
        require_source_partition_choice('角色可知；参考',payload)
        result=normalize_archive_partitions(payload)
        self.assertEqual([x['knowledge'] for x in result['material_requests'][0]['archive_attachments']],['known','reference'])
        self.assertEqual(len(result['attachment_partition_recovery']),2)
        payload={'material_requests':[{'kind':'actor','archive_attachments':[{'path':'a','knowledge':'角色可知/扮演参考'}]}]}
        with self.assertRaises(NaturalSourceClarificationError):require_source_partition_choice('角色可知/扮演参考',payload)

    def test_style_annotation_repair_is_fields_only(self):
        self.assertEqual(repair_paths({'literary_mode':'错误','reason':'保留'},'extraction changed literary_mode; original natural text is preserved'),['/literary_mode'])
        self.assertEqual(repair_paths({'prose':'保留'},'unknown failure'),[])

    def test_source_label_rationale_is_kept_and_all_ambiguities_share_one_task(self):
        payload={'material_requests':[{'kind':'actor','archive_attachments':[
            {'path':'a','knowledge':'参考：铜靴的来话方式'},
            {'path':'b','knowledge':'已知：他听说了风俗'}]}]}
        require_source_partition_choice('参考：铜靴的来话方式；已知：他听说了风俗',payload)
        result=normalize_archive_partitions(payload)
        self.assertEqual([x['knowledge'] for x in result['material_requests'][0]['archive_attachments']],['reference','known'])
        payload={'material_requests':[{'kind':'actor','archive_attachments':[
            {'path':'a','knowledge':'角色可知/扮演参考'},{'path':'b','knowledge':'未知'}]}]}
        try:require_source_partition_choice('角色可知/扮演参考；未知',payload)
        except NaturalSourceClarificationError as error:self.assertEqual(len(error.fields),2)
        else:self.fail('ambiguous partitions need the author')

    def test_source_selected_decorated_references_restore_only_explicit_ids(self):
        from literary_engineering_studio.runtimes.creator_delivery_labels import recover_style_reference_ids
        payload={'reference_ids':['**R09**','**S01/S02**']}
        recover_style_reference_ids('参照：**R09**、**S01/S02**',payload,{'reference_ids':['R09','S01','S02']})
        self.assertEqual(payload['reference_ids'],['R09','S01','S02'])
        for value in ('**R09/R10**','R09R11','**R09**'):
            payload={'reference_ids':[value]}
            recover_style_reference_ids('R09R11 **R09/R10**',payload,{'reference_ids':['R09','R11']})
            self.assertEqual(payload['reference_ids'],[value])

    def test_semantic_replay_freezes_the_actual_original_despite_prompt_change(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from literary_engineering_studio.runtimes.natural_turn_store import NaturalTurnStore
        with TemporaryDirectory() as temp:
            journal=NaturalTurnStore(Path(temp),'creator')
            source='已保存的委托原文。'
            error=NaturalSourceClarificationError('明确知识分区',fields=['/material_requests/0'])
            journal.reject('新上下文提示',error,answer=source)
            self.assertEqual(journal.feedback()['previous_answer'],source)
            self.assertEqual(journal.feedback()['recovery']['source_sha256'],sha256(source.encode()).hexdigest())

    def test_need_errors_are_batched_and_archive_paths_are_not_candidate_ids(self):
        from literary_engineering_studio.runtimes.material_need import require_source_needs
        from literary_engineering_studio.runtimes.natural_field_repair import field_repair_task
        need={'gap':'缺口','why_existing_insufficient':'不足','expected_use':'用途',
            'reviewed_candidate_ids':['canon/a.yaml'],'existing_material_evidence':{'canon/a.yaml':'原文'},'mount_reasons':{}}
        payload={'material_requests':[{'kind':'environment','need_evidence':need},{'kind':'event-narration','need_evidence':need}]}
        try:require_source_needs('缺口；不足；用途',payload,{'material_need_contract':'v1','available_material_ids':[]})
        except NaturalSourceClarificationError as error:
            self.assertEqual(len(error.fields),2)
            task=field_repair_task('原文',payload,error.fields,{'available_material_ids':[]})
            self.assertEqual(task['context']['available_material_ids'],[])
            self.assertIn('编号不是素材候选',task['context']['candidate_id_contract'])
        else:self.fail('archive paths cannot act as material candidate ids')

    def test_style_list_format_restores_only_unique_exact_lines(self):
        from literary_engineering_studio.runtimes.creator_delivery_labels import recover_style_list_format
        source='- 主预设：甲。\n- 辅预设：乙。'
        payload={'literary_mode':'主预设：甲。\n辅预设：乙。'}
        recover_style_list_format(source,payload)
        self.assertEqual(payload['literary_mode'],source)
        payload={'literary_mode':'主预设：甲。\n辅预设：丙。'}
        recover_style_list_format(source,payload)
        self.assertEqual(payload['literary_mode'],'主预设：甲。\n辅预设：丙。')

    def test_saved_partial_fields_are_merged_before_zero_call_recovery(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from literary_engineering_studio.runtimes.natural_transport_pipeline import NaturalTransportPipeline
        with TemporaryDirectory() as temp:
            source='原文'
            root=Path(temp); folder=root/'natural-answers'/sha256(source.encode()).hexdigest()
            folder.mkdir(parents=True)
            (folder/'old.partial.json').write_text(json.dumps({'payload':{'prose':source,'editor_focus':[{'wrong':True}]},'paths':['/editor_focus']}),encoding='utf-8')
            (folder/'old.extraction-2.md').write_text('{"editor_focus":[]}',encoding='utf-8')
            def prepare(answer,payload,kind,context):
                if payload.get('prose')!=source or payload.get('editor_focus')!=[]:raise ValueError('invalid')
                return payload
            pipe=NaturalTransportPipeline(root,'system',lambda *_:self.fail('no extra calls'),prepare,{'creator':{}})
            self.assertEqual(pipe.process(source,'creator',{},reuse_only=True)['prose'],source)

    def test_field_replay_keeps_preparers_merged_payload_for_next_failure(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from literary_engineering_studio.runtimes.natural_transport_pipeline import NaturalTransportPipeline
        with TemporaryDirectory() as temp:
            source='作者说：修分区。'
            folder=Path(temp)/'natural-answers'/sha256(source.encode()).hexdigest();folder.mkdir(parents=True)
            (folder/'prior.extraction-1.md').write_text('{"patches":[{"path":"/knowledge","value":"known"}]}',encoding='utf-8')
            merged={'material_requests':[{'knowledge':'known'}]}
            def prepare(*_):raise NaturalSourceClarificationError('补需求',fields=['/material_requests/0/need_evidence'],payload=merged)
            pipe=NaturalTransportPipeline(Path(temp),'system',lambda *_:self.fail('no model'),prepare,{'field-repair':{}})
            try:pipe.process(source,'field-repair',{},reuse_only=True)
            except NaturalSourceClarificationError as error:self.assertEqual(error.payload,merged)
            else:self.fail('next source choice must retain full frozen fields')

    def test_attachment_endpoints_come_only_from_one_explicit_source_range(self):
        from literary_engineering_studio.runtimes.commission_source_format import restore_attachment_line_ranges
        payload={'material_requests':[{'archive_attachments':[{'path':'canon/a.yaml','start_line':1,'end_line':None}]}]}
        restore_attachment_line_ranges('挂载：`canon/a.yaml` 第 1 行。',payload)
        self.assertEqual(payload['material_requests'][0]['archive_attachments'][0]['end_line'],1)
        for source in ('未列范围 `canon/a.yaml`','`canon/a.yaml` 第 1 行；`canon/a.yaml` 第 1–3 行'):
            payload={'material_requests':[{'archive_attachments':[{'path':'canon/a.yaml','start_line':1,'end_line':None}]}]}
            restore_attachment_line_ranges(source,payload)
            self.assertIsNone(payload['material_requests'][0]['archive_attachments'][0]['end_line'])

    def test_metadata_repair_contract_keeps_object_shape_and_enum_values(self):
        from literary_engineering_studio.runtimes.natural_field_repair import field_repair_task
        task=field_repair_task('原文',{'material_requests':[]},
            ['/material_requests/0/knowledge','/material_requests/0/need_evidence'],{})
        rows=task['response_contract']['patches']
        self.assertIn('known',rows[0]['value'])
        self.assertIn('mount_reasons',rows[1]['value'])
        self.assertIn('existing_material_evidence',rows[1]['value'])

    def test_preparation_editor_questions_are_preserved_but_not_invoked_without_body(self):
        from literary_engineering_studio.runtimes.scene_natural_output import _validate_editor_focus
        from literary_engineering_studio.runtimes.scene_creator_memory import SceneCreatorMemoryV1
        from tempfile import TemporaryDirectory
        from pathlib import Path
        focus={'issue':'抒情长句须服务思念','excerpt':'未来的正文','operation':''}
        payload={'material_requests':[{'kind':'environment'}],'prose':'','editor_focus':[focus]}
        _validate_editor_focus('抒情长句须服务思念',payload,{},'creator')
        self.assertEqual(payload['editor_focus'],[])
        self.assertEqual(payload['deferred_editor_focus'],[focus])
        with TemporaryDirectory() as temp:
            path=Path(temp)/'memory.json'
            memory=SceneCreatorMemoryV1('s');memory.deferred_editor_focus=[focus];memory.save(path)
            self.assertEqual(SceneCreatorMemoryV1.load(path,'s').deferred_editor_focus,[focus])

    def test_inline_card_identity_stops_at_full_stop_without_losing_sections(self):
        from tests.actor_card_fixtures import actor_card_payload
        from literary_engineering_studio.runtimes.natural_local_delivery import local_cards
        card=actor_card_payload('莓灯')
        card['sections']['CORE_IDENTITY']='代号：莓灯。本名：莓灯。她想起铜靴。'
        source='\n\n'.join('**【'+key+'】** '+value for key,value in card['sections'].items())
        cards=local_cards(source,{'eligible_actors':['莓灯','铜靴']})
        self.assertEqual(list(cards),['莓灯'])
        self.assertEqual(cards['莓灯']['sections'],card['sections'])

    def test_style_reference_mount_cannot_be_fixed_by_fabricating_candidate_ids(self):
        from literary_engineering_studio.runtimes.material_need import require_source_needs
        need={'gap':'缺口','why_existing_insufficient':'不足','expected_use':'用途','reviewed_candidate_ids':[],
            'existing_material_evidence':{},'mount_reasons':{'material:0':'借节奏'}}
        payload={'material_requests':[{'need_evidence':need,'material_attachments':[{'candidate_id':'R07'}]}]}
        try:require_source_needs('缺口不足用途借节奏',payload,{'material_need_contract':'v1','available_material_ids':[]})
        except NaturalSourceClarificationError as error:
            self.assertIn('/material_requests/0/material_attachments',error.fields)
            self.assertIn('/material_requests/0/need_evidence',error.fields)
        else:self.fail('a nonexistent candidate mount cannot remain frozen')

    def test_repair_object_has_full_eleven_card_sections(self):
        from literary_engineering_studio.runtimes.natural_field_repair import field_repair_task
        task=field_repair_task('原文',{},['/material_requests/0/character_card'],{'actor_card_schema':'arcvellum/actor-character-card/v2'})
        card=task['response_contract']['patches'][0]['value']
        self.assertEqual(len(card['sections']),11)

    def test_only_metadata_reply_accepts_one_embedded_json_patch_locally(self):
        from literary_engineering_studio.runtimes.natural_transport_pipeline import _whole_json
        reply='指定字段如下：\n```json\n{"patches":[]}\n```\n其余冻结。'
        self.assertEqual(_whole_json(reply,embedded=True),{'patches':[]})
        self.assertIsNone(_whole_json(reply))
        self.assertIsNone(_whole_json(reply+'\n```json\n{}\n```',embedded=True))

    def test_source_author_patch_list_is_a_field_value_and_still_checked_for_scope(self):
        from literary_engineering_studio.runtimes.natural_transport_repair import apply_repair
        from literary_engineering_studio.runtimes.natural_field_repair import apply_field_patch
        record=apply_repair({'patches':[]},{'patches':[{'path':'/prose','value':'改正文'}]},['/patches'])
        with self.assertRaises(ValueError):apply_field_patch({'prose':'原文'},record,['/knowledge'])

    def test_saved_actor_annotation_patch_restores_full_reply_and_speech_zero_call(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from literary_engineering_studio.runtimes.scene_natural_output import NaturalOutputProcessor
        from literary_engineering_studio.runtimes.scene_creator_v2_materials import _actor_fields
        from literary_engineering_studio_engine.public.prompting import prompt_layer_spec
        with TemporaryDirectory() as temp:
            source='（塞茶盘）你先端着。'
            root=Path(temp);folder=root/'natural-answers'/sha256(source.encode()).hexdigest();folder.mkdir(parents=True)
            (folder/'old.partial.json').write_text(json.dumps({'payload':{'candidates':[]},'paths':['/candidates']}),encoding='utf-8')
            candidate={'text':source,'focus':'开口','annotations':[{'kind':'first_person_action','text':'（塞茶盘）'},
                {'kind':'spoken','text':'你先端着。'}]}
            (folder/'old.extraction-2.md').write_text(json.dumps({'patches':[{'path':'/candidates','value':[candidate]}]},ensure_ascii=False),encoding='utf-8')
            processor=NaturalOutputProcessor(root,prompt_layer_spec('scene.v2.transport.extractor').default_text,
                lambda *_:self.fail('saved annotations must not cost another call'))
            result=processor.process(source,kind='material',context={'role':'character-actor','request':{'target':'莓灯'}},reuse_only=True)
            self.assertEqual(result['candidates'][0]['text'],source)
            self.assertEqual(_actor_fields(result['candidates'][0])['spoken'],'你先端着。')
            self.assertEqual(result['__transport']['model_calls'],0)

    def test_sibling_anchor_reference_is_syntax_only_and_validates_exact_span(self):
        source='她说：回来啦。'
        value={'$source':{'first_block':'b0001','last_block':'b0001'},'start_anchor':'回来','end_anchor':'啦。'}
        raw={'source_sha256':sha256(source.encode()).hexdigest(),'prose':value}
        self.assertEqual(decode_reference_delivery(raw,source)['prose'],'回来啦。')
        value['$source']['start_anchor']='冲突'
        self.assertIsInstance(decode_reference_delivery(raw,source)['prose'],dict)

    def test_explicit_delivery_preamble_is_not_reader_body(self):
        from literary_engineering_studio.runtimes.natural_local_delivery import local_creator_fields
        for label in ('下面是本场正文。','正文如下。'):
            source='返修说明。'+label+'\n\n---\n\n# 镇子\n\n月亮低了。\n\n---\n\n**交接札记**\n留给下一场。'
            fields=local_creator_fields(source,'creator')
            self.assertEqual(fields['prose'],'# 镇子\n\n月亮低了。')

    def test_missing_reference_digest_is_program_owned_but_wrong_digest_stays_invalid(self):
        source='月亮低了。'
        value={'prose':{'$source':{'first_block':'b0001','last_block':'b0001'}}}
        result=decode_reference_delivery(value,source)
        self.assertEqual(result['prose'],source)
        self.assertEqual(result['source_sha256'],sha256(source.encode()).hexdigest())
        value['source_sha256']='0'*64
        with self.assertRaises(ValueError):decode_reference_delivery(value,source)

    def test_explicit_notes_recover_without_a_standard_body_heading(self):
        from literary_engineering_studio.runtimes.natural_local_delivery import local_creator_fields
        source='## 一、本场文学判断\n写季节反复。\n# 镇子\n## 一\n灯亮了。\n## 二、取舍札记\n**改写（adapt）**\n- `v2:abcd:1-2` → 改回桥下。'
        result=local_creator_fields(source,'creator',{'available_material_ids':['v2:abcd:1','v2:abcd:2','v2:abcd:3']})
        self.assertEqual(result['decision_summary'],'写季节反复。')
        self.assertEqual([r['candidate_id'] for r in result['material_decisions']],['v2:abcd:1','v2:abcd:2'])
        self.assertNotIn('prose',result)

    def test_partial_discard_and_unchanged_notes_do_not_override_current_choices(self):
        from literary_engineering_studio.runtimes.natural_choice_labels import local_choice_labels
        source='## 取舍札记\n- `v2:abcd:1` → adapt。\n- `v2:abcd:2` → 状态不变（上一轮已 use/adapt）。\n**舍下（discard）**\n- `v2:abcd:1` 中她封爵的台词。'
        result=local_choice_labels(source,['v2:abcd:1','v2:abcd:2'])
        self.assertEqual([(r['candidate_id'],r['decision']) for r in result],[('v2:abcd:1','adapt')])

    def test_pending_bold_invitations_preserve_numbered_body_in_full(self):
        from literary_engineering_studio.runtimes.natural_local_delivery import local_creator_fields
        body='# 镇子\n\n## 一\n灯亮了。\n\n## 二\n月亮低了。'
        source='## 二、取材委托\n**委托一 · 角色**\n请回应。\n## 四、正文\n'+body+'\n## 五、取舍札记\n待用。'
        result=local_creator_fields(source,'creator',{'available_material_ids':[]})
        self.assertEqual(result['prose'],'')
        self.assertEqual(result['pending_body_source'],body)

    def test_author_phase_patch_keeps_exact_body_and_archives_completed_commissions(self):
        from literary_engineering_studio.runtimes.natural_delivery_phase import project_creator_phase
        from literary_engineering_studio.runtimes.natural_field_repair import apply_field_patch
        from copy import deepcopy
        frozen={'prose':'灯亮了。','material_requests':[{'kind':'actor','target':'莓灯'}]}
        with self.assertRaises(NaturalSourceClarificationError):project_creator_phase('本轮委托。',deepcopy(frozen))
        for phase in ('prepare','complete'):
            reply={'patches':[{'path':'/delivery_phase','value':phase}]}
            patched=apply_field_patch(frozen,reply,['/delivery_phase'])
            result=project_creator_phase(json.dumps(reply),patched)
            if phase=='prepare':
                self.assertEqual(result['pending_body_source'],frozen['prose'])
                self.assertEqual(result['material_requests'],frozen['material_requests'])
                self.assertEqual(result['prose'],'')
            else:
                self.assertEqual(result['completed_commission_notes'],frozen['material_requests'])
                self.assertEqual(result['prose'],frozen['prose'])
                self.assertEqual(result['material_requests'],[])
        with self.assertRaises(NaturalSourceClarificationError):project_creator_phase('无阶段。',{**frozen,'delivery_phase':'complete'})

    def test_next_source_field_failure_retains_merged_record_not_patch_envelope(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from literary_engineering_studio.runtimes.scene_natural_output import NaturalOutputProcessor
        from literary_engineering_studio.runtimes.natural_transport_repair import NaturalExtractionError
        with TemporaryDirectory() as temporary:
            processor=NaturalOutputProcessor(Path(temporary),'transport',lambda *_:self.fail('no formatter needed'))
            def prepare(source,payload,kind,context):
                self.assertEqual(payload['prose'],'冻结正文。')
                self.assertEqual(payload['material_requests'][0]['knowledge'],'known')
                raise NaturalExtractionError('style source missing',fields=['/material_requests/0/style_direction'])
            processor._prepare=prepare
            frozen={'prose':'冻结正文。','material_requests':[{'knowledge':'待确认','style_direction':'错误值'}]}
            reply=json.dumps({'patches':[{'path':'/material_requests/0/knowledge','value':'known'}]})
            with self.assertRaises(NaturalSourceClarificationError) as caught:
                processor.process_field_repair('正文与委托。',reply,kind='creator',context={},payload=frozen,fields=['/material_requests/0/knowledge'])
            error=caught.exception
            self.assertEqual(error.fields,('/material_requests/0/style_direction',))
            self.assertEqual(error.payload['prose'],frozen['prose'])
            self.assertNotIn('patches',error.payload)

    def test_partial_resolution_remains_open_with_original_progress_preserved(self):
        from literary_engineering_studio.runtimes.scene_review_validation import validate_review_extraction
        payload={'issue_progress':[{'issue_id':'old','status':'partially_resolved','evidence':'桥头灯亮了。'}]}
        validate_review_extraction(payload,{'prose':'桥头灯亮了。','review_continuity':{'open_issues':[{'issue_id':'old'}]}},'仍有一部分问题。')
        self.assertEqual(payload['issue_progress'][0]['status'],'persists')
        self.assertEqual(payload['issue_progress'][0]['source_progress_status'],'partially_resolved')

    def test_only_preserved_complete_review_evidence_can_return_to_original_reviewer(self):
        from literary_engineering_studio.runtimes.scene_creator_natural import _complete_review_evidence_failure
        from literary_engineering_studio.runtimes.natural_transport_repair import NaturalExtractionError
        error=NaturalExtractionError('failed',fields=['/issue_progress/5/evidence'],payload={'decision':'revise','summary':'原判断'})
        self.assertTrue(_complete_review_evidence_failure(error))
        for fields,payload in ((['/decision'],error.payload),(['/unknown/5/evidence'],error.payload),([],error.payload),(['/strengths/0/evidence'],{'strengths':[]})):
            self.assertFalse(_complete_review_evidence_failure(NaturalExtractionError('failed',fields=fields,payload=payload)))

    def test_primary_adapt_choice_and_notes_survive_subfragment_discard_explanation(self):
        from literary_engineering_studio.runtimes.natural_local_delivery import local_creator_fields
        source='## 正文\n灯亮了。\n## 取舍札记\n- **v2:abcd:1（演员）——adapt。** 原话改写；末句舍去（discard）。'
        result=local_creator_fields(source,'creator',{'available_material_ids':['v2:abcd:1']})
        self.assertEqual(result['material_decisions'][0]['decision'],'adapt')
        self.assertEqual(result['prose'],'灯亮了。')
        self.assertEqual(result['decision_summary'],source.split('## 取舍札记\n')[1])

    def test_current_editor_questions_exclude_completed_processing_recap(self):
        from literary_engineering_studio.runtimes.natural_editor_focus import recover_creator_editor_focus
        source='**编辑问题处理（editor_focus）**\n- 前问题已改。\n\n**editor_focus（供局部编辑参考）**\n- “灯亮了”是否呼应得太近？'
        payload={'prose':'灯亮了。'}
        recover_creator_editor_focus(source,payload,'creator')
        self.assertEqual(len(payload['editor_focus']),1)
        self.assertEqual(payload['editor_focus'][0]['excerpt'],'灯亮了')

    def test_creator_stream_recovers_only_one_same_input_completed_body(self):
        from literary_engineering_studio.runtimes.scene_creator_delivery_source import recover_saved_creator_delivery,combine_creator_delivery
        from pathlib import Path
        from tempfile import TemporaryDirectory
        body='## 正文\n攒姓是他认回来的名字。\n## 创作札记\n声音保留。'
        final='札记已保存。'
        prompt='固定合同\n本次创作资料：\n'+json.dumps({'prose':'旧正文','style':'原文风'},ensure_ascii=False)
        with TemporaryDirectory() as temporary:
            root=Path(temporary);run=root/'pi-conversations/worker/runs/one';run.mkdir(parents=True)
            (run/'conversation.prompt.md').write_text(json.dumps({'schema':'arcvellum/scene-creator/v2','call_purpose':'revision','prompt':prompt}),encoding='utf-8')
            events=[{'event':'agent.message.completed','data':{'text':body}},
                {'event':'agent.message.completed','data':{'text':final}},
                {'event':'runner.conversation.result','data':{'answer':final}}]
            (run/'runtime.output.log').write_text('\n'.join(json.dumps(event) for event in events),encoding='utf-8')
            answer=recover_saved_creator_delivery(final,prompt,root,root/'originals')
            self.assertIn(body,answer)
            self.assertIn(final,answer)
            self.assertEqual(recover_saved_creator_delivery(final,prompt.replace('旧正文','新正文'),root,root/'originals'),final)
            self.assertEqual(recover_saved_creator_delivery('别的结论',prompt,root,root/'originals'),'别的结论')
        self.assertEqual(combine_creator_delivery(final,[body,body.replace('名字','姓氏')]),final)
        self.assertEqual(combine_creator_delivery(body,[body]),body)

    def test_unbulleted_editor_request_is_retained_and_absent_source_never_invokes_editor(self):
        from literary_engineering_studio.runtimes.natural_editor_focus import recover_creator_editor_focus
        payload={'prose':'灯亮了。','editor_focus':[{'issue':'编造问题'}]}
        recover_creator_editor_focus('## 创作札记\n本轮完成。',payload,'creator')
        self.assertEqual(payload['editor_focus'],[])
        recover_creator_editor_focus('## editor_focus\n作者若想调整阈值，请另行裁定。',payload,'creator')
        self.assertEqual(payload['editor_focus'],[])
        self.assertEqual(payload['deferred_editor_focus'][0]['issue'],'作者若想调整阈值，请另行裁定。')

    def test_one_title_body_between_explicit_note_boundaries_is_preserved(self):
        from literary_engineering_studio.runtimes.natural_local_delivery import local_creator_fields
        body='# 镇子\n\n## 一\n灯亮了。\n\n## 二\n攒姓认回他的名字。'
        source='【本轮判断】仅调整呼吸。\n\n---\n\n'+body+'\n\n---\n\n## 创作札记\n无新委托。'
        fields=local_creator_fields(source,'creator',{'available_material_ids':['c1']})
        self.assertEqual(fields['prose'],body)
        self.assertEqual(fields['material_requests'],[])

    def test_known_closed_review_confirmations_are_history_and_unknown_ids_still_fail(self):
        from literary_engineering_studio.runtimes.scene_review_validation import validate_review_extraction
        context={'prose':'灯亮了。','review_continuity':{'open_issues':[{'issue_id':'open'}],
            'previous':{'issues':[{'issue_id':'closed','status':'resolved'},{'issue_id':'open','status':'persists'}]}}}
        payload={'issue_progress':[{'issue_id':'closed','status':'resolved','evidence':'旧稿证据'},
            {'issue_id':'open','status':'resolved','evidence':'灯亮了。'}]}
        validate_review_extraction(payload,context,'closed → resolved；open → resolved')
        self.assertEqual([row['issue_id'] for row in payload['issue_progress']],['open'])
        self.assertEqual(payload['historical_issue_progress'][0]['issue_id'],'closed')
        payload['issue_progress'].append({'issue_id':'unknown','status':'resolved','evidence':'灯亮了。'})
        with self.assertRaises(ValueError):validate_review_extraction(payload,context,'open resolved，unknown resolved')

    def test_review_evidence_reference_resolves_frozen_body_and_rejects_foreign_version(self):
        from literary_engineering_studio.runtimes.evidence_patch_source import prose_evidence_source,resolve_evidence_patches
        from literary_engineering_studio.runtimes.scene_natural_output import NaturalOutputProcessor
        from literary_engineering_studio.runtimes.natural_field_repair import field_repair_task
        from pathlib import Path
        from tempfile import TemporaryDirectory
        body='灯亮了。\n\n攒姓认回了他的名字。\n他走上桥。'
        catalog=prose_evidence_source(body)
        path='/strengths/0/evidence'
        reference={'prose_sha256':catalog['sha256'],'prose_block':'p0002'}
        reply={'patches':[{'path':path,'value':reference}]}
        task=field_repair_task('已通过。',{'decision':'pass','strengths':[{'claim':'名字成立','evidence':'旧话'}]},[path],{'prose':body})
        self.assertNotIn('prose',task['context'])
        self.assertEqual(task['context']['prose_source'],catalog)
        with TemporaryDirectory() as temporary:
            processor=NaturalOutputProcessor(Path(temporary),'transport',lambda *_:self.fail('no model needed'))
            result=processor.process_field_repair('已通过。',json.dumps(reply),kind='review',context={'prose':body},
                payload={'decision':'pass','summary':'名字成立','strengths':[{'claim':'名字成立','evidence':'旧话'}]},fields=[path])
            self.assertEqual(result['strengths'][0]['evidence'],'攒姓认回了他的名字。\n他走上桥。')
            self.assertEqual(result['decision'],'pass')
        for change in ({'prose_sha256':'0'*64,'prose_block':'p0002'}, {'prose_sha256':catalog['sha256'],'prose_block':'p9999'}):
            with self.assertRaises(ValueError):resolve_evidence_patches({'patches':[{'path':path,'value':change}]},body,[path])

    def test_explicit_material_notes_detach_without_changing_story_or_delta(self):
        from literary_engineering_studio.runtimes.creator_body_boundary import detach_creator_notes
        body='# 镇子\n\n攒姓认回他的名字。'
        notes='\n\n---\n\n# 素材使用札记\n`v2:abcd:1` adapt，保留"攒姓"。'
        frozen={'prose':body+notes,'scene_delta':{'next_handoff':'桥上'}}
        result=detach_creator_notes(frozen)
        self.assertEqual(result['prose'],body)
        self.assertEqual(result['detached_creator_notes'],notes)
        self.assertEqual(result['scene_delta'],frozen['scene_delta'])
        self.assertEqual(frozen['prose'],body+notes)
        plain={'prose':body+'\n\n# 素材使用札记\n人物自己写的日记。'}
        self.assertEqual(detach_creator_notes(plain),plain)

    def test_candidate_one_cannot_validate_as_a_prefix_of_candidate_twelve(self):
        from literary_engineering_studio.runtimes.natural_selection_pending import validate_choice_ids
        validate=lambda source,value,label:None
        payload={'material_decisions':[{'candidate_id':'v2:abcd:1'}]}
        with self.assertRaises(ValueError):validate_choice_ids('采用 `v2:abcd:12`',payload,validate,['v2:abcd:1','v2:abcd:12'])
        validate_choice_ids('采用v2:abcd:1。',payload,validate,['v2:abcd:1'])
        payload={'material_decisions':[{'candidate_id':'v2:abcd:2'}]}
        validate_choice_ids('采用 `v2:abcd:1/:2`',payload,validate,['v2:abcd:1','v2:abcd:2'])
        self.assertEqual(payload['material_id_notation_recovery'][0]['candidate_id'],'v2:abcd:2')

    def test_nested_selection_sections_keep_bold_candidate_headers_and_their_reasons(self):
        from literary_engineering_studio.runtimes.natural_choice_labels import local_choice_labels
        source='# 素材取舍记录\n\n## 一、人物\n\n**`v2:abcd:1`（演员）——adapt。**\n改成他替人递碗的动作。\n\n## 二、场面\n**use — v2:bcde:1（场面）**，保留站位。\n\n**discard — 第四节末两句格言**\n它不是候选编号。\n\n# 交接\n- v2:abcd:1 → discard。'
        result=local_choice_labels(source,['v2:abcd:1','v2:bcde:1'])
        self.assertEqual([(row['candidate_id'],row['decision']) for row in result],[('v2:abcd:1','adapt'),('v2:bcde:1','use')])
        self.assertIn('改成他替人递碗',result[0]['reason'])

    def test_inline_numeric_suffix_inherits_only_its_same_paragraph_explicit_prefix(self):
        from literary_engineering_studio.runtimes.natural_selection_pending import shared_prefix_source
        source='`v2:abcd:1` 留用借还账。`:2` 用作口传姿态。`:21` 改写为三问三答。'
        self.assertEqual(shared_prefix_source(source,'v2:abcd:21')['form'],'same-paragraph-explicit-prefix')
        self.assertIsNone(shared_prefix_source(source,'v2:abcd:3'))
        self.assertIsNone(shared_prefix_source('`v2:abcd:1`\n\n`:21`','v2:abcd:21'))
        self.assertIsNone(shared_prefix_source('`v2:abcd:1`，`v2:bcde:1` 后的 `:21`','v2:abcd:21'))

    def test_pending_selection_replays_preserved_choices_without_model_or_body_changes(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from literary_engineering_studio.runtimes.scene_natural_output import NaturalOutputProcessor
        source='## 正文\n桥灯亮了。\n## 创作札记\n`v2:abcd:1` 留用。`:2` 改写。'
        choices=[{'candidate_id':'v2:abcd:2','decision':'adapt','reason':'改写。'}]
        pending={'prose':'桥灯亮了。','decision_summary':'留用与改写。','material_requests':[],
                 'material_decisions':[], 'unverified_material_decisions':choices,
                 'material_selection_pending':'主创的自然取舍需要与实际候选编号核对。'}
        context={'available_material_ids':['v2:abcd:1','v2:abcd:2']}
        with TemporaryDirectory() as temporary:
            processor=NaturalOutputProcessor(Path(temporary),'transport',lambda *_:self.fail('no paid retry'))
            saved=Path(temporary)/'natural-answers'/sha256(source.encode()).hexdigest()
            saved.mkdir(parents=True)
            (saved/('0'*64+'.json')).write_text(json.dumps(pending,ensure_ascii=False),encoding='utf-8')
            result=processor.process(source,kind='creator',context=context,reuse_only=True)
            self.assertEqual(result['material_decisions'],choices)
            self.assertEqual(result['prose'],pending['prose'])
            self.assertEqual(result['__transport']['model_calls'],0)
            self.assertNotIn('material_selection_pending',result)
            self.assertEqual(pending['material_decisions'],[])
            for changed, catalog in ((source.replace('`:2`','`:3`'),context),
                    (source,{'available_material_ids':['v2:abcd:1']})):
                rejected=processor._prepare(changed,pending,'creator',catalog)
                self.assertIn('material_selection_pending',rejected)
                self.assertEqual(rejected['material_decisions'],[])

    def test_explicit_editor_no_change_is_source_backed_without_a_model_retry(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from literary_engineering_studio.runtimes.natural_local_delivery import local_delivery
        from literary_engineering_studio.runtimes.scene_natural_output import NaturalOutputProcessor
        verdict='本场不给额外的替换建议；照原稿保留即可。'
        source='两处均保留：人物声音与结构回环。'+verdict
        with TemporaryDirectory() as temporary:
            processor=NaturalOutputProcessor(Path(temporary),'transport',lambda *_:self.fail('no paid retry'))
            result=processor.process(source,kind='tone',context={'prose':'河底那条鱼没有动。它绿着。'})
            self.assertEqual(result['edits'],[])
            self.assertEqual(result['no_edit_source'],verdict)
            self.assertEqual(result['__transport']['model_calls'],0)
        for incomplete in ('','建议保留。','其余保留原稿。',
                '【替换片段】改写。\n'+verdict,'建议修改：缩短第一句。\n'+verdict):
            self.assertIsNone(local_delivery(incomplete,'tone',{}))

    def test_review_formatter_cannot_copy_old_summary_and_directions_into_a_new_source(self):
        from literary_engineering_studio.runtimes.scene_review_validation import validate_review_extraction
        from literary_engineering_studio.runtimes.natural_transport_context import extraction_context
        from literary_engineering_studio.runtimes.natural_transport_repair import NaturalExtractionError
        previous={'summary':'旧问题是第五节缺呼吸。\n正文已经成立：风俗。',
                  'revision_instructions':['加一个呼吸动作。']}
        context={'prose':'她按住坛口。','review_continuity':{'previous':{'review':previous,'issues':[]},'open_issues':[]}}
        stale={'decision':'revise','summary':'旧问题是第五节缺呼吸。',
               'revision_instructions':['加一个呼吸动作。']}
        with self.assertRaises(NaturalExtractionError) as caught:
            validate_review_extraction(stale,context,'呼吸已补；现在只需说明下注是否故意。')
        self.assertIn('/revision_instructions',caught.exception.fields)
        validate_review_extraction(stale,context,'旧问题是第五节缺呼吸。仍需加一个呼吸动作。')
        projected=extraction_context('review',context)
        self.assertNotIn('review',projected['review_continuity']['previous'])
        self.assertIn('review_identity',projected['review_continuity']['previous'])
        self.assertEqual(context['review_continuity']['previous']['review'],previous)
