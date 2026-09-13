from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.project_agent.actions import dependencies_from_actions


class _Autopilot:
    def __init__(self):
        self.run = None
        self.authorized = None

    def start(self, root):
        self.run = {"run_id": "run-1", "project_root": str(root), "status": "running"}
        return self.run

    def status(self, _root):
        return {"ok": True, "run": self.run}

    def pause(self, run_id, *, reason):
        self.run = {**self.run, "run_id": run_id, "status": "paused", "stop_reason": reason}
        return self.run

    def resume(self, run_id, *, authorized):
        self.authorized = authorized
        self.run = {**self.run, "run_id": run_id, "status": "running"}
        return self.run


class ProjectAgentActionTests(unittest.TestCase):
    def test_actions_reuse_direction_and_autopilot_services(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            recorded = []
            autopilot = _Autopilot()
            actions = dependencies_from_actions(
                record_direction=lambda project, message, actor: recorded.append(
                    (project, message, actor)
                ) or {"record": {"message": message, "actor": actor}, "digest": "directions.md"},
                autopilot=autopilot,
            )

            direction = actions.record_direction(root, {"message": "保留开放结局"})
            started = actions.creation_control(root, {"operation": "start"})
            resumed = actions.creation_control(root, {"operation": "resume"})

            self.assertEqual(recorded[0], (root, "保留开放结局", "project-agent"))
            self.assertEqual(direction["operation"], "record_direction")
            self.assertEqual(started["run"]["status"], "running")
            self.assertEqual(resumed["run"]["status"], "running")
            self.assertFalse(autopilot.authorized)
            self.assertTrue(direction["receipt"]["token"])

    def test_control_requires_an_existing_run(self):
        actions = dependencies_from_actions(
            record_direction=lambda *_args, **_kwargs: {},
            autopilot=_Autopilot(),
        )
        with self.assertRaisesRegex(ValueError, "existing creation run"):
            actions.creation_control(Path("."), {"operation": "pause"})


if __name__ == "__main__":
    unittest.main()
