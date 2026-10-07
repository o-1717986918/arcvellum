from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from literary_engineering_studio.runtimes.scene_natural_output import NaturalOutputProcessor
from literary_engineering_studio.runtimes.natural_material_response import whole_material_response


class WholeMaterialResponseTests(unittest.TestCase):
    def test_literal_actor_and_environment_use_no_second_model(self):
        for role,text in [('character-actor','我把碗扶正。\n\n“添不添？”我问。'),('environment-writer','锅沿还热着。\n\n木板在脚下松了一点。')]:
            with TemporaryDirectory() as tmp:
                def unavailable(*_):
                    self.fail('a complete bounded response requires no extraction model')
                output=NaturalOutputProcessor(Path(tmp),'transport',unavailable).process(text,kind='material',context={'role':role})
                self.assertEqual(output['candidates'][0]['text'],text)
                self.assertEqual(next(Path(tmp).rglob('original.md')).read_text(encoding='utf-8'),text)

    def test_event_provenance_large_response_and_ambiguous_actor_still_need_transport(self):
        self.assertIsNone(whole_material_response('旧日里发生了什么。',{'role':'event-narrator'}))
        self.assertIsNone(whole_material_response('风'*2401,{'role':'environment-writer'}))
        self.assertIsNone(whole_material_response('“我留下。”他说。',{'role':'character-actor'}))
