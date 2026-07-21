from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.execution_coordinator import ProjectExecutionCoordinator
from literary_engineering_studio.supervisor import project_lock_key


class ProjectExecutionCoordinatorTests(unittest.TestCase):
    def test_serializes_one_project_but_not_different_projects(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            coordinator = ProjectExecutionCoordinator()

            self.assertTrue(coordinator.acquire(first, "manual"))
            self.assertFalse(coordinator.acquire(first, "autopilot"))
            self.assertTrue(coordinator.acquire(second, "autopilot"))
            coordinator.release(first, "manual")
            self.assertTrue(coordinator.acquire(first, "autopilot"))

    def test_project_lock_is_shared_across_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            self.assertEqual(
                project_lock_key(project, "scene-development"),
                project_lock_key(project, "review-and-audit"),
            )


if __name__ == "__main__":
    unittest.main()
