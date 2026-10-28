"""Narrow structural normalization remains auditable and fails closed."""
from pathlib import Path
import json
import tempfile
import unittest
from literary_engineering_studio.runtimes.transport_json_closure import recover_object_terminator
from literary_engineering_studio.runtimes.scene_natural_output import NaturalOutputProcessor
from literary_engineering_studio_engine.public.prompting import prompt_layer_spec


class TransportJsonClosureTests(unittest.TestCase):
    def test_fenced_receipt_points_to_the_original_response_offset(self):
        fence = chr(96) * 3
        raw = '\n ' + fence + 'json\n{"items":[{"value":"原文"]}\n' + fence + '\n'
        payload, receipt = recover_object_terminator(raw)
        repaired = raw[:receipt['inserted_at']] + '}' + raw[receipt['inserted_at']:]
        self.assertEqual(json.loads(repaired.strip()[7:-3]), payload)
        self.assertEqual(payload, {'items':[{'value':'原文'}]})

    def test_one_missing_object_close_preserves_nested_values_and_escaped_quotes(self):
        valid = {'candidates': [{'annotations': [{'kind':'spoken',
            'text': {'$source': {'first_block':'b0001','start_anchor':'她说："留下。"'}}}]}]}
        text = json.dumps(valid, ensure_ascii=False, separators=(',', ':'))
        broken = text.replace('}}]}', '}]}', 1)
        result = recover_object_terminator(broken)
        self.assertIsNotNone(result)
        payload, receipt = result
        self.assertEqual(payload, valid)
        self.assertFalse(receipt['values_changed'])
        self.assertNotEqual(receipt['raw_sha256'], receipt['normalized_sha256'])

    def test_missing_values_duplicate_keys_and_multiple_closures_remain_invalid(self):
        for text in ['{"a":[{"b":]}', '{"a":[{"b":1,"b":2]}',
                     '{"a":[{"b":[{"c":1]]}', '{"a":[{"b":"unterminated]}',
                     '{"a":[{"b":1]} trailing', '{"a":[{"b":1}]}']:
            with self.subTest(text=text):
                self.assertIsNone(recover_object_terminator(text))

    def test_source_transport_persists_receipt_and_can_reuse_the_source_without_model_calls(self):
        source = '她把旧铜铃系回门边，风过来时，响声落在门后。'
        valid = {'candidates':[{'text':source,'basis':'proposed','source_note':'新描写'}]}
        text = json.dumps(valid, ensure_ascii=False, separators=(',', ':'))
        broken = text.replace('"}]', '"]', 1)
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            processor = NaturalOutputProcessor(root,
                prompt_layer_spec('scene.v2.transport.extractor').default_text,
                lambda system, prompt: calls.append(prompt) or broken)
            first = processor.process(source, kind='material', context={'role':'event-narrator'})
            second = processor.process(source, kind='material', context={'role':'event-narrator'})
            self.assertEqual(first['candidates'][0]['text'], source)
            self.assertEqual(second['candidates'][0]['text'], source)
            self.assertEqual(len(calls), 1)
            receipt_path = next(root.rglob('*.syntax-recovery.json'))
            receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
            self.assertEqual(receipt['source_sha256'], receipt_path.parent.name)
            self.assertEqual(next(root.rglob('*.extraction-1.md')).read_text(encoding='utf-8'), broken)
