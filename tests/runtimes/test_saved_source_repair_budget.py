from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from literary_engineering_studio.runtimes.scene_creator_natural import NaturalCreatorMixin
from literary_engineering_studio.runtimes.natural_transport_repair import NaturalSourceClarificationError
from literary_engineering_studio.runtimes.source_repair_budget import SourceRepairBudget, text_digest


class Driver(NaturalCreatorMixin):
    def __init__(self, root):
        self.root, self._cache_hits = root, 0

    def _cache_path(self, transaction_id, relative):
        return self.root / relative


class Processor:
    system_prompt = 'same frozen extractor'

    def __init__(self, root):
        self.root = root

    def process_field_repair(self, source, reply, *, kind, context, payload, fields):
        result = deepcopy(payload)
        result['consistency_record'] = json.loads(reply)['patches'][0]['value']
        return result

    def revalidate_record(self, source, payload, kind, context):
        return deepcopy(payload)


class SavedSourceRepairBudgetTests(unittest.TestCase):
    def test_saved_exact_reply_is_replayed_after_exhaustion_without_claiming_again(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            processor = Processor(root / 'v2')
            driver = Driver(root)
            error = NaturalSourceClarificationError('补齐作者记录', fields=('/consistency_record',),
                payload={'prose': '当前正文', 'consistency_record': None})
            source, context = '原作者交付', {'prose': '当前正文'}
            budget = SourceRepairBudget(processor.root, 'creator', text_digest(source))
            answer = json.dumps({'patches': [{'path': '/consistency_record', 'value': {'facts': []}}]})
            driver._source_field_repair('tx', processor, source, 'creator', context, error, lambda *_: answer)
            for checkpoint in budget.root.glob('*.completed.json'):
                checkpoint.unlink()
            for index in range(3):
                budget.claim('source-author', str(index))
            before = budget.path.read_bytes()
            result = driver._source_field_repair('tx', processor, source, 'creator', context, error,
                lambda *_: self.fail('saved exact repair must not call a model'))
            self.assertEqual(result['consistency_record'], {'facts': []})
            self.assertEqual(before, budget.path.read_bytes())
            self.assertEqual(driver._cache_hits, 1)
            self.assertEqual(driver._source_field_repair('tx', processor, source, 'creator', context, error,
                lambda *_: self.fail('completed replay must not call a model')), result)
            self.assertEqual(before, budget.path.read_bytes())
            with self.assertRaises(NaturalSourceClarificationError):
                driver._source_field_repair('tx', processor, source, 'creator', {**context, 'canon_revision': 2}, error,
                    lambda *_: self.fail('changed context cannot reuse the saved reply'))

    def test_fresh_call_consumes_one_claim_and_restart_reuses_the_delivery(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            processor, driver = Processor(root / 'v2'), Driver(root)
            error = NaturalSourceClarificationError('补齐作者记录', fields=('/consistency_record',),
                payload={'prose': '当前正文', 'consistency_record': None})
            calls = []
            def invoke(task):
                calls.append(task)
                return json.dumps({'patches': [{'path': '/consistency_record', 'value': {'facts': []}}]})
            first = driver._source_field_repair('tx', processor, 'source', 'creator', {}, error, invoke)
            second = Driver(root)._source_field_repair('tx', processor, 'source', 'creator', {}, error, invoke)
            self.assertEqual(first, second)
            self.assertEqual(len(calls), 1)
            state = json.loads(SourceRepairBudget(processor.root, 'creator', text_digest('source')).path.read_text())
            self.assertEqual(len(state['calls']), 1)
