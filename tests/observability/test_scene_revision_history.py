from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from literary_engineering_studio.observability.creative_live.contracts import artifact_id, project_id
from literary_engineering_studio.observability.creative_live.scene_revision_history import merge_scene_revision_history


class SceneRevisionHistoryTests(unittest.TestCase):
    def test_restores_initial_revision_and_exact_promoted_text_without_live_events(self) -> None:
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "project"
            cache = base / "scene-transactions" / "scene-tx-1"
            draft = root / "drafts" / "scenes" / "scene_0001.md"
            receipt = root / "workflow" / "scene_commits" / "scene_0001.json"
            cache.mkdir(parents=True)
            draft.parent.mkdir(parents=True)
            receipt.parent.mkdir(parents=True)
            first, revised = "她站在门外。", "她站在门外，听见有人唱歌。"
            (cache / "creative_result_first.json").write_text(json.dumps({"prose": first}), encoding="utf-8")
            (cache / "revision_result_1.json").write_text(json.dumps({"prose": revised}), encoding="utf-8")
            draft.write_text(revised + "\n", encoding="utf-8")
            receipt.write_text(json.dumps({
                "prose_sha256": hashlib.sha256(revised.encode("utf-8")).hexdigest(),
            }), encoding="utf-8")
            identity = artifact_id(project_id(root), "drafts/scenes/scene_0001.md", "scene-tx-1")
            event_history = [{
                "revision_id": identity + ":r1", "artifact_id": identity,
                "event_id": "commit", "at": "2099-01-01T00:00:00+00:00",
                "identity": "promoted", "content": "", "characters": 0,
            }]

            result = merge_scene_revision_history(
                root, base, [SimpleNamespace(transaction_id="scene-tx-1", scene_id="scene_0001")],
                identity, event_history,
            )

            self.assertEqual([item["content"] for item in result], [first, revised, revised])
            self.assertEqual(result[-1]["identity"], "promoted")
            self.assertIn("有人唱歌", result[1]["diff"])
            self.assertEqual(
                merge_scene_revision_history(root, base, [], identity, event_history), event_history,
            )


if __name__ == "__main__":
    unittest.main()
