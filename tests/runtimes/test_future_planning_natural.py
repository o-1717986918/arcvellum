import unittest
from literary_engineering_studio.runtimes.future_planning_natural import future_planning_delivery


class FuturePlanningNaturalTests(unittest.TestCase):
    def test_failure_in_later_chapter_resumes_without_redeveloping_accepted_prefix(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        calls=[]
        def deliver(root,gateway,prompt,*,kind,context,**kwargs):
            calls.append((kind,context.get('chapter_id')))
            if kind=='planning-future-outline':
                return {'chapters':[{'chapter_id':name,'future_scene_count':1} for name in ('c1','c2')]}
            if context['chapter_id']=='c2' and calls.count((kind,'c2'))==1:
                raise ValueError('current chapter incomplete')
            return {'chapter':{'chapter_id':context['chapter_id'],'scenes':[{'name':'文学单元'}]}}
        with TemporaryDirectory() as temporary:
            kwargs={'root':Path(temporary),'gateway':None,'prompt':'作者方向','context':{'chapter_counts':{'c1':1,'c2':1}},'layer_id':'planning.v2.future'}
            with self.assertRaisesRegex(ValueError,'incomplete'):
                future_planning_delivery(deliver,**kwargs)
            result=future_planning_delivery(deliver,**kwargs)
        self.assertEqual(len(result['chapters']),2)
        self.assertEqual(calls,[('planning-future-outline',None),('planning-future-chapter','c1'),('planning-future-chapter','c2'),('planning-future-chapter','c2')])

    def test_explicit_percentage_weights_become_equivalent_ratios_with_source_retained(self):
        from literary_engineering_studio.runtimes.planning_reading import normalize_planning_weights
        original = {'chapters': [{'length_weight': '36%', 'scenes': [{'length_weight': ' 12.5 % '}, {'length_weight': 2}]}]}
        result = normalize_planning_weights(original)
        self.assertEqual(result['chapters'][0]['length_weight'], .36)
        self.assertEqual(result['chapters'][0]['scenes'][0]['length_weight'], .125)
        self.assertEqual(original['chapters'][0]['length_weight'], '36%')
        self.assertEqual(result['weight_transport_resolution'][0]['original'], '36%')

    def test_outline_is_developed_by_chapter_and_keeps_whole_book_strategy(self):
        calls = []
        def deliver(root, gateway, prompt, *, kind, context, **kwargs):
            calls.append((kind, prompt))
            if kind == 'planning-future-outline':
                return {'narrative_design': {'narrator_voice': '热闹讲述'}, 'chapters': [
                    {'chapter_id': 'chapter_0001', 'future_scene_count': 1, 'length_weight': 2},
                    {'chapter_id': 'chapter_0002', 'future_scene_count': 2, 'length_weight': 3}]}
            count = context['future_scene_count']
            return {'chapter': {'chapter_id': context['chapter_id'], 'scenes': [{'name': '单元'+str(i)} for i in range(count)]}}
        result = future_planning_delivery(deliver, None, None, '作者方向', layer_id='planning.v2.future',
            context={'chapter_counts': {'chapter_0001': 2, 'chapter_0002': 2}})
        self.assertEqual([kind for kind, _ in calls], ['planning-future-outline', 'planning-future-chapter', 'planning-future-chapter'])
        self.assertEqual([len(row['scenes']) for row in result['chapters']], [1, 2])
        self.assertEqual(result['chapters'][1]['length_weight'], 3)
        self.assertIn('热闹讲述', calls[-1][1])
        self.assertIn('单元0', calls[-1][1])
        self.assertIn('未来正文单元数量：', calls[-1][1])
        self.assertIn('相对篇幅权重：', calls[-1][1])
        self.assertNotIn('"narrative_design":', calls[-1][1])
        self.assertNotIn('"scenes":', calls[-1][1])

    def test_wrong_chapter_order_is_rejected_before_development(self):
        def deliver(*args, **kwargs):
            return {'chapters': [{'chapter_id': 'other', 'future_scene_count': 2}]}
        with self.assertRaisesRegex(ValueError, 'identities'):
            future_planning_delivery(deliver, None, None, '方向', layer_id='planning.v2.future', context={'chapter_counts': {'chapter_0001': 2}})
