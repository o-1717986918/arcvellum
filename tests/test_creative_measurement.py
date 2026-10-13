"""Target changes preserve measured evidence and frozen acceptance instances."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from literary_engineering_studio.application.style.stylometry_contracts import (
    CorpusTextSource, StylePresetV1, StylePresetCollectionV1,
)
from literary_engineering_studio.application.style.stylometry_service import StylometryService
from literary_engineering_studio.infrastructure.stylometry_analysis import LabStylometryAnalysis
from literary_engineering_studio.persistence.stylometry import FileStylometryRepository
from tests.acceptance.creative_measurement import configure_targets


class CreativeMeasurementTests(unittest.TestCase):
    def test_real_statistics_remain_while_target_versions_are_changed_and_resumable(self):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            project = folder / 'work'; project.mkdir()
            (project / 'project.yaml').write_text('title: 技术统计回归', encoding='utf-8')
            repository = FileStylometryRepository(folder / 'data')
            service = StylometryService(LabStylometryAnalysis(), repository)
            profile = service.analyze(project, (
                CorpusTextSource('train', 'one', '风从河面吹来。她把门推开，看看炉中的火。' * 30),
                CorpusTextSource('holdout', 'two', '他循着山路走过去。石头上落着水。' * 30, split='holdout'),
            ), '合成技术证据')
            original = service.save_version(project, profile['profile_id'], json.dumps(profile['controls']), title='世界')
            preset = StylePresetV1('world', '世界', '讲述世界', ('world',), ('train',), original['version_id'])
            service.save_presets(project, StylePresetCollectionV1(0, True, 'world', (preset,)), 0)
            configuration = folder / 'targets.json'
            payload = {'schema': 'arcvellum/measurement-acceptance-targets/v1',
                       'presets': {'world': {'sentence_length_han': {'min': 30, 'max': 45}}}}
            configuration.write_text(json.dumps(payload), encoding='utf-8')
            before = service.profile(project, profile['profile_id'])['profile_json']
            record = configure_targets(service, project, folder, configuration)
            current = repository.presets(project).presets[0]
            version = service.version(project, current.stylometry_version_id)
            target = next(row for row in json.loads(version['controls_json'])['targets'] if row['id'] == 'sentence_length_han')
            self.assertEqual((target['min'], target['max']), (30, 45))
            self.assertEqual(service.profile(project, profile['profile_id'])['profile_json'], before)
            self.assertEqual(service.version(project, original['version_id']), original)
            self.assertEqual(configure_targets(service, project, folder, configuration), record)
            self.assertEqual(len(repository.versions(project)), 2)
            payload['presets']['world']['sentence_length_han']['max'] = 50
            configuration.write_text(json.dumps(payload), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, '配置已变化'):
                configure_targets(service, project, folder, configuration)
            other = folder / 'already-frozen'; (other / 'data/scene-transactions/tx').mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, '交易已经冻结'):
                configure_targets(service, project, other, configuration)
