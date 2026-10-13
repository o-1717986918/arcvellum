from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from literary_engineering_studio.runtimes.scene_creator_natural import _validate_request_archive_choices
from literary_engineering_studio.runtimes.scene_creator_workspace import SceneCreatorWorkspace
from literary_engineering_studio.runtimes.natural_transport_repair import NaturalSourceClarificationError
from literary_engineering_studio_engine.public.projects import InitOptions, init_work_project


class ArchiveChoiceFieldRecoveryTests(unittest.TestCase):
    def test_scratch_alias_is_rejected_and_only_its_commission_fields_are_authorized(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            init_work_project(InitOptions(root / 'project', title='档案挂载回归'))
            workspace = SceneCreatorWorkspace(root / 'project', root / 'data')
            requests = [SimpleNamespace(kind='environment', attachments=[]),
                SimpleNamespace(kind='character-description',
                                attachments=[{'path':'creator_scratch: notes.md'}])]
            coordinator = SimpleNamespace(validate_request_archives=lambda rows:
                [workspace.freeze_attachments(row.attachments, kind=row.kind) for row in rows])
            with self.assertRaises(NaturalSourceClarificationError) as caught:
                _validate_request_archive_choices(requests, coordinator)
            self.assertEqual(caught.exception.fields, (
                '/material_requests/1/archive_attachments',
                '/material_requests/1/working_context', '/material_requests/1/need_evidence'))
            self.assertFalse((root / 'project' / 'notes.md').exists())
            self.assertIn('不能冒充作品档案', str(caught.exception))

    def test_empty_archive_selection_keeps_its_existing_validation(self):
        with TemporaryDirectory() as directory:
            init_work_project(InitOptions(Path(directory) / 'project', title='空挂载回归'))
            workspace = SceneCreatorWorkspace(Path(directory) / 'project', Path(directory) / 'data')
            coordinator = SimpleNamespace(validate_request_archives=lambda rows:
                [workspace.freeze_attachments([], kind=row.kind) for row in rows])
            _validate_request_archive_choices([SimpleNamespace(kind='environment')], coordinator)


if __name__ == '__main__':
    unittest.main()
