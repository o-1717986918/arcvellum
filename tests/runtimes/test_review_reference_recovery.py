from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from literary_engineering_studio.runtimes.evidence_patch_source import resolve_evidence_patches, prose_evidence_source
from literary_engineering_studio.runtimes.natural_transport_repair import NaturalSourceClarificationError
from literary_engineering_studio.runtimes.scene_natural_output import NaturalOutputProcessor


class ReviewReferenceRecoveryTests(unittest.TestCase):
    def test_all_invalid_hashes_report_exact_fields_without_changing_the_reply(self):
        body = '当前第一段。\n\n当前第二段。'
        refs = [{'prose_sha256': 'old', 'prose_block': 'p0001'}, {'prose_sha256': 'old', 'prose_block': 'p0002'}]
        reply = {'patches': [{'path': '/consistency_checks', 'value': [{'evidence': refs}]}]}
        before = deepcopy(reply)
        with self.assertRaises(ValueError) as caught:
            resolve_evidence_patches(reply, body, ['/consistency_checks'])
        self.assertEqual(caught.exception.fields, ('/consistency_checks/0/evidence/0/prose_sha256',
                                                 '/consistency_checks/0/evidence/1/prose_sha256'))
        self.assertEqual(reply, before)

    def test_saved_semantic_review_patch_with_wrong_hash_needs_author_repair_without_extraction(self):
        record = {'decision': 'revise', 'consistency_checks': []}
        first = '```json\n'+json.dumps({'review_record': record})+'\n```'
        patch = {'patches': [{'path': '/consistency_checks', 'value': [{'evidence': [
            {'prose_sha256': 'old', 'prose_block': 'p0001'}]}]}]}
        combined = first+'\n\n【原作者指定字段补交】\n'+json.dumps(patch)
        with TemporaryDirectory() as directory:
            processor = NaturalOutputProcessor(Path(directory), 'extractor',
                lambda *_args: self.fail('explicit invalid reference must not trigger transport retries'))
            with self.assertRaises(NaturalSourceClarificationError) as caught:
                processor.process(combined, kind='review', context={
                    'creation_integrity_contract': 'scene-consistency/v1', 'prose': '当前正文。'})
            self.assertEqual(caught.exception.fields, ('/consistency_checks/0/evidence/0/prose_sha256',))
            self.assertEqual(caught.exception.source_text, combined)

    def test_known_reference_restores_only_its_current_body_block(self):
        body = '第一段。\n\n第二段。'
        ref = {'prose_sha256': prose_evidence_source(body)['sha256'], 'prose_block': 'p0002'}
        reply = {'patches': [{'path': '/strengths/0/evidence', 'value': ref}]}
        self.assertEqual(resolve_evidence_patches(reply, body, ['/strengths/0/evidence'])['patches'][0]['value'], '第二段。')
        with self.assertRaises(ValueError):
            resolve_evidence_patches(reply, '另一版正文。', ['/strengths/0/evidence'])


if __name__ == '__main__':
    unittest.main()
