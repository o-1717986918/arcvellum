"""Typed composition of repositories sharing one SQLite unit of work."""

from __future__ import annotations

from dataclasses import dataclass

from ..application.persistence_ports import Clock, IdGenerator
from .asset_history import AssetHistoryRepository
from .autopilot_runs import AutopilotRepository
from .context_ledgers import ContextLedgerRepository
from .creative_plans import CreativePlanRepository
from .mutation_receipts import MutationReceiptRepository
from .recycle_bin import RecycleBinRepository
from .resource_leases import ResourceLeaseRepository
from .sessions import SessionRepository
from .sqlite_uow import SqliteUnitOfWork


@dataclass(frozen=True)
class SqliteRepositorySet:
    autopilot_runs: AutopilotRepository
    sessions: SessionRepository
    context_ledgers: ContextLedgerRepository
    mutation_receipts: MutationReceiptRepository
    creative_plans: CreativePlanRepository
    recycle_bin: RecycleBinRepository
    resource_leases: ResourceLeaseRepository
    asset_history: AssetHistoryRepository


def compose_sqlite_repositories(
    uow: SqliteUnitOfWork,
    *,
    clock: Clock,
    ids: IdGenerator,
) -> SqliteRepositorySet:
    return SqliteRepositorySet(
        autopilot_runs=AutopilotRepository(uow, clock=clock, ids=ids),
        sessions=SessionRepository(uow, clock=clock, ids=ids),
        context_ledgers=ContextLedgerRepository(uow, clock=clock),
        mutation_receipts=MutationReceiptRepository(uow),
        creative_plans=CreativePlanRepository(uow, clock=clock),
        recycle_bin=RecycleBinRepository(uow),
        resource_leases=ResourceLeaseRepository(uow, clock=clock),
        asset_history=AssetHistoryRepository(uow),
    )


__all__ = ["SqliteRepositorySet", "compose_sqlite_repositories"]
