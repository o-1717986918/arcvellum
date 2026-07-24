import json
import tempfile
import unittest
from pathlib import Path

from literary_engineering_studio_engine.candidate_promotion import _review_session_independence


class ReviewSessionIndependenceTests(unittest.TestCase):
    def test_current_contract_requires_a_different_reviewer_session(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "drafts" / "candidates" / "scene_0001-platform-agent.md"
            candidate.parent.mkdir(parents=True)
            candidate.write_text("正文。\n", encoding="utf-8")
            candidate.with_suffix(".json").write_text(
                json.dumps({"formal_contract_revision": "2026-07-23.3", "writer_session_id": "writer-a"}),
                encoding="utf-8",
            )

            self.assertFalse(_review_session_independence(root, candidate, {"reviewer_session_id": "writer-a"})[0])
            self.assertFalse(_review_session_independence(root, candidate, {})[0])
            self.assertTrue(_review_session_independence(root, candidate, {"reviewer_session_id": "reviewer-b"})[0])

    def test_legacy_candidate_keeps_a_migration_compatibility_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "drafts" / "candidates" / "scene_0001-platform-agent.md"
            candidate.parent.mkdir(parents=True)
            candidate.write_text("正文。\n", encoding="utf-8")
            candidate.with_suffix(".json").write_text("{}\n", encoding="utf-8")

            self.assertTrue(_review_session_independence(root, candidate, {})[0])


if __name__ == "__main__":
    unittest.main()
