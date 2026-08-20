from __future__ import annotations

import unittest

from literary_engineering_studio.protocols.scene_artifacts import (
    is_scene_revision_candidate_path,
    is_scene_revision_manifest_path,
    is_scene_revision_transaction_path,
)


class SceneArtifactPathTests(unittest.TestCase):
    def test_accepts_unversioned_and_versioned_revision_pair(self) -> None:
        for suffix in ("", "_02", "_12"):
            candidate = f"drafts/revisions/scene_0001_revision{suffix}.md"
            manifest = f"drafts/revisions/scene_0001_revision{suffix}.json"
            self.assertTrue(is_scene_revision_candidate_path(candidate))
            self.assertTrue(is_scene_revision_manifest_path(manifest))
            self.assertTrue(is_scene_revision_transaction_path(candidate))
            self.assertTrue(is_scene_revision_transaction_path(manifest))

    def test_rejects_control_and_report_artifacts(self) -> None:
        rejected = (
            "drafts/revisions/scene_0001_revision_02.prompt.json",
            "drafts/revisions/scene_0001_revision_02_report.md",
            "drafts/revisions/scene_0001_revision_02.agent_tasks.md",
            "drafts/scenes/scene_0001_revision_02.md",
            "drafts/revisions/not-a-revision.md",
        )
        for path in rejected:
            self.assertFalse(is_scene_revision_transaction_path(path), path)


if __name__ == "__main__":
    unittest.main()
