from copy import deepcopy
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from literary_engineering_studio.runtimes.natural_authored_records import (
    authored_record, author_field_present, restore_authored_consistency_layout,
)


def source(record):
    return '## 正文\n原作者正文。\n\n```json\n' + json.dumps({'creator_record': record}, ensure_ascii=False) + '\n```'


def append_patch(text, patch, fenced=False):
    value = json.dumps({'patches': patch}, ensure_ascii=False)
    return text + '\n\n【原作者指定字段补交】\n' + ('```json\n'+value+'\n```' if fenced else value)


class NaturalAuthoredRecordReplayTests(unittest.TestCase):
    def test_single_patch_wrapper_is_structural_and_cannot_replace_another_record(self):
        from literary_engineering_studio.runtimes.natural_authored_records import replay_authored_patch
        original = source({'consistency_record': {'facts': [{'source_state': 'attributed'}]}})
        path = '/consistency_record/facts/0/source_state'
        reply = json.dumps({'creator_record': {'patches': [{'path': path, 'value': 'new'}]}})
        self.assertEqual(replay_authored_patch({}, original, reply, [path])['patches'][0]['value'], 'new')
        combined = original+'\n\n【原作者指定字段补交】\n'+reply
        self.assertEqual(authored_record(combined,'creator_record')['consistency_record']['facts'][0]['source_state'],'new')
        ambiguous = json.dumps({'creator_record': {'patches': [{'path': path, 'value': 'new'}], 'facts': []}})
        self.assertIsNone(authored_record(original+'\n\n【原作者指定字段补交】\n'+ambiguous,'creator_record'))

    def test_partial_author_patch_and_cache_replay_need_no_transport_call(self):
        from literary_engineering_studio.runtimes.scene_natural_output import NaturalOutputProcessor
        record = {'material_requests': [], 'material_decisions': [], 'decision_summary': '原作者的叙述判断',
                  'scene_delta': {}, 'consistency_record': {'canon_change': False, 'no_canon_change_reason': '没有新增Canon',
                      'facts': [{'subject': '她', 'predicate': '说话', 'value': '已经说了', 'evidence': '原作者正文。',
                                 'source_state': 'attributed', 'durable': False}]}}
        original = source(record)
        reply = json.dumps({'patches': [{'path': '/consistency_record/facts/0/source_state', 'value': 'new'}]})
        context = {'creation_integrity_contract': 'scene-consistency/v1', 'available_material_ids': []}
        with TemporaryDirectory() as directory:
            processor = NaturalOutputProcessor(Path(directory), 'extractor',
                lambda *_args: self.fail('explicit author JSON must not invoke a model'))
            payload = processor.process(original, kind='creator', context=context)
            for _ in range(2):
                patched = processor.process_field_repair(original, reply, kind='creator', context=context,
                    payload=payload, fields=['/consistency_record/facts/0/source_state'])
                self.assertEqual(patched['prose'], payload['prose'])
                self.assertEqual(patched['consistency_record']['facts'][0]['source_state'], 'new')
                self.assertEqual(patched['__transport']['model_calls'], 0)

    def test_nested_patch_sequence_is_authored_and_previous_value_is_not_current(self):
        original = {'consistency_record': {'facts': [{'source_state': 'attributed'}]}}
        text = append_patch(source(original), [{'path': '/consistency_record/facts/0/source_state', 'value': 'new'}])
        text = append_patch(text, [{'path': '/consistency_record/facts/0/source_state', 'value': 'changed'}], fenced=True)
        current = {'facts': [{'source_state': 'changed'}]}
        self.assertTrue(author_field_present(text, 'consistency_record', current))
        self.assertFalse(author_field_present(text, 'consistency_record', original['consistency_record']))
        self.assertEqual(authored_record(text, 'creator_record')['consistency_record'], current)

    def test_outer_dispositions_restore_exact_author_values_without_mutating_source(self):
        prior = [{'proposal_id': 'original-id', 'action': 'retain', 'reason': '原作者的理由'}]
        record = {'prior_delta_dispositions': prior, 'consistency_record': {'facts': []}}
        before = deepcopy(record)
        text = source(record)
        projected = authored_record(text, 'creator_record')
        self.assertEqual(record, before)
        self.assertEqual(projected['consistency_record']['prior_delta_dispositions'], prior)
        payload = deepcopy(record)
        restore_authored_consistency_layout(text, payload)
        self.assertTrue(author_field_present(text, 'consistency_record', payload['consistency_record']))
        self.assertEqual(payload['prior_delta_dispositions'], prior)

    def test_conflicting_layouts_and_duplicate_records_are_not_chosen(self):
        record = {'prior_delta_dispositions': [], 'consistency_record': {'prior_delta_dispositions': [{'action': 'withdraw'}]}}
        text = source(record)
        self.assertIsNone(authored_record(text, 'creator_record'))
        self.assertFalse(author_field_present(text, 'consistency_record', record['consistency_record']))
        repeated = source({'consistency_record': {'facts': []}}) * 2
        self.assertIsNone(authored_record(repeated, 'creator_record'))

    def test_malformed_or_prose_changing_patch_never_proves_authorship(self):
        for patch in ([{'path': '/prose', 'value': '伪造正文'}],
                      [{'path': '/consistency_record/facts/9/source_state', 'value': 'new'}],
                      [{'path': '/consistency_record', 'op': 'increment', 'value': {}}]):
            text = append_patch(source({'consistency_record': {'facts': []}}), patch)
            self.assertIsNone(authored_record(text, 'creator_record'))
            self.assertFalse(author_field_present(text, 'consistency_record', {'facts': []}))


if __name__ == '__main__':
    unittest.main()
