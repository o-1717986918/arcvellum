"""Natural literary identities remain distinct and expose one free style field."""
import unittest
from literary_engineering_studio_engine.public.prompting import prompt_layer_spec
from literary_engineering_studio_engine.public.literary import parse_scene_material_requests_v3

class NaturalPromptContractTests(unittest.TestCase):
    def test_creative_identities_are_positive_and_style_ready(self):
        for kind in ('creator.identity','review','material.environment','material.character-description',
                     'material.event-narration','material.scene-description'):
            text=prompt_layer_spec('scene.v2.'+kind).default_text
            self.assertEqual(text.count('{{STYLE_DIRECTION}}'),1)
            for phrase in ('你不能','你不是','不要','禁止','权限','JSON'):
                self.assertNotIn(phrase,text)
        actor=prompt_layer_spec('scene.v2.material.actor').default_text
        self.assertEqual(actor.count('【'),16)
        self.assertNotIn('STYLE_DIRECTION',actor)

    def test_free_style_field_roundtrips(self):
        request={'kind':'environment','target':'雨巷','purpose':'让等待可感',
                 'scene_moment':'敲门之前','cue':'雨停后的巷子','author_prompt':'写出水汽仍留在身体上的片刻。',
                 'style_direction':'句子可以回旋，让湿润的触感逐渐靠近。'}
        result=parse_scene_material_requests_v3({'material_requests':[request]},[])
        self.assertEqual(result[0].to_dict()['style_direction'],request['style_direction'])
        request['style_direction']='文' * 8001
        with self.assertRaises(ValueError):
            parse_scene_material_requests_v3({'material_requests':[request]},[])

if __name__=='__main__': unittest.main()

