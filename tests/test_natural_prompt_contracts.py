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
            for phrase in ('你不能','你不是','不要','禁止','不得','无权','没有权限','JSON'):
                self.assertNotIn(phrase,text)
        actor=prompt_layer_spec('scene.v2.material.actor').default_text
        self.assertEqual(actor.count('【'),16)
        self.assertNotIn('STYLE_DIRECTION',actor)

    def test_each_material_creator_has_its_own_literary_method_and_frozen_version(self):
        markers = {
            'environment': ('地方的时空', '身体里的感知', '空间给予的行动'),
            'character-description': ('观察位置', '身体', '他人目光'),
            'event-narration': ('因果脉络', '切入时刻', '讲述位置'),
            'scene-description': ('空间框架', '动作的接续', '心中地图'),
        }
        texts = {}
        for kind, phrases in markers.items():
            spec = prompt_layer_spec('scene.v2.material.' + kind)
            self.assertEqual(spec.package_version, 5)
            self.assertTrue(all(phrase in spec.default_text for phrase in phrases))
            self.assertEqual(spec.default_text.count('{{STYLE_DIRECTION}}'), 1)
            texts[kind] = spec.default_text
        self.assertEqual(len(set(texts.values())), 4)
        self.assertEqual(prompt_layer_spec('scene.v2.material.actor').package_version, 3)

    def test_free_style_field_roundtrips(self):
        request={'kind':'environment','target':'雨巷','purpose':'让等待可感',
                 'scene_moment':'敲门之前','cue':'雨停后的巷子','author_prompt':'写出水汽仍留在身体上的片刻。',
                 'style_direction':'句子可以回旋，让湿润的触感逐渐靠近。'}
        result=parse_scene_material_requests_v3({'material_requests':[request]},[])
        self.assertEqual(result[0].to_dict()['style_direction'],request['style_direction'])
        request['style_direction']='文' * 8001
        with self.assertRaises(ValueError):
            parse_scene_material_requests_v3({'material_requests':[request]},[])

    def test_review_and_revision_prompts_separate_repairs_from_optional_exploration(self):
        review = prompt_layer_spec('scene.v2.review').default_text
        protocol = prompt_layer_spec('scene.v2.review.protocol').default_text
        revision = prompt_layer_spec('scene.v2.creator.revise').default_text

        for phrase in ('已经成立的文学经验', '影响本场成立的主要问题', '可选探索', '正文证据'):
            self.assertIn(phrase, review)
        for phrase in ('已经改正', '仍在', '变成新问题', '无法判断'):
            self.assertIn(phrase, protocol)
        for phrase in ('优先处理真正损害阅读的地方', '保留前稿已经形成', '完整审读信'):
            self.assertIn(phrase, revision)
        for text in (review, protocol, revision):
            for phrase in ('你不能', '你不是', '不要', '不得', '无权', '没有权限'):
                self.assertNotIn(phrase, text)

if __name__=='__main__': unittest.main()

