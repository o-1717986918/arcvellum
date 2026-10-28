"""Whole-object syntax repair must change the request instead of replaying failure."""
import json
import tempfile
import unittest
from pathlib import Path
from literary_engineering_studio.runtimes.scene_natural_output import NaturalOutputProcessor
from literary_engineering_studio_engine.public.prompting import prompt_layer_spec


class TransportSyntaxRetryTests(unittest.TestCase):
    def test_invalid_json_retry_contains_feedback_and_can_escape_identical_answer_cache(self):
        source = '雨水沿门框滴下来，她把碗往桌里推了推。'
        invalid = '{"candidates":[{"text":"' + source + '","basis":"proposed","source_note":"新描写"}]'
        calls, cache = [], {}
        def invoke(_system, prompt):
            calls.append(json.loads(prompt))
            if prompt not in cache:
                cache[prompt] = invalid if len(cache) == 0 else json.dumps({
                    'candidates': [{'text': source, 'basis': 'proposed', 'source_note': '新描写'}]},
                    ensure_ascii=False)
            return cache[prompt]
        with tempfile.TemporaryDirectory() as directory:
            processor = NaturalOutputProcessor(
                Path(directory), prompt_layer_spec('scene.v2.transport.extractor').default_text, invoke)
            result = processor.process(source, kind='material', context={'role': 'event-narrator'})
        self.assertEqual(result['candidates'][0]['text'], source)
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(cache), 2)
        self.assertNotIn('transport_feedback', calls[0])
        self.assertIn('JSON', calls[1]['transport_feedback']['issue'])
        self.assertIn('完整对象', calls[1]['transport_feedback']['request'])
        self.assertEqual(calls[0]['source_text'], calls[1]['source_text'])
        self.assertNotIn('repair_paths', calls[1])

    def test_repeated_invalid_delivery_remains_blocked_after_bounded_repair(self):
        source = '她把旧铜铃系回门边。'
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            processor = NaturalOutputProcessor(Path(directory), 'technical extractor',
                lambda system, prompt: calls.append(prompt) or '{broken')
            for _ in range(2):
                with self.assertRaises(ValueError):
                    processor.process(source, kind='material', context={'role': 'event-narrator'})
        self.assertEqual(len(calls), 2)
        self.assertNotEqual(calls[0], calls[1])
