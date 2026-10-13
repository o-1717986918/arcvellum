from copy import deepcopy
import unittest
from literary_engineering_studio.runtimes.scene_creator_natural import _validate_transport_intent, _validate_transport_material_plan
from literary_engineering_studio.runtimes.natural_transport_repair import NaturalSourceClarificationError
from literary_engineering_studio.runtimes.natural_field_repair import apply_field_patch, field_repair_task


class CreatorIntentFieldRecoveryTests(unittest.TestCase):
    def test_oversized_intent_preserves_delivery_for_scoped_author_repair(self):
        payload = {'creative_intent': {'reader_experience': '体验' * 301},
                   'prose': '完整的原作者正文。', 'material_requests': [], 'decision_summary': '原札记'}
        original = deepcopy(payload)
        with self.assertRaises(NaturalSourceClarificationError) as caught:
            _validate_transport_intent(payload)
        error = caught.exception
        self.assertEqual(error.fields, ('/creative_intent',))
        self.assertEqual(payload, original)
        self.assertEqual(error.payload, original)
        task = field_repair_task('保存的完整原回答', error.payload, error.fields, {})
        self.assertEqual(task['allowed_paths'], ['/creative_intent'])
        patched = apply_field_patch(error.payload, {'patches': [{'path': '/creative_intent',
            'value': {'reader_experience': '体验两人日常', 'reader_knows': '本场规矩',
                      'reader_misreads': '', 'withheld': ''}}]}, error.fields)
        _validate_transport_intent(patched)
        self.assertEqual(patched['prose'], original['prose'])
        self.assertEqual(patched['decision_summary'], original['decision_summary'])

    def test_compatibility_empty_update_and_missing_intent_remain_readable(self):
        _validate_transport_intent({})
        _validate_transport_intent({'creative_intent': dict.fromkeys(
            ('reader_experience','reader_knows','reader_misreads','withheld'), '')})

    def test_known_and_withheld_limits_are_not_relaxed(self):
        with self.assertRaises(NaturalSourceClarificationError):
            _validate_transport_intent({'creative_intent': {'reader_experience': '体验',
                                                           'withheld': '秘' * 401}})

    def test_empty_plan_requires_the_author_to_choose_without_changing_invitations(self):
        payload = {'material_requests': [{'kind':'environment'}],
                   'material_plan': {'required_kinds': [], 'reason': ''}, 'prose': ''}
        original = deepcopy(payload)
        with self.assertRaises(NaturalSourceClarificationError) as caught:
            _validate_transport_material_plan(payload)
        self.assertEqual(caught.exception.fields, ('/material_plan',))
        self.assertEqual(payload, original)
        repaired = apply_field_patch(payload, {'patches':[{'path':'/material_plan',
            'value':{'required_kinds':['environment'], 'reason':'建立本场空间'}}]}, caught.exception.fields)
        _validate_transport_material_plan(repaired)
        self.assertEqual(repaired['material_requests'], original['material_requests'])

    def test_absent_plan_remains_available_for_the_existing_pending_plan_flow(self):
        _validate_transport_material_plan({'material_requests':[{'kind':'environment'}]})


if __name__ == '__main__':
    unittest.main()
