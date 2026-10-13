from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from literary_engineering_studio.runtimes.scene_natural_output import NaturalOutputProcessor
from literary_engineering_studio.runtimes.natural_material_response import whole_material_response


class WholeMaterialResponseTests(unittest.TestCase):
    def test_literal_environment_uses_no_second_model(self):
        for role,text in [('environment-writer','锅沿还热着。\n\n木板在脚下松了一点。')]:
            with TemporaryDirectory() as tmp:
                def unavailable(*_):
                    self.fail('a complete bounded response requires no extraction model')
                output=NaturalOutputProcessor(Path(tmp),'transport',unavailable).process(text,kind='material',context={'role':role})
                self.assertEqual(output['candidates'][0]['text'],text)
                self.assertEqual(next(Path(tmp).rglob('original.md')).read_text(encoding='utf-8'),text)

    def test_first_person_actor_text_requires_complete_speech_and_action_annotation(self):
        text='我把碗扶正。\n\n“添不添？”我问。'
        self.assertIsNone(whole_material_response(text, {'role':'character-actor'}))
        import json
        from literary_engineering_studio.runtimes.scene_creator_v2_materials import _parse_candidates
        from literary_engineering_studio_engine.public.literary import SceneMaterialRequestV3
        def extract(system,prompt):
            task=json.loads(prompt)
            self.assertIn('目标人物本人', task['actor_annotation'])
            return json.dumps({'candidates':[{'text':text,'focus':'询问',
                'spoken':'添不添？','first_person_action':'我把碗扶正。','private_impulse':''}]},ensure_ascii=False)
        with TemporaryDirectory() as tmp:
            result=NaturalOutputProcessor(Path(tmp),'transport',extract).process(text,kind='material',
                context={'role':'character-actor','request':{'target':'阿青'}})
            candidate,=_parse_candidates(result,SceneMaterialRequestV3('actor','阿青','询问','此刻','空碗','来话'),'id')
            self.assertIn('添不添？',candidate['text'])
            self.assertIn('我把碗扶正',candidate['text'])

    def test_event_provenance_large_response_and_ambiguous_actor_still_need_transport(self):
        self.assertIsNone(whole_material_response('旧日里发生了什么。',{'role':'event-narrator'}))
        self.assertIsNone(whole_material_response('风'*2401,{'role':'environment-writer'}))
        self.assertIsNone(whole_material_response('“我留下。”他说。',{'role':'character-actor'}))
