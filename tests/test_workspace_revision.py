from __future__ import annotations

import unittest

from literary_engineering_studio.api.streaming import read_model_revision
from literary_engineering_studio.projections.workspace_revision import build_workspace_revisions


class WorkspaceRevisionTests(unittest.TestCase):
    def test_builds_stable_section_and_aggregate_revisions(self):
        sections = {
            "dashboard": {"current_task": {"task_id": "task-1"}},
            "library": {"generated_at": "fixed", "sections": {}},
            "delivery": {"status": "draft"},
            "reader_manifest": {"project_revision": "reader-1", "units": []},
            "project_progress": {"revision": "progress-1", "overall_percent": 10},
            "autopilot_status": {"run": None},
            "agent_observability": {"revision": "agent-1", "sessions": []},
        }

        first, first_revision = build_workspace_revisions(sections)
        second, second_revision = build_workspace_revisions({key: dict(value) for key, value in sections.items()})

        self.assertEqual(first, second)
        self.assertEqual(first_revision, second_revision)
        self.assertEqual(first["reader_manifest"], "reader-1")
        self.assertEqual(first["agent_observability"], "agent-1")

    def test_explicit_revision_coalesces_volatile_presentation_fields(self):
        first = {"revision": "workspace-1", "elapsed_seconds": 5}
        second = {"revision": "workspace-1", "elapsed_seconds": 15}

        self.assertEqual(read_model_revision(first), read_model_revision(second))
        self.assertNotEqual(
            read_model_revision({"elapsed_seconds": 5}),
            read_model_revision({"elapsed_seconds": 15}),
        )


if __name__ == "__main__":
    unittest.main()
