from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.persistence.job_store import JobStore
from literary_engineering_studio.runtime.resources import (
    ResourceClaim,
    claims_conflict,
)


def _claim(node: str, *, reads=(), writes=()) -> ResourceClaim:
    return ResourceClaim(
        task_node_id=node,
        project_id="project-test",
        reads=tuple(reads),
        writes=tuple(writes),
        runtime_slot="agent-worker",
        model_slot="default",
        network="none",
        exclusive_barriers=(),
    )


def _conflicts(left: dict, right: dict) -> bool:
    return claims_conflict(ResourceClaim(**_body(left)), ResourceClaim(**_body(right))).conflicts


def _body(payload: dict) -> dict:
    return {
        key: payload[key]
        for key in (
            "task_node_id",
            "project_id",
            "reads",
            "writes",
            "runtime_slot",
            "model_slot",
            "network",
            "exclusive_barriers",
        )
    }


class ResourceLeaseRepositoryTests(unittest.TestCase):
    def test_readers_share_and_writer_conflicts(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = JobStore(Path(temporary) / "studio.sqlite3")
            first = store.acquire_resource_lease(
                _claim("reader-a", reads=("canon/a.yaml",)).as_dict(),
                job_id="job-a",
                lease_owner="worker-a",
                lease_seconds=60,
                conflicts=_conflicts,
            )
            second = store.acquire_resource_lease(
                _claim("reader-b", reads=("canon/a.yaml",)).as_dict(),
                job_id="job-b",
                lease_owner="worker-b",
                lease_seconds=60,
                conflicts=_conflicts,
            )
            blocked = store.acquire_resource_lease(
                _claim("writer", writes=("canon/a.yaml",)).as_dict(),
                job_id="job-c",
                lease_owner="worker-c",
                lease_seconds=60,
                conflicts=_conflicts,
            )

            self.assertTrue(first)
            self.assertTrue(second)
            self.assertEqual(blocked, "")
            self.assertEqual(len(store.list_resource_leases("project-test")), 2)

    def test_renew_release_and_restart_preserve_lease(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "studio.sqlite3"
            store = JobStore(database)
            lease_id = store.acquire_resource_lease(
                _claim("reader", reads=("plot/a.json",)).as_dict(),
                job_id="job-a",
                lease_owner="worker-a",
                lease_seconds=60,
                conflicts=_conflicts,
            )

            restarted = JobStore(database)
            self.assertEqual(len(restarted.list_resource_leases()), 1)
            self.assertTrue(
                restarted.renew_resource_lease(
                    lease_id,
                    job_id="job-a",
                    lease_owner="worker-a",
                    lease_seconds=90,
                )
            )
            self.assertTrue(
                restarted.release_resource_lease(lease_id, job_id="job-a")
            )
            self.assertEqual(restarted.list_resource_leases(), [])


if __name__ == "__main__":
    unittest.main()
