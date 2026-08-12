import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literary_engineering_studio_engine.workflow.state_scene import (
    next_scene_workflow_state,
)


class SceneWorkflowOrderTests(unittest.TestCase):
    def test_default_route_closes_earliest_scene_before_latest_touched_scene(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scenes = root / "scenes"
            scenes.mkdir()
            first = scenes / "scene_0001.yaml"
            second = scenes / "scene_0002.yaml"
            first.write_text("scene_id: scene_0001\n", encoding="utf-8")
            second.write_text("scene_id: scene_0002\n", encoding="utf-8")
            with patch(
                "literary_engineering_studio_engine.workflow.state_scene._scene_state",
                side_effect=lambda _root, path: {
                    "scene_id": path.stem,
                    "scene": f"scenes/{path.name}",
                    "status": "blocked",
                    "current_step": (
                        "state-patch-json"
                        if path.stem == "scene_0001"
                        else "candidate-generation-provenance"
                    ),
                },
            ):
                selected = next_scene_workflow_state(root)

            self.assertEqual(selected["scene_id"], "scene_0001")
            self.assertEqual(selected["current_step"], "state-patch-json")

    def test_explicit_scene_still_allows_non_linear_work(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scenes = root / "scenes"
            scenes.mkdir()
            second = scenes / "scene_0002.yaml"
            second.write_text("scene_id: scene_0002\n", encoding="utf-8")
            with patch(
                "literary_engineering_studio_engine.workflow.state_scene._scene_state",
                return_value={
                    "scene_id": "scene_0002",
                    "scene": "scenes/scene_0002.yaml",
                    "status": "blocked",
                    "current_step": "candidate-generation-provenance",
                },
            ):
                selected = next_scene_workflow_state(root, "scenes/scene_0002.yaml")

            self.assertEqual(selected["scene_id"], "scene_0002")


if __name__ == "__main__":
    unittest.main()
