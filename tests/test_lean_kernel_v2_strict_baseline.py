from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.workflow.state_scene import _scene_state


_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "lean_kernel_v2"
    / "strict_v1_scene_baseline.json"
)


class LeanKernelStrictV1BaselineTests(unittest.TestCase):
    def test_minimal_scene_keeps_the_recorded_strict_v1_sequence(self) -> None:
        baseline = json.loads(_FIXTURE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            scene.write_text(
                "scene_id: scene_0001\nchapter_id: chapter_0001\n",
                encoding="utf-8",
            )

            state = _scene_state(root, scene)

        sequence = [str(step["key"]) for step in state["steps"]]
        self.assertEqual(sequence, baseline["state_sequence"])
        self.assertEqual(len(sequence), baseline["state_count"])
        self.assertEqual(state["current_step"], "context-packet")
        self.assertEqual(state["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
