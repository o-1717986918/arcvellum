import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.scene_handoff import build_scene_handoff, scene_handoff_status


class SceneHandoffTests(unittest.TestCase):
    def test_promoted_predecessor_requires_digest_bound_handoff(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scenes").mkdir(parents=True)
            (root / "drafts" / "scenes").mkdir(parents=True)
            (root / "drafts" / "promotions").mkdir(parents=True)
            (root / "scenes" / "scene_0001.yaml").write_text("scene_id: scene_0001\ntimeline_order: 1\nlocation: dock\noutgoing_hooks:\n  - bell\n", encoding="utf-8")
            (root / "scenes" / "scene_0002.yaml").write_text("scene_id: scene_0002\ntimeline_order: 2\n", encoding="utf-8")
            (root / "drafts" / "scenes" / "scene_0001.md").write_text("# Draft\n\n正文。\n", encoding="utf-8")
            (root / "drafts" / "promotions" / "scene_0001_promotion.json").write_text(json.dumps({"scene_id": "scene_0001"}), encoding="utf-8")

            ready, message, _payload = scene_handoff_status(root, "scene_0002")
            self.assertFalse(ready)
            self.assertIn("missing", message)

            handoff = build_scene_handoff(root, "scene_0001")
            self.assertTrue(handoff.is_file())
            ready, _message, payload = scene_handoff_status(root, "scene_0002")
            self.assertTrue(ready)
            self.assertEqual(payload["outgoing_hooks"], ["bell"])

            (root / "drafts" / "scenes" / "scene_0001.md").write_text("# Draft\n\n被改过。\n", encoding="utf-8")
            ready, message, _payload = scene_handoff_status(root, "scene_0002")
            self.assertFalse(ready)
            self.assertIn("stale", message)


if __name__ == "__main__":
    unittest.main()
