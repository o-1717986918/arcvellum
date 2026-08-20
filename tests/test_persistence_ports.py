from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

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
from literary_engineering_studio.persistence.composition import sqlite_persistence_ports
from literary_engineering_studio.persistence.job_store import JobStore


class PersistencePortCompositionTests(unittest.TestCase):
    def test_sqlite_store_composes_named_structural_ports(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = JobStore(Path(temporary) / "studio.sqlite3")
            ports = sqlite_persistence_ports(store)

            self.assertIsInstance(ports.jobs, JobRepositoryPort)
            self.assertIsInstance(ports.autopilot, AutopilotRepositoryPort)
            self.assertIsInstance(ports.sessions, SessionRepositoryPort)
            self.assertIsInstance(ports.leases, LeaseRepositoryPort)
            self.assertIsInstance(ports.plans, PlanRepositoryPort)
            self.assertIsInstance(ports.asset_revisions, AssetRevisionIndexPort)
            self.assertIsInstance(ports.events, DurableEventStorePort)
            self.assertIsInstance(ports.unit_of_work, UnitOfWorkPort)
            self.assertIsInstance(ports.worker, WorkerPersistencePort)

    def test_composition_reuses_existing_repositories_and_plan_event_aggregate(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = JobStore(Path(temporary) / "studio.sqlite3")
            ports = sqlite_persistence_ports(store)

            self.assertIs(ports.facade, store)
            self.assertIs(ports.jobs, store)
            self.assertIs(ports.autopilot, store.autopilot_runs)
            self.assertIs(ports.sessions, store.sessions)
            self.assertIs(ports.leases, store.resource_leases)
            self.assertIs(ports.plans, store.creative_plans)
            self.assertIs(ports.asset_revisions, store.asset_history)
            self.assertIs(ports.events, store)
            self.assertIs(ports.unit_of_work, store.unit_of_work)
            self.assertTrue(callable(ports.plans.creative_plan_events))


if __name__ == "__main__":
    unittest.main()
