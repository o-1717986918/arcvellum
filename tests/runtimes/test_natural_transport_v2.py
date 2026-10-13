"""Preserved-source reconstruction, zero-call paths and focused technical repair."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest

from literary_engineering_studio_engine.public.literary import (
    natural_source_index, resolve_natural_source_references, parse_scene_material_requests_v4,
)
from literary_engineering_studio_engine.public.prompting import prompt_layer_spec
from literary_engineering_studio.runtimes.scene_natural_output import NaturalOutputProcessor
from literary_engineering_studio.runtimes.scene_creator_v2_materials import _parse_candidates
from literary_engineering_studio.runtimes.scene_creator_material_context import freeze_material_candidate
from tests.actor_card_fixtures import actor_card_payload

SYSTEM = prompt_layer_spec('scene.v2.transport.extractor').default_text


def reference(text, first, last=None, **anchors):
    return {'$source': {'sha256': sha256(text.encode()).hexdigest(), 'first_block': first,
                        'last_block': last or first, **anchors}}


class NaturalTransportTests(unittest.TestCase):
    def test_reviewers_own_wrong_quote_is_clarified_while_transport_typo_stays_technical(self):
        from literary_engineering_studio.runtimes.scene_review_validation import validate_review_extraction
        from literary_engineering_studio.runtimes.natural_transport_repair import NaturalSourceClarificationError
        payload={'strengths':[{'evidence':'桥上的灯亮了。'}]}
        context={'prose':'桥头的灯亮了。'}
        with self.assertRaises(NaturalSourceClarificationError):
            validate_review_extraction(payload,context,'证据：桥上的灯亮了。')
        try:
            validate_review_extraction(payload,context,'成立之处：桥头的灯亮了。')
        except ValueError as error:
            self.assertNotIsInstance(error,NaturalSourceClarificationError)
        else:
            self.fail('transport changed the source quote')
        try:
            validate_review_extraction(payload,context,'审读意见：桥上的灯亮了。')
        except ValueError as error:
            self.assertNotIsInstance(error,NaturalSourceClarificationError)

    def test_review_quote_presentation_restores_actual_body_without_changing_words(self):
        from literary_engineering_studio.runtimes.scene_review_validation import validate_review_extraction
        payload={'strengths':[{'evidence':'> 她说"回来啦"。\n'}]}
        validate_review_extraction(payload,{'prose':'她说“回来啦”。'},'> 她说"回来啦"。')
        self.assertEqual(payload['strengths'][0]['evidence'],'她说“回来啦”。')
        self.assertEqual(payload['review_format_recovery'][0]['original'],'> 她说"回来啦"。\n')

    def test_hash_shorthand_requires_one_actual_catalog_match(self):
        from literary_engineering_studio.runtimes.natural_selection_pending import abbreviated_choice_source
        source='## use\n- 70dc:1 借月风俗\n- 1b602 肖像姿态'
        known=['v2:70dcaaaa:1','v2:70dcaaaa:2','v2:1b602bbb:1']
        proof=abbreviated_choice_source(source,known[0],known)
        self.assertEqual(source[proof['start']:proof['end']],proof['source'])
        self.assertIsNotNone(abbreviated_choice_source(source,known[2],known))
        self.assertIsNone(abbreviated_choice_source(source,known[1],known))
        self.assertIsNone(abbreviated_choice_source(source,known[0],known+['v2:70dccccd:1']))
        self.assertIsNone(abbreviated_choice_source('70dc:1 只是散文中的数字',known[0],known))

    def test_decorated_style_id_is_recovered_only_from_one_explicit_allowed_token(self):
        from literary_engineering_studio.runtimes.creator_delivery_labels import recover_style_preset_id
        source = '**主：`world-narration`（世界与风俗）**。'
        payload = {'preset_id':'**主：`world-narration`（'}
        self.assertTrue(recover_style_preset_id(source,payload,{'preset_ids':['world-narration','lyric']}))
        self.assertEqual(payload['preset_id'],'world-narration')
        record=payload['preset_label_recovery']
        self.assertEqual(source[record['start']:record['end']],record['original'])
        for value in ('world-narration-alt','world-narration/lyric','unselected'):
            self.assertFalse(recover_style_preset_id(value,{'preset_id':value},{'preset_ids':['world-narration','lyric']}))

    def test_unresolved_event_text_is_repaired_as_a_contract_error(self):
        source = '月亮来到屋檐，旧账房记下年份。'
        calls=[]
        def invoke(_system,prompt):
            calls.append(json.loads(prompt))
            if len(calls)==1:
                return json.dumps({'candidates':[{'text':{'unrecognized_reference':'b0001'},
                    'basis':'proposed','source_note':'创作提议'}]},ensure_ascii=False)
            return json.dumps({'candidates':[{'text':source,'basis':'proposed','source_note':'创作提议'}]},ensure_ascii=False)
        with TemporaryDirectory() as directory:
            result=self.processor(directory,invoke).process(source,kind='material',context={'role':'event-narrator'})
        self.assertEqual(result['candidates'][0]['text'],source)
        self.assertEqual(len(calls),2)
        from literary_engineering_studio.runtimes.event_material_provenance import recover_event_source_status
        with self.assertRaisesRegex(ValueError,'resolved literal source'):
            recover_event_source_status(source,{'candidates':[{'text':{'unrecognized_reference':'b0001'}}]})

    def test_explicit_delimited_completed_body_recovers_old_request_recap_without_regeneration(self):
        text = '本场已咨询角色，两人声音已返回。下面是正文。\n\n---\n\n她把月亮迎进茶馆。\n\n---\n\n**交接札记**\n两人等着傍晚。'
        from literary_engineering_studio.runtimes.natural_local_delivery import local_creator_fields
        self.assertEqual(local_creator_fields(text, 'creator'), {'prose': '她把月亮迎进茶馆。', 'material_requests': []})
        with TemporaryDirectory() as directory:
            source_dir = Path(directory)/'natural-answers'/sha256(text.encode()).hexdigest()
            source_dir.mkdir(parents=True)
            (source_dir/'previous.extraction-1.md').write_text(json.dumps({
                'prose':'她把月亮迎进茶馆。','material_requests':[{'kind':'actor','target':'阿青','author_prompt':'旧邀请'}],
                'decision_summary':'两人等着傍晚。'},ensure_ascii=False),encoding='utf-8')
            result=self.processor(directory,lambda *_: self.fail('same source called a model')).process(
                text,kind='creator',context={})
        self.assertEqual(result['material_requests'], [])
        self.assertEqual(result['__transport']['mode'],'recovered')

    def test_creator_transport_retains_actual_delta_catalog_and_scoped_context_contract(self):
        from literary_engineering_studio.runtimes.natural_transport_task import extraction_task
        from literary_engineering_studio.runtimes.natural_transport_context import extraction_context
        from literary_engineering_studio.runtimes.scene_natural_output import CONTRACTS
        source = '准备阶段：请接住眼前的来话。'
        context = {'available_delta_targets': ['canon/world_rules.yaml'], 'available_material_ids': []}
        task = extraction_task('creator', CONTRACTS['creator'], extraction_context('creator', context),
            natural_source_index(source), source, {}, {})
        self.assertEqual(task['context']['available_delta_targets'], ['canon/world_rules.yaml'])
        self.assertIn('context.available_delta_targets', task['delivery_guidance'])
        self.assertIn('6000', task['task_contract']['material_requests'][0]['working_context'])

    def test_explicit_new_commissions_keep_revision_draft_pending_until_materials_return(self):
        from literary_engineering_studio.runtimes.natural_local_delivery import local_creator_fields
        source = '## 二、本轮重新委托（两条）\n请接住眼前来话。\n## 三、修订正文\n她把月亮迎进茶馆。'
        self.assertEqual(local_creator_fields(source, 'creator'), {'prose': ''})

    def test_explicit_marked_editor_advice_is_preserved_locally(self):
        text = ('## 一、句子\n\n**【规则编号】** 规则1 · 判断与依据\n\n'
            '**【原片段】** 她攒姓要拿海风攒。\n\n**【替换片段】** 她攒盘缠，打算拿海风攒。\n\n'
            '**【理由】** 这是编辑给出的判断，程序完整保留。\n\n---\n\n其余保留原稿。')
        with TemporaryDirectory() as directory:
            result = self.processor(directory, lambda *args: self.fail('labelled edits must be read locally')).process(
                text, kind='tone', context={'prose': '她攒姓要拿海风攒。'})
        self.assertEqual(result['__transport']['mode'], 'local')
        self.assertEqual(result['edits'], [{'rule_id': '1', 'before': '她攒姓要拿海风攒。',
            'after': '她攒盘缠，打算拿海风攒。', 'reason': '这是编辑给出的判断，程序完整保留。'}])

    def test_shared_prefix_choice_ids_are_grounded_without_inventing_another_number(self):
        from literary_engineering_studio.runtimes.natural_selection_pending import shared_prefix_source
        text = '采用（v2:abc:1 / :2 / :3），按原叙述次序组织。'
        result = shared_prefix_source(text, 'v2:abc:2')
        self.assertEqual(text[result['start']:result['end']], result['source'])
        self.assertIsNone(shared_prefix_source(text, 'v2:abc:4'))
        self.assertIsNone(shared_prefix_source(text, 'v2:def:2'))

    def test_labelled_ellipsis_choice_keeps_section_prefix_evidence(self):
        from literary_engineering_studio.runtimes.natural_selection_pending import shared_prefix_source
        text = '## 事件候选\n**`v2:abc:1`——use。** 原因。\n**`…:2`——adapt。** 原因。'
        result = shared_prefix_source(text, 'v2:abc:2')
        self.assertEqual(text[result['prefix_start']:result['prefix_end']], result['prefix_source'])
        self.assertEqual(text[result['start']:result['end']], result['source'])
        self.assertIsNone(shared_prefix_source(text, 'v2:def:2'))
        self.assertIsNone(shared_prefix_source(text, 'v2:abc:3'))
        separated = text.replace('\n**`…:2`', '\n## 另一类别\n**`…:2`')
        self.assertIsNone(shared_prefix_source(separated, 'v2:abc:2'))
        labelled=text.replace('**`v2:', '**事件 `v2:').replace('**`…:', '**事件 `…:')
        self.assertIsNotNone(shared_prefix_source(labelled,'v2:abc:2'))

    def test_explicit_ambiguous_role_partition_goes_to_creator_without_annotation_retry(self):
        from literary_engineering_studio.runtimes.natural_transport_repair import NaturalSourceClarificationError
        source = '本轮角色邀请：请接住眼前的来话。挂载角色档案，分区 known+reference。'
        calls = []
        def invoke(*args):
            calls.append(args)
            return json.dumps({'material_requests': [{'kind': 'actor', 'target': '阿青',
                'author_prompt': '请接住眼前的来话。', 'archive_attachments': [{
                    'path': 'characters/person-1.yaml', 'knowledge': 'known+reference'}]}]}, ensure_ascii=False)
        with TemporaryDirectory() as directory:
            with self.assertRaises(NaturalSourceClarificationError):
                self.processor(directory, invoke).process(source, kind='creator', context={})
        self.assertEqual(len(calls), 1)

    def test_selection_only_transport_requests_only_the_pending_choices(self):
        from literary_engineering_studio.runtimes.natural_transport_task import extraction_task
        from literary_engineering_studio.runtimes.scene_natural_output import CONTRACTS
        text = '改写 v2:abc:1，使光成为这一段的时间。'
        task = extraction_task('creator', CONTRACTS['creator'], {'selection_only': True},
            natural_source_index(text), text, {}, {}, paths=['/prose', '/material_decisions'])
        self.assertEqual(set(task['task_contract']), {'material_decisions'})
        self.assertEqual(task['remaining_fields'], ['material_decisions'])
        self.assertEqual(task['repair_paths'], ['/material_decisions'])
        self.assertNotIn('actor_card_contract', task)

    def processor(self, directory, invoke):
        return NaturalOutputProcessor(Path(directory), SYSTEM, invoke)

    def test_unicode_blank_lines_and_ambiguous_anchor(self):
        text = '月亮🌙落了。\n\n同一句，同一句。\n门开了。'
        index = natural_source_index(text)
        self.assertEqual(index['index_unit'], 'unicode-codepoint')
        whole = reference(text, 'b0001', 'b0003')
        self.assertEqual(resolve_natural_source_references({'prose': whole}, text)['prose'], text)
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            resolve_natural_source_references({'prose': reference(text, 'b0002', start_anchor='同一句')}, text)
        with self.assertRaisesRegex(ValueError, 'digest'):
            resolve_natural_source_references({'prose': {'$source': {'sha256': 'foreign', 'first_block': 'b0001'}}}, text)

    def test_eleven_labelled_card_is_read_locally(self):
        card = actor_card_payload()
        text = '\n\n'.join('【'+key+'】\n'+value for key,value in card['sections'].items())
        with TemporaryDirectory() as directory:
            result = self.processor(directory, lambda *_: self.fail('card called a model')).process(
                text, kind='card', context={'target': card['target']})
            self.assertEqual(result['card']['sections'], card['sections'])
            self.assertEqual(result['__transport']['model_calls'], 0)

    def test_style_choice_is_read_locally(self):
        text = '预设：world\n参照：r1、r2\n叙述方式：从风俗讲起。\n选择理由：让岁月进入日常。'
        with TemporaryDirectory() as directory:
            result = self.processor(directory, lambda *_: self.fail('style called a model')).process(
                text, kind='style-choice', context={'preset_ids':['world'], 'reference_ids':['r1','r2']})
        self.assertEqual(result['reference_ids'], ['r1','r2'])

    def test_short_actor_speech_has_full_original_and_zero_call(self):
        text = '“嗯。”'
        with TemporaryDirectory() as directory:
            result = self.processor(directory, lambda *_: self.fail('speech called a model')).process(
                text, kind='material', context={'role':'character-actor'})
        request = parse_scene_material_requests_v4({'material_requests':[{
            'kind':'actor','target':'阿青','purpose':'来话','scene_moment':'现在','cue':'问候',
            'author_prompt':'阿青，你听到朋友问好。'}]},['阿青'])[0]
        candidate = _parse_candidates(result, request, 'request')[0]
        self.assertEqual(candidate['text'], text)

    def test_actor_interleaving_and_private_relay_are_preserved(self):
        text = '“船回来啦！”\n我把杯子举过头顶。\n心里却惦记那封未寄的信。\n“今晚请你喝两杯。”'
        calls=[]
        def invoke(_system, prompt):
            task=json.loads(prompt);calls.append(task)
            return json.dumps({'candidates':[{'text':reference(text,'b0001','b0004'), 'focus':'重逢',
                'annotations':[{'kind':kind,'text':reference(text,block)} for kind,block in (
                    ('spoken','b0001'),('first_person_action','b0002'),('private_impulse','b0003'),('spoken','b0004'))]}]},ensure_ascii=False)
        with TemporaryDirectory() as directory:
            response=self.processor(directory,invoke).process(text,kind='material',context={'role':'character-actor'})
        request=parse_scene_material_requests_v4({'material_requests':[{'kind':'actor','target':'阿青',
            'purpose':'重逢','scene_moment':'门口','cue':'朋友回来','author_prompt':'阿青，你看见朋友走来。'}]},['阿青'])[0]
        candidate=_parse_candidates(response,request,'request')[0]
        self.assertEqual(candidate['text'],text)
        self.assertEqual(len(candidate['spoken_fragments']),2)
        ref=type('Ref',(),{'candidate_id':candidate['candidate_id'],'start_char':None,'end_char':None})()
        visible=freeze_material_candidate(ref,{candidate['candidate_id']:candidate},visible_only=True)['content']
        self.assertIn('今晚请你',visible);self.assertNotIn('未寄的信',visible)
        self.assertEqual(len(calls),1)

    def test_repair_changes_only_the_invalid_choice(self):
        text='雨停了。\n取舍：改写 v2:real:1，让雨声退到街外。'
        calls=[]
        def invoke(_system,prompt):
            task=json.loads(prompt);calls.append(task)
            if len(calls)==1:
                return json.dumps({'prose':'雨停了。','material_decisions':[
                    {'candidate_id':'invented','decision':'adapt','reason':'让雨声退到街外'}]},ensure_ascii=False)
            self.assertEqual(task['repair_paths'],['/material_decisions'])
            return json.dumps({'patches':[{'path':'/material_decisions','value':[
                {'candidate_id':'v2:real:1','decision':'adapt','reason':'让雨声退到街外'}]}]},ensure_ascii=False)
        with TemporaryDirectory() as directory:
            result=self.processor(directory,invoke).process(text,kind='creator',context={})
        self.assertEqual(result['prose'],'雨停了。');self.assertEqual(len(calls),2)

    def test_cosmetic_context_changes_reuse_and_scope_changes_revalidate(self):
        text='预设：world\n参照：r1\n叙述方式：讲述风俗。\n选择理由：日子很长。'
        context={'preset_ids':['world'],'reference_ids':['r1']}
        with TemporaryDirectory() as directory:
            processor=self.processor(directory,lambda *_: self.fail('reuse called a model'))
            processor.process(text,kind='style-choice',context=context)
            result=processor.process(text,kind='style-choice',context={**context,'attempt':99},reuse_only=True)
            self.assertEqual(result['__transport']['mode'],'reused')
            with self.assertRaises(ValueError):
                processor.process(text,kind='style-choice',context={**context,'preset_ids':['different']},reuse_only=True)

    def test_concurrent_identical_extraction_invokes_once(self):
        text='窗前的雨一直没有停。'
        calls=[]
        def invoke(_system,prompt):
            calls.append(prompt);time.sleep(.1)
            return json.dumps({'prose':text},ensure_ascii=False)
        with TemporaryDirectory() as directory:
            def run(_):
                return self.processor(directory,invoke).process(text,kind='creator',context={})
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(run,range(2)))
        self.assertEqual(len(calls),1);self.assertTrue(all(row['prose']==text for row in results))

    def test_frozen_context_precedes_source_and_digest_follows_it(self):
        calls=[]
        with TemporaryDirectory() as directory:
            def invoke(_system,prompt):
                calls.append(prompt);return json.dumps({'prose':'雨停了。'},ensure_ascii=False)
            self.processor(directory,invoke).process('雨停了。',kind='creator',context={})
        prompt=calls[0]
        self.assertLess(prompt.index('"context"'),prompt.index('"source_text"'))
        self.assertLess(prompt.index('"source_text"'),prompt.index('"source_index"'))

    def test_crlf_original_bytes_survive_recovery(self):
        text='雨落了。\r\n\r\n门开了。'
        with TemporaryDirectory() as directory:
            processor=self.processor(directory,lambda *_:json.dumps({'prose':text},ensure_ascii=False))
            processor.process(text,kind='creator',context={})
            processor.process(text,kind='creator',context={},reuse_only=True)
            original=Path(directory)/'natural-answers'/sha256(text.encode()).hexdigest()/'original.source.txt'
            self.assertEqual(original.read_bytes(),text.encode())

    def test_invalid_reference_repairs_only_that_field(self):
        text='雨停了。\n窗外忽然有了鸟叫。'
        calls=[]
        def invoke(_system,prompt):
            task=json.loads(prompt);calls.append(task)
            if len(calls)==1:
                return json.dumps({'prose':reference(text,'b0001'),
                    'decision_summary':reference(text,'unknown')},ensure_ascii=False)
            self.assertEqual(task['repair_paths'],['/decision_summary'])
            self.assertEqual(task['remaining_fields'],['decision_summary'])
            self.assertNotIn('actor_card_contract',task)
            return json.dumps({'patches':[{'path':'/decision_summary','value':reference(text,'b0002')}]},ensure_ascii=False)
        with TemporaryDirectory() as directory:
            result=self.processor(directory,invoke).process(text,kind='creator',context={})
        self.assertEqual(result['prose'],'雨停了。\n')
        self.assertEqual(result['decision_summary'],'窗外忽然有了鸟叫。')

    def test_copied_task_envelope_keeps_only_literary_delivery(self):
        text = '雨停了。\n窗外有了鸟叫。'
        def invoke(_system, _prompt):
            return json.dumps({'source_sha256': sha256(text.encode()).hexdigest(),
                'task_contract': {'prose': reference(text, 'b0001'), 'decision_summary': '听鸟鸣'},
                'source_index': {'a_large_copied_input': 'reading metadata'}}, ensure_ascii=False)
        with TemporaryDirectory() as directory:
            result = self.processor(directory, invoke).process(text, kind='creator', context={})
        self.assertEqual(result['prose'], '雨停了。\n')
        self.assertNotIn('source_index', result)
        self.assertEqual(result['__transport']['model_calls'], 1)

    def test_actor_complete_source_is_seeded_even_when_model_returns_excerpt(self):
        text = '我把杯子举过头顶。\n“回来啦！”\n心里还记着那封信。'
        def invoke(_system, prompt):
            task = json.loads(prompt)
            self.assertEqual(task['context']['request']['target'], '阿青')
            contract = task['task_contract']['candidates'][0]
            self.assertIn('annotations', contract); self.assertNotIn('basis', contract)
            return json.dumps({'candidates': [{'text': reference(text, 'b0002'), 'focus': '重逢',
                'annotations': [{'kind': 'first_person_action', 'text': reference(text, 'b0001')},
                    {'kind': 'spoken', 'text': reference(text, 'b0002')},
                    {'kind': 'private_impulse', 'text': reference(text, 'b0003')}]}]}, ensure_ascii=False)
        with TemporaryDirectory() as directory:
            result = self.processor(directory, invoke).process(text, kind='material',
                context={'role': 'character-actor', 'request': {'kind': 'actor', 'target': '阿青'}})
        self.assertEqual(result['candidates'][0]['text'], text)
        self.assertEqual(len(result['candidates'][0]['annotation_spans']), 3)

    def test_long_environment_is_complete_local_material_and_admitted(self):
        text = '月亮落在镇子上空。\n' * 400
        with TemporaryDirectory() as directory:
            result = self.processor(directory, lambda *_: self.fail('complete material called a model')).process(
                text, kind='material', context={'role': 'environment-writer'})
        request = parse_scene_material_requests_v4({'material_requests': [{'kind': 'environment',
            'target': '小镇', 'purpose': '世界开场', 'scene_moment': '夏末', 'cue': '浮月',
            'author_prompt': '请写小镇的夏末。'}]}, [])[0]
        self.assertEqual(_parse_candidates(result, request, 'request')[0]['text'], text)
        self.assertEqual(result['__transport']['model_calls'], 0)

    def test_event_contract_keeps_world_material_and_separate_fact_status(self):
        text = '浮月是镇上的季节。'
        def invoke(_system, prompt):
            task = json.loads(prompt)
            item = task['task_contract']['candidates'][0]
            self.assertIn('basis', item); self.assertNotIn('spoken', item)
            self.assertIn('风俗', task['delivery_guidance'])
            self.assertIsInstance(task['source_index']['blocks'][0], list)
            return json.dumps({'candidates': [{'text': text, 'focus': '地方历法',
                'basis': 'confirmed', 'source_note': '原文明示的季节事实'}]}, ensure_ascii=False)
        with TemporaryDirectory() as directory:
            result = self.processor(directory, invoke).process(text, kind='material', context={'role': 'event-narrator'})
        self.assertEqual(result['candidates'][0]['basis'], 'confirmed')

    def test_preparation_keeps_invitations_when_trial_body_is_also_present(self):
        text = '**交付阶段**：准备邀请与创作札记\n\n阿青，你听见朋友喊你。\n\n正文（试写稿）\n朋友来了。'
        calls = []
        request = {'kind': 'actor', 'target': '阿青', 'purpose': '重逢', 'scene_moment': '门口',
                   'cue': '问候', 'author_prompt': '阿青，你听见朋友喊你。'}
        def invoke(_system, prompt):
            task = json.loads(prompt); calls.append(task)
            self.assertIn('准备邀请', task['delivery_guidance'])
            return json.dumps({'prose': '朋友来了。', 'material_requests': [request]}, ensure_ascii=False)
        with TemporaryDirectory() as directory:
            result = self.processor(directory, invoke).process(text, kind='creator', context={})
        self.assertEqual(result['prose'], '')
        self.assertEqual(len(result['material_requests']), 1)
        self.assertEqual(len(calls), 1)

    def test_markdown_table_cards_are_local_and_preserve_each_cell(self):
        card = actor_card_payload()
        text = '\n'.join('| **'+key+'** | '+value+' |' for key,value in card['sections'].items())
        with TemporaryDirectory() as directory:
            result = self.processor(directory, lambda *_: self.fail('table card called a model')).process(
                text, kind='card', context={'target': card['target']})
        self.assertEqual(result['card']['sections'], card['sections'])

    def test_reference_quote_presentation_recovers_exact_original(self):
        text = '他说“走吧”，把门推开。'
        ref = reference(text, 'b0001', start_anchor='他说"走吧"', end_anchor='推开。')
        self.assertEqual(resolve_natural_source_references({'prose': ref}, text)['prose'], text)
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            resolve_natural_source_references({'prose': reference('“好” "好"', 'b0001',
                start_anchor="'好'")}, '“好” "好"')

    def test_original_event_segments_are_admitted_with_individual_fact_states(self):
        request = parse_scene_material_requests_v4({'material_requests': [{'kind': 'event-narration',
            'target': '镇史', 'purpose': '传言', 'scene_moment': '百年', 'cue': '浮月',
            'author_prompt': '请讲镇子的传闻。'}]}, [])[0]
        rows = [{'text': '这是一段完整镇史。', 'focus': '镇史', 'basis': 'attributed',
                 'source_note': '镇上口传', 'source_delivery': 'original-v2'} for _ in range(4)]
        self.assertEqual(len(_parse_candidates({'candidates': rows}, request, 'request')), 4)
        with self.assertRaisesRegex(ValueError, 'three'):
            _parse_candidates({'candidates': [{k:v for k,v in row.items() if k!='source_delivery'}
                                             for row in rows]}, request, 'request')

    def test_complete_mixed_event_source_keeps_original_fact_partitions(self):
        text = '月亮来到屋檐。\n- **confirmed**：已有季节。\n- **attributed**：镇上传闻。\n- **proposed**：新增风俗。'
        def invoke(*_):
            return json.dumps({'candidates': [{'text': text, 'focus': '镇子的历法',
                'basis': 'confirmed', 'source_note': '既有季节'}]}, ensure_ascii=False)
        with TemporaryDirectory() as directory:
            result = self.processor(directory, invoke).process(text, kind='material', context={'role': 'event-narrator'})
        self.assertEqual(result['candidates'][0]['text'], text)
        self.assertEqual(result['candidates'][0]['basis'], 'proposed')
        self.assertEqual(result['source_status_recovery'][0]['source_states'], ['attributed', 'confirmed', 'proposed'])

    def test_headed_body_is_local_while_retrospective_invitations_remain_notes(self):
        text = '# 交稿\n## 一 · 取材回顾\n旧委托。\n## 二 · 正文\n### 一\n风从窗外进来。\n\n---\n## 三 · 交接\n下一夜。'
        def invoke(_system, prompt):
            task = json.loads(prompt)
            self.assertNotIn('prose', task['task_contract'])
            self.assertNotIn('material_requests', task['task_contract'])
            return json.dumps({'decision_summary': '旧委托。', 'scene_delta': {'next_handoff': ['下一夜。']}}, ensure_ascii=False)
        with TemporaryDirectory() as directory:
            result = self.processor(directory, invoke).process(text, kind='creator', context={})
        self.assertEqual(result['prose'], '### 一\n风从窗外进来。')
        self.assertEqual(result['material_requests'], [])

    def test_empty_planning_units_repair_without_rewriting_successful_metadata(self):
        text = '第一章有一个单元：下雨。'
        calls = []
        def invoke(_system, prompt):
            task = json.loads(prompt); calls.append(task)
            if len(calls) == 1:
                return json.dumps({'chapter': {'chapter_id': 'c1', 'scenes': []}, 'narrative_design': '听雨'}, ensure_ascii=False)
            self.assertEqual(task['repair_paths'], ['/chapter'])
            return json.dumps({'patches': [{'path': '/chapter', 'value': {'chapter_id': 'c1',
                'scenes': [{'name': '下雨'}]}}]}, ensure_ascii=False)
        with TemporaryDirectory() as directory:
            result = self.processor(directory, invoke).process(text, kind='planning-future-chapter',
                context={'chapter_id': 'c1', 'future_scene_count': 1})
        self.assertEqual(len(result['chapter']['scenes']), 1)
        self.assertEqual(result['narrative_design'], '听雨')


if __name__=='__main__':unittest.main()
