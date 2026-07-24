from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.agent_tasks import (
    agent_task_completion_status,
    write_agent_completion_marker,
)


class AgentTaskFreshnessTests(unittest.TestCase):
    def test_reissued_task_invalidates_older_completion_marker(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = root / "branches" / "scene_0001" / "roleplay_simulation.agent_tasks.md"
            task.parent.mkdir(parents=True)
            task.write_text("first task\n", encoding="utf-8")
            completion = write_agent_completion_marker(task, root=root)
            os.utime(completion, ns=(1_000_000_000, 1_000_000_000))
            os.utime(task, ns=(2_000_000_000, 2_000_000_000))

            status = agent_task_completion_status(task, root=root)

            self.assertFalse(status["complete"])
            self.assertEqual(status["status"], "stale_completion")
            self.assertIn("predates", str(status["message"]))


if __name__ == "__main__":
    unittest.main()
