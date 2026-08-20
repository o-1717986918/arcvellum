from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.infrastructure.memory import (
    FrozenClock,
    SequenceIdGenerator,
)
from literary_engineering_studio.observability.context_ledger import ContextLedger
from literary_engineering_studio.persistence.job_store import JobStore
from literary_engineering_studio.runtime.resources import ResourceClaim

from tests.orchestration.plan_persistence_support import index_record


FIXED_TIME = datetime(2026, 8, 20, 0, 0, tzinfo=timezone.utc)
FIXED_ISO = FIXED_TIME.isoformat()


class SqliteTimeIdentityContractTests(unittest.TestCase):
    def test_composed_repositories_share_clock_and_identity_sequence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = JobStore(
                root / "studio.sqlite3",
                clock=FrozenClock(FIXED_TIME),
                ids=SequenceIdGenerator(),
            )

            job = store.create({"project_root": str(root)})
            run = store.create_autopilot_run(
                str(root),
                mode="collaborative",
                runtime="pi-agent",
                policy={"mode": "collaborative"},
            )
            session = store.create_advisor_session(str(root), "snapshot-one")
            notice = store.upsert_advisor_inbox(
                str(root),
                dedupe_key="test-notice",
                kind="status",
                severity="info",
                title="测试",
                message="确定性边界",
            )

            self.assertEqual(job["job_id"], "job-0000000000000001")
            self.assertEqual(run["run_id"], "autopilot-0000000000000002")
            self.assertEqual(session["session_id"], "advisor-0000000000000003")
            self.assertEqual(notice["item_id"], "notice-0000000000000004")
            self.assertEqual(job["created_at"], FIXED_ISO)
            self.assertEqual(run["created_at"], FIXED_ISO)
            self.assertEqual(session["created_at"], FIXED_ISO)
            self.assertEqual(notice["created_at"], FIXED_ISO)
            self.assertEqual(store.events_since(job["job_id"])[0]["at"], FIXED_ISO)

    def test_lease_context_and_plan_boundaries_use_injected_clock(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = JobStore(
                root / "studio.sqlite3",
                clock=FrozenClock(FIXED_TIME),
                ids=SequenceIdGenerator(),
            )
            job = store.create({"project_root": str(root)})
            claim = ResourceClaim(
                task_node_id="scene-one",
                project_id="project-one",
                reads=("canon/world.yaml",),
                writes=(),
                runtime_slot="agent-worker",
                model_slot="default",
                network="none",
                exclusive_barriers=(),
            )
            lease_id = store.acquire_resource_lease(
                claim.as_dict(),
                job_id=job["job_id"],
                lease_owner="worker-one",
                lease_seconds=60,
                conflicts=lambda _left, _right: False,
            )
            lease = next(
                item for item in store.list_resource_leases("project-one")
                if item["lease_id"] == lease_id
            )
            self.assertEqual(lease["updated_at"], FIXED_ISO)
            self.assertEqual(
                lease["lease_expires_at"],
                "2026-08-20T00:01:00+00:00",
            )

            ledger = ContextLedger(
                ledger_id="context-deterministic-clock",
                project_root_hash="project-hash",
                session_id="session-one",
                operation_id="operation-one",
                plan_id="",
                entries=(),
                assembled_sha256="a" * 64,
            )
            persisted_ledger = store.record_context_ledger(
                str(root),
                ledger.as_dict(),
            )
            self.assertEqual(persisted_ledger["created_at"], FIXED_ISO)

            record = index_record("plan-deterministic-clock", project_root=root)
            record.pop("created_at")
            revision = store.reserve_creative_plan_revision(record)
            events = store.creative_plan_events("plan-deterministic-clock")
            self.assertEqual(revision["created_at"], FIXED_ISO)
            self.assertEqual(events[0]["at"], FIXED_ISO)


if __name__ == "__main__":
    unittest.main()
