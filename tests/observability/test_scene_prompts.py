import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from literary_engineering_studio.observability.scene_prompts import scene_prompt_detail
from literary_engineering_studio.application.style.transaction_bundle import TransactionStyleBundleV1


class ScenePromptInspectionTests(unittest.TestCase):
    def test_frozen_bundle_and_measurements_are_linked_to_edit_stages(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / 'scene-transactions/tx'
            directory.mkdir(parents=True)
            def save(name, value):
                path = directory/name; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value), encoding='utf-8')
            bundle = TransactionStyleBundleV1('tx', 2, {'preset_id': 'world'}, {'assembled': {'content': '冻结文风'}}, {'enabled': True}, True).to_dict()
            save('transaction_style_bundle.json', bundle)
            save('less-ai-tone/create-one/report.json', {'phase': 'create', 'original_sha256': 'original', 'cleaned_sha256': 'edited'})
            save('stylometry/original.json', {'text_sha256': 'original', 'result': {'targets': [{'id': 'sentence_length_han', 'observed': 21}]}})
            save('stylometry/edited.json', {'text_sha256': 'edited', 'result': {'targets': [{'id': 'sentence_length_han', 'observed': 25}]}})
            result = scene_prompt_detail(root, [SimpleNamespace(transaction_id='tx', scene_id='scene_0001')], 'tx')
            self.assertEqual(result['style_bundle'], bundle)
            stages = {row['text_sha256']: row['stages'] for row in result['measurements']}
            self.assertEqual(stages['original'], ['create · 编辑前原稿'])
            self.assertEqual(stages['edited'], ['create · 编辑后正文'])
            self.assertEqual(json.loads((directory/'transaction_style_bundle.json').read_text()), bundle)

    def test_project_membership_is_checked_before_reading_any_transaction(self):
        with TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, 'does not belong'):
                scene_prompt_detail(Path(temporary), [], 'other')
