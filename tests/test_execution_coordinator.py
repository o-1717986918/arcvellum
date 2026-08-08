from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from literary_engineering_studio.execution_coordinator import ProjectExecutionCoordinator
from literary_engineering_studio.runtime.execution_admission import (
    ExecutionAdmission,
    release_execution_admission,
)
from literary_engineering_studio.runtime.resources import ResourceClaim, project_identity
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

    def test_read_only_claims_share_project_but_exclusive_owner_blocks_them(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            coordinator = ProjectExecutionCoordinator()
            first = _claim(project, "review-a", reads=("canon/a.yaml",))
            second = _claim(project, "review-b", reads=("canon/a.yaml",))

            self.assertTrue(coordinator.acquire_claim(project, "job-a", first))
            self.assertTrue(coordinator.acquire_claim(project, "job-b", second))
            self.assertEqual(coordinator.owners(project), ("job-a", "job-b"))
            self.assertFalse(coordinator.acquire(project, "writer"))

            coordinator.release(project, "job-a")
            coordinator.release(project, "job-b")
            self.assertTrue(coordinator.acquire(project, "writer"))
            self.assertFalse(coordinator.acquire_claim(project, "job-c", first))

    def test_conflicting_claims_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            coordinator = ProjectExecutionCoordinator()
            reader = _claim(project, "reader", reads=("drafts/scene.md",))
            writer = _claim(project, "writer", writes=("drafts/scene.md",))

            self.assertTrue(coordinator.acquire_claim(project, "read-job", reader))
            self.assertFalse(
                coordinator.acquire_claim(project, "write-job", writer)
            )

    def test_failed_durable_release_does_not_leave_process_owner(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            coordinator = ProjectExecutionCoordinator()
            claim = _claim(project, "reader", reads=("canon/a.yaml",))
            self.assertTrue(coordinator.acquire_claim(project, "job-a", claim))
            store = Mock()
            store.release_resource_lease.side_effect = RuntimeError(
                "database unavailable"
            )
            admission = ExecutionAdmission(
                project_root=str(project),
                coordinator_owner="job-a",
                job_id="job-a",
                resource_lease_id="resource-a",
            )

            with self.assertRaisesRegex(RuntimeError, "database unavailable"):
                release_execution_admission(store, coordinator, admission)

            self.assertEqual(coordinator.owners(project), ())


def _claim(
    project: Path,
    node_id: str,
    *,
    reads: tuple[str, ...] = (),
    writes: tuple[str, ...] = (),
) -> ResourceClaim:
    return ResourceClaim(
        task_node_id=node_id,
        project_id=project_identity(project),
        reads=reads,
        writes=writes,
        runtime_slot="agent-worker",
        model_slot="default",
        network="none",
        exclusive_barriers=(),
    )


if __name__ == "__main__":
    unittest.main()
