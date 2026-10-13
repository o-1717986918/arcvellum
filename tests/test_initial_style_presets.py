import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from literary_engineering_studio.application.project_manager import create_project
from literary_engineering_studio.application.style.initial_presets import initialize_style_presets
from literary_engineering_studio.application.style.stylometry_service import StylometryService
from literary_engineering_studio.infrastructure.stylometry_analysis import LabStylometryAnalysis
from literary_engineering_studio.persistence.stylometry import FileStylometryRepository


class InitialStylePresetTests(unittest.TestCase):
    def test_modes_are_really_measured_with_complete_declared_training_and_holdout(self):
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            with patch("literary_engineering_studio.application.project_manager.default_config_path", return_value=base / "config.json"):
                root = Path(create_project(parent_directory=str(base), title="文风预设", folder_name="work")["path"])
            service = StylometryService(LabStylometryAnalysis(base / "cache"), FileStylometryRepository(base / "data"))
            catalog = initialize_style_presets(service, root)
            self.assertEqual(len(catalog["presets"]), 4)
            self.assertEqual(len(catalog["reference_catalog"]["references"]), 39)
            for row in catalog["presets"]:
                snapshot = row["snapshot"]; self.assertTrue(snapshot["enabled"])
                profile = service.profile(root, snapshot["profile_id"])
                self.assertEqual({source["split"] for source in profile["source_declarations"]}, {"train", "holdout"})
                version = service.version(root, snapshot["version_id"])
                compiled = json.loads(version["compiled_json"])
                self.assertEqual(len(compiled["targets"]), 4)
                self.assertTrue(all(target["observed"] is not None for target in compiled["targets"]))
            self.assertEqual(initialize_style_presets(service, root)["revision"], 1)

    def test_verified_print_wrap_reflow_preserves_paragraphs_and_reference(self):
        from literary_engineering_studio.application.style.initial_presets import _measurement_text
        row = {'source_kind': 'verified_literary_original', 'source_title': '《老殘遊記》原文', 'text': '第一行\n第二行\n\n另一段。'}
        self.assertEqual(_measurement_text(row), '第一行第二行\n\n另一段。')
        self.assertEqual(row['text'], '第一行\n第二行\n\n另一段。')
        self.assertEqual(_measurement_text({**row, 'source_title': '用户样段'}), row['text'])
        self.assertEqual(_measurement_text({**row, 'source_kind': 'user_supplied_example'}), row['text'])

    def test_selected_references_recompute_version_and_keep_editor_choices_and_history(self):
        from dataclasses import replace
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            with patch('literary_engineering_studio.application.project_manager.default_config_path', return_value=base/'config.json'):
                root = Path(create_project(parent_directory=str(base), title='重算预设', folder_name='work')['path'])
            service = StylometryService(LabStylometryAnalysis(base/'cache'), FileStylometryRepository(base/'data'))
            initialize_style_presets(service, root)
            collection = service.repository.presets(root)
            chosen = replace(collection.presets[0], title='世界的热闹', literary_intent='以华丽而机智的声音叙述风俗',
                             reference_ids=('S01', 'S02'), combine='replace', usage='observe')
            service.save_presets(root, replace(collection, presets=(chosen, *collection.presets[1:])), collection.revision)
            original = service.version(root, chosen.stylometry_version_id)
            catalog = service.recalculate_preset(root, chosen.preset_id, 2)
            new = catalog['presets'][0]
            self.assertEqual((new['title'], new['literary_intent'], tuple(new['reference_ids']), new['combine'], new['usage']),
                             (chosen.title, chosen.literary_intent, chosen.reference_ids, chosen.combine, chosen.usage))
            self.assertNotEqual(new['stylometry_version_id'], chosen.stylometry_version_id)
            self.assertEqual(service.version(root, chosen.stylometry_version_id), original)
            profile = service.profile(root, new['snapshot']['profile_id'])
            self.assertEqual([(row['source_id'], row['split']) for row in profile['source_declarations']], [('s01', 'train'), ('s02', 'holdout')])
            before = len(service.workbench(root)['profiles'])
            with self.assertRaisesRegex(ValueError, '已更新'):
                service.recalculate_preset(root, chosen.preset_id, 2)
            self.assertEqual(len(service.workbench(root)['profiles']), before)
