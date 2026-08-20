from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock

from literary_engineering_studio.advisor.service import ProjectAdvisor
from literary_engineering_studio.api_server import create_app
from literary_engineering_studio.application.persistence_ports import (
    AssetRevisionIndexPort,
    AutopilotRepositoryPort,
    DurableEventStorePort,
    JobRepositoryPort,
    LeaseRepositoryPort,
    PlanRepositoryPort,
    SessionRepositoryPort,
    UnitOfWorkPort,
    WorkerPersistencePort,
)
from literary_engineering_studio.application.container import build_application_container
from literary_engineering_studio.application.ports import ApplicationPorts
from literary_engineering_studio.automation.controller import AutopilotService
from literary_engineering_studio.infrastructure.memory import (
    FrozenClock,
    SequenceIdGenerator,
    build_memory_persistence_ports,
)
from literary_engineering_studio.runtime.supervisor import WorkerSupervisor


class MemoryPersistenceContractTests(unittest.TestCase):
    def setUp(self):
        self.ports = build_memory_persistence_ports(
            clock=FrozenClock(datetime(2026, 8, 20, tzinfo=timezone.utc)),
            ids=SequenceIdGenerator(),
        )

    def test_composition_satisfies_named_runtime_protocols(self):
        self.assertIsInstance(self.ports.jobs, JobRepositoryPort)
        self.assertIsInstance(self.ports.worker, WorkerPersistencePort)
        self.assertIsInstance(self.ports.autopilot, AutopilotRepositoryPort)
        self.assertIsInstance(self.ports.sessions, SessionRepositoryPort)
        self.assertIsInstance(self.ports.leases, LeaseRepositoryPort)
        self.assertIsInstance(self.ports.plans, PlanRepositoryPort)
        self.assertIsInstance(self.ports.asset_revisions, AssetRevisionIndexPort)
        self.assertIsInstance(self.ports.events, DurableEventStorePort)
        self.assertIsInstance(self.ports.unit_of_work, UnitOfWorkPort)

    def test_job_and_event_contract_preserves_idempotency_and_revision(self):
        first = self.ports.jobs.create({"project_root": "C:/work"}, idempotency_key="same")
        repeated = self.ports.jobs.create({"project_root": "ignored"}, idempotency_key="same")
        self.assertEqual(first["job_id"], repeated["job_id"])
        self.assertTrue(self.ports.jobs.claim(first["job_id"], "worker", lease_seconds=30))
        completed = self.ports.jobs.update(first["job_id"], status="complete", result={"ok": True})
        self.assertEqual(completed["revision"], 2)
        self.assertEqual(
            [item["event"] for item in self.ports.events.events_since(first["job_id"])],
            ["run.queued", "run.started", "run.complete"],
        )

    def test_autopilot_session_and_asset_contracts_share_one_state(self):
        policy = {"mode": "autonomous", "limits": {"max_tasks": 4}}
        saved_policy = self.ports.sessions.save_delegation_policy("C:/work", policy)
        run = self.ports.autopilot.create_autopilot_run(
            "C:/work",
            mode="autonomous",
            runtime="pi-agent",
            policy=saved_policy["policy"],
        )
        advanced = self.ports.autopilot.advance_autopilot_run(run["run_id"], current_route="scene-development")
        self.assertEqual(advanced["tasks_completed"], 1)
        self.assertEqual(self.ports.sessions.read_delegation_policy("C:/work")["policy"], policy)

        transaction = {
            "transaction_id": "tx-1",
            "project_root": "C:/work",
            "asset_id": "character:lin",
            "base_revision": "sha256:a",
            "new_revision": "sha256:b",
            "before_snapshot": "before.yaml",
            "after_snapshot": "after.yaml",
            "created_at": "2026-08-20T00:00:00+00:00",
        }
        self.ports.asset_revisions.record_asset_transaction(transaction)
        self.assertEqual(len(self.ports.asset_revisions.list_asset_revisions("C:/work", "character:lin")), 2)

    def test_worker_supervisor_runs_without_sqlite(self):
        job = self.ports.jobs.create({"project_root": "C:/work"})
        supervisor = WorkerSupervisor(self.ports.worker, max_workers=1, lease_seconds=30)
        try:
            supervisor.submit(
                job["job_id"],
                lambda _stop: {"status": "complete", "value": 2},
                lock_key="project:C:/work:execution",
            )
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                result = self.ports.jobs.read(job["job_id"])
                if result["status"] == "complete":
                    break
                time.sleep(0.02)
            self.assertEqual(self.ports.jobs.read(job["job_id"])["status"], "complete")
        finally:
            supervisor.shutdown()

    def test_advisor_and_autopilot_accept_named_memory_ports(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "work"
            project.mkdir()
            (project / "project.yaml").write_text("title: 内存测试\n", encoding="utf-8")
            advisor = ProjectAdvisor(
                {"application": {"data_root": str(root)}},
                self.ports.sessions,
                data_root=root,
                session_event_tracker=lambda **_fields: None,
            )
            session = advisor.create_session(project)
            self.assertEqual(advisor.list_sessions(project)[0]["session_id"], session["session_id"])

            autopilot = AutopilotService(
                {"application": {"data_root": str(root)}},
                runs=self.ports.autopilot,
                sessions=self.ports.sessions,
                plans=self.ports.plans,
                session_event_tracker=lambda **_fields: None,
            )
            try:
                self.assertEqual(autopilot.policy(project)["policy"]["mode"], "collaborative")
            finally:
                autopilot.shutdown()

    def test_application_container_composes_without_sqlite(self):
        supervisor = Mock()
        supervisor.health.return_value = {"ready": True}
        runtime_pool = Mock()
        runtime_pool.status.return_value = {"ready": True}
        process_manager = Mock()
        process_manager.status.return_value = []
        prepared_context_cache = Mock()
        prepared_context_cache.status.return_value = {"enabled": False}
        ports = ApplicationPorts(
            persistence=self.ports,
            live_events=Mock(),
            read_models=Mock(),
            prepared_context_cache=prepared_context_cache,
            process_manager=process_manager,
            runtime_pool=runtime_pool,
            execution_coordinator=Mock(),
            supervisor=supervisor,
            runtime_ids=("pi-agent",),
            runner_status_loader=lambda *_args, **_kwargs: [],
            model_connection_status_loader=lambda _config: {"ready": True},
        )
        container = build_application_container(
            {"application": {"data_root": "."}},
            ports,
        )
        try:
            self.assertIs(container.ports.persistence, self.ports)
            self.assertTrue(container.services.lifecycle.health()["ready"])
            self.assertIs(create_app(container=container).state.container, container)
        finally:
            container.shutdown()


if __name__ == "__main__":
    unittest.main()
