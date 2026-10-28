"""A cheaper model view must preserve exact Unicode source references."""
import json
import unittest
from literary_engineering_studio_engine.public.literary import natural_source_index
from literary_engineering_studio.runtimes.natural_source_view import model_source_view
from literary_engineering_studio.runtimes.natural_reference_delivery import decode_reference_delivery
from literary_engineering_studio.runtimes.natural_transport_task import extraction_task


class CompactNaturalSourceTests(unittest.TestCase):
    def setUp(self):
        self.source = ''.join(
            f'第{i}行：她把纸船放进水里，抬头望着屋檐。🙂\r\n\n' for i in range(180))
        self.index = natural_source_index(self.source)

    def test_dense_source_uses_labels_without_duplicate_index_excerpts(self):
        view = model_source_view(self.index, self.source)
        self.assertEqual(view['source_index']['presentation'], 'labelled-lines-v1')
        self.assertEqual(view['source_index']['sha256'], self.index['sha256'])
        self.assertNotIn('blocks', view['source_index'])
        restored = []
        for line in view['source_text'].splitlines(keepends=True):
            if line.startswith('[b'):
                line = line.split('] ', 1)[1]
            restored.append(line)
        self.assertEqual(''.join(restored), self.source)
        legacy = {'source_text': self.source, 'source_index': {'sha256': self.index['sha256'],
            'blocks': [[r['id'], r['beginning'], r['ending']] for r in self.index['blocks']]}}
        size = lambda v: len(json.dumps(v, ensure_ascii=False).encode('utf-8'))
        self.assertLess(size(view), size(legacy) * .75)

    def test_new_view_keeps_original_ids_offsets_and_digest_validation(self):
        first, last = self.index['blocks'][10], self.index['blocks'][13]
        raw = {'prose': {'$source': {'first_block': first['id'], 'last_block': last['id']}}}
        result = decode_reference_delivery(raw, self.source)
        self.assertEqual(result['prose'], self.source[first['start']:last['end']])
        with self.assertRaisesRegex(ValueError, 'digest'):
            decode_reference_delivery({**raw, 'source_sha256': '0' * 64}, self.source)
        with self.assertRaises(ValueError):
            decode_reference_delivery({'prose': {'$source': {'first_block': 'b9999'}}}, self.source)

    def test_short_and_sparse_sources_keep_the_existing_presentation(self):
        short = '原文中的 [b0001] 也只是原文。\n第二行。'
        view = model_source_view(natural_source_index(short), short)
        self.assertEqual(view['source_text'], short)
        self.assertIn('blocks', view['source_index'])
        sparse = '\n'.join('长段落。' * 150 for _ in range(30))
        self.assertEqual(model_source_view(natural_source_index(sparse), sparse)['source_text'], sparse)

    def test_production_task_uses_compact_view_without_changing_context_or_fields(self):
        context = {'role': 'event-narrator', 'request': '保留全部授权资料'}
        contract = {'candidates': [{'text': '原文引用'}]}
        task = extraction_task('material', contract, context, self.index, self.source, {}, {})
        self.assertEqual(task['context'], context)
        self.assertEqual(task['source_index']['presentation'], 'labelled-lines-v1')
        self.assertEqual(task['remaining_fields'], ['candidates'])
        self.assertIn('[b0001] 第0行', task['source_text'])
