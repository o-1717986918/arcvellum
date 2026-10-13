"""A preview cap cannot remove author records from actual execution results."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from literary_engineering_studio.runtimes.pi_worker_protocol import last_worker_result, public_event_data
from literary_engineering_studio.runtimes.natural_local_delivery import local_creator_fields
from literary_engineering_studio.runtimes.scene_creator_delivery_source import recover_saved_creator_delivery


class CompleteReplyIntegrityTests(unittest.TestCase):
    def test_actual_reply_and_initialization_remain_complete_while_preview_stays_bounded(self):
        text='原作者文字。'*4000+'\n```json\n{"creator_record":{"scene_delta":{}}}\n```'
        with TemporaryDirectory() as temporary:
            path=Path(temporary)/'runtime.output.log'
            data={'status':'completed','answer':text,'initializationAnswer':text,'api_key':'secret'}
            path.write_text(json.dumps({'event':'runner.worker.result','data':data},ensure_ascii=False),encoding='utf-8')
            result=last_worker_result(path)
            self.assertEqual(result['answer'],text)
            self.assertEqual(result['initializationAnswer'],text)
            self.assertNotIn('api_key',result)
            self.assertEqual(len(public_event_data(data)['answer']),20_000)

    def test_author_record_after_body_is_detached_even_when_notes_precede_the_body(self):
        body='她把碗放回桌上。\n\n他坐了下来。'
        source='## 创作札记\n沿已发生的动作展开。\n\n## 正文\n'+body+'\n\n```json\n'+json.dumps(
            {'creator_record':{'scene_delta':{},'decision_summary':'完整作者判断','material_requests':[]}},ensure_ascii=False)+'\n```'
        value=local_creator_fields(source,'creator',{'creation_integrity_contract':'scene-consistency/v1'})
        self.assertEqual(value['prose'],body)
        self.assertEqual(value['decision_summary'],'完整作者判断')

    def test_completed_original_can_restore_only_its_exact_saved_preview_and_input(self):
        answer='## 正文\n'+'她把碗放下。'*4000
        prompt='任务一'
        with TemporaryDirectory() as temporary:
            root=Path(temporary);run=root/'pi-conversations/worker/runs/run';run.mkdir(parents=True)
            (run/'conversation.prompt.md').write_text(json.dumps({'schema':'arcvellum/scene-creator/v2',
                'call_purpose':'creator','prompt':prompt}),encoding='utf-8')
            events=[{'event':'runner.conversation.result','data':{'answer':answer}},
                    {'event':'runner.worker.result','data':{'status':'completed','answer':answer}}]
            output=run/'runtime.output.log';output.write_text('\n'.join(json.dumps(e) for e in events),encoding='utf-8')
            short=answer[:20_000]
            self.assertEqual(recover_saved_creator_delivery(short,prompt,root,root/'archive'),answer)
            self.assertEqual(recover_saved_creator_delivery(short,'其他任务',root,root/'archive'),short)
            events[-1]['data']['status']='blocked'
            output.write_text('\n'.join(json.dumps(e) for e in events),encoding='utf-8')
            self.assertEqual(recover_saved_creator_delivery(short,prompt,root,root/'archive'),short)
