import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.context_broker import context_trace_status
from literary_engineering_studio_engine.context_packet import build_context_packet
from literary_engineering_studio_engine.workflow_state import _scene_state


class ContextTraceV2Tests(unittest.TestCase):
    def test_trace_records_digests_and_detects_changed_canon(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scenes").mkdir(parents=True)
            (root / "canon").mkdir()
            (root / "memory").mkdir()
            (root / "project.yaml").write_text("title: Test\n", encoding="utf-8")
            (root / "canon" / "world_rules.yaml").write_text("rule: first\n", encoding="utf-8")
            (root / "scenes" / "scene_0001.yaml").write_text("scene_id: scene_0001\nparticipants: []\n", encoding="utf-8")

            result = build_context_packet(root, rebuild_index=True)
            trace = json.loads(result.trace_path.read_text(encoding="utf-8"))

            self.assertEqual(trace["schema"], "literary-engineering-workbench/context-trace/v2")
            self.assertTrue(trace["loaded_sources"])
            self.assertTrue(all(item["sha256"] for item in trace["loaded_sources"]))
            self.assertEqual(context_trace_status(root, "scene_0001").status, "pass")

            (root / "canon" / "world_rules.yaml").write_text("rule: changed\n", encoding="utf-8")
            status = context_trace_status(root, "scene_0001")
            self.assertEqual(status.status, "stale")
            self.assertIn("canon/world_rules.yaml", status.message)

    def test_state_machine_rewinds_to_context_then_roleplay_after_source_change(self):
        """A rebuilt trace must invalidate every later scene artifact in order."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            (root / "canon").mkdir()
            (root / "project.yaml").write_text("title: Test\n", encoding="utf-8")
            (root / "canon" / "world_rules.yaml").write_text("rule: first\n", encoding="utf-8")
            scene.write_text("scene_id: scene_0001\nparticipants: []\n", encoding="utf-8")
            build_context_packet(root, scene=scene, rebuild_index=True)

            roleplay = root / "branches" / "scene_0001" / "roleplay_simulation.md"
            roleplay.parent.mkdir(parents=True)
            roleplay.write_text("formal roleplay evidence\n", encoding="utf-8")

            (root / "canon" / "world_rules.yaml").write_text("rule: changed\n", encoding="utf-8")
            stale = _scene_state(root, scene)
            self.assertEqual(stale["current_step"], "context-trace")
            stale_steps = {step["key"]: step for step in stale["steps"]}
            self.assertEqual(stale_steps["context-trace"]["status"], "stale")

            build_context_packet(root, scene=scene, rebuild_index=True)
            rewound = _scene_state(root, scene)
            self.assertEqual(rewound["current_step"], "roleplay-simulation")
            rewound_steps = {step["key"]: step for step in rewound["steps"]}
            self.assertEqual(rewound_steps["roleplay-simulation"]["status"], "stale")


if __name__ == "__main__":
    unittest.main()
