"""Recover formatter ordering using verified original spans, never actor invention."""
from tempfile import TemporaryDirectory
from pathlib import Path
from copy import deepcopy
import unittest
from literary_engineering_studio.runtimes.natural_actor_transport import seed_actor_response
from literary_engineering_studio.runtimes.natural_reference_delivery import decode_reference_delivery


class ActorAnnotationRecoveryTests(unittest.TestCase):
    def test_grouped_annotations_return_to_source_order_without_changing_any_text(self):
        body='我放下碗。\n\n“够了。”\n\n我坐下来。'
        raw={'candidates':[{'annotations':[{'kind':'spoken','text':'“够了。”'},
            {'kind':'first_person_action','text':'我坐下来。'},
            {'kind':'first_person_action','text':'我放下碗。'}]}]}
        before=deepcopy(raw)
        result=decode_reference_delivery(seed_actor_response(raw,body,'material',{'role':'character-actor'}),body)
        row=result['candidates'][0]
        self.assertEqual(row['text'],body)
        self.assertEqual(row['annotation_order_recovery']['source_order'],[2,0,1])
        self.assertEqual([a['text'] for a in row['annotations']],['我放下碗。','“够了。”','我坐下来。'])
        for span,annotation in zip(row['annotation_spans'],row['annotations']):
            self.assertEqual(body[span['start']:span['end']],annotation['text'])
        self.assertEqual(raw,before)

    def test_incomplete_positions_are_not_sorted_by_guessing(self):
        body='我放下碗。\n\n“够了。”\n\n我放下碗。\n\n我坐下来。'
        raw={'candidates':[{'annotations':[{'kind':'first_person_action','text':'我坐下来。'},
            {'kind':'first_person_action','text':'我放下碗。'},{'kind':'spoken','text':'“够了。”'}]}]}
        with self.assertRaisesRegex(ValueError,'every position verified'):
            decode_reference_delivery(seed_actor_response(raw,body,'material',{'role':'character-actor'}),body)
