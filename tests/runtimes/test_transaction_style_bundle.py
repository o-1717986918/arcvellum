from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from tests.runtimes.test_less_ai_tone_experiment import runtime, brief
from tests.runtimes.test_creator_stylometry import snapshot
from literary_engineering_studio.runtimes.scene_natural_output import creator_style, validate_extracted_text
from literary_engineering_studio.application.style.transaction_bundle import TransactionStyleBundleV1


class TransactionStyleBundleTests(unittest.TestCase):
    def catalog(self):
        return {"revision": 3, "enabled": True, "presets": [{"preset_id": "world-narration", "active": True,
            "literary_intent": "展开世界", "snapshot": snapshot("世界计量目标").to_dict()}],
            "reference_catalog": {"references": [{"unit_id": "R24", "source_title": "用户样段", "text": "世界参照完整原文"}]}}

    def test_creator_editor_review_share_selected_complete_refs_and_measurement(self):
        with TemporaryDirectory() as temporary:
            adapter = runtime(Path(temporary)); adapter._config["application"]["scene_creator_v2"] = {"enabled": True}
            catalog = self.catalog(); adapter._style_preset_catalog_provider = lambda _: catalog
            choice = {"preset_id": "world-narration", "reference_ids": ["R24"], "reason": "展开森林众人的生活", "literary_mode": "风俗概述"}
            with patch.object(adapter, "_select_transaction_style", return_value=choice), patch(
                "literary_engineering_studio.runtimes.scene_creator_briefing.active_style_prompt_text", return_value="正式通用文风"):
                bundle = adapter._prepare_transaction_style_bundle("chosen", brief())
            mount = adapter._tone_mount("chosen", brief())
            self.assertTrue(mount["enabled"])
            self.assertEqual(mount["style"], creator_style({"style": bundle["style"]}))
            self.assertIn("世界参照完整原文", mount["style"]); self.assertIn("世界计量目标", mount["style"])
            catalog["presets"][0]["snapshot"] = snapshot("后来参数").to_dict()
            adapter._config["application"]["less_ai_tone_experiment"]["enabled"] = False
            self.assertEqual(adapter._prepare_transaction_style_bundle("chosen", brief()), bundle)
            corrupt = deepcopy(bundle); corrupt["selection"]["reason"] = "被修改"
            with self.assertRaisesRegex(ValueError, "digest"):
                TransactionStyleBundleV1.validate(corrupt)

    def test_interrupted_choice_uses_frozen_catalog_after_configuration_changes(self):
        with TemporaryDirectory() as temporary:
            adapter = runtime(Path(temporary)); adapter._config["application"]["scene_creator_v2"] = {"enabled": True}
            adapter._style_preset_catalog_provider = lambda _: self.catalog()
            with patch.object(adapter, "_select_transaction_style", side_effect=RuntimeError("interrupted")):
                with self.assertRaisesRegex(RuntimeError, "interrupted"):
                    adapter._prepare_transaction_style_bundle("interrupted", brief())
            adapter._cache_path("interrupted", "prompt_assembly_v2.json").write_text("{}", encoding="utf-8")
            adapter._style_preset_catalog_provider = lambda _: {"enabled": False}
            choice = {"preset_id": "world-narration", "reference_ids": ["R24"], "reason": "风俗与季节", "literary_mode": "概述"}
            with patch.object(adapter, "_select_transaction_style", return_value=choice):
                self.assertEqual(adapter._prepare_transaction_style_bundle("interrupted", brief())["preset_revision"], 3)

    def test_selection_extraction_keeps_author_choice_and_rejects_invented_reference(self):
        answer = "world-narration，R24。以风俗概述展开世界，因为读者值得认识森林的生活。"
        choice = {"preset_id": "world-narration", "reference_ids": ["R24"], "literary_mode": "风俗概述", "reason": "读者值得认识森林的生活"}
        context = {"preset_ids": ["world-narration"], "reference_ids": ["R24"]}
        validate_extracted_text(answer, choice, "style-choice", context)
        choice["reference_ids"] = ["R25"]
        with self.assertRaisesRegex(ValueError, "unavailable"):
            validate_extracted_text(answer, choice, "style-choice", context)

    def test_replace_and_observe_use_one_bundle_for_creator_and_editor(self):
        for usage, general_present, metric_present in [('guide', False, True), ('observe', True, False)]:
            with self.subTest(usage=usage), TemporaryDirectory() as temporary:
                adapter = runtime(Path(temporary)); adapter._config['application']['scene_creator_v2'] = {'enabled': True}
                catalog = self.catalog(); catalog['presets'][0]['snapshot'].update(combine='replace', usage=usage)
                adapter._style_preset_catalog_provider = lambda _: catalog
                choice = {'preset_id': 'world-narration', 'reference_ids': ['R24'], 'reason': '展开森林生活', 'literary_mode': '风俗叙述'}
                with patch.object(adapter, '_select_transaction_style', return_value=choice), patch(
                    'literary_engineering_studio.runtimes.scene_creator_briefing.active_style_prompt_text', return_value='正式通用文风'):
                    bundle = adapter._prepare_transaction_style_bundle('selected', brief())
                text = bundle['style']['assembled']['content']
                self.assertEqual('正式通用文风' in text, general_present)
                self.assertEqual('世界计量目标' in text, metric_present)
                self.assertEqual(adapter._tone_mount('selected', brief())['style'], text)
                self.assertEqual(bundle['measurement']['usage'], usage)
