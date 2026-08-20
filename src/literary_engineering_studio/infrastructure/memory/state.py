"""Shared state container; behavior remains in aggregate-specific adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
import threading
from typing import Any


@dataclass
class MemoryPersistenceState:
    lock: threading.RLock = field(default_factory=threading.RLock)
    jobs: dict[str, dict[str, Any]] = field(default_factory=dict)
    job_events: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    project_locks: dict[str, dict[str, Any]] = field(default_factory=dict)
    resource_leases: dict[str, dict[str, Any]] = field(default_factory=dict)
    autopilot_runs: dict[str, dict[str, Any]] = field(default_factory=dict)
    autopilot_events: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    autopilot_leases: dict[str, dict[str, Any]] = field(default_factory=dict)
    delegated_decisions: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    advisor_sessions: dict[str, dict[str, Any]] = field(default_factory=dict)
    agent_sessions: dict[str, dict[str, Any]] = field(default_factory=dict)
    delegation_policies: dict[str, dict[str, Any]] = field(default_factory=dict)
    plans: dict[str, dict[str, Any]] = field(default_factory=dict)
    plan_revisions: dict[tuple[str, int], dict[str, Any]] = field(default_factory=dict)
    plan_events: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    asset_transactions: dict[tuple[str, str], list[dict[str, Any]]] = field(default_factory=dict)
    context_ledgers: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    mutation_receipts: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


__all__ = ["MemoryPersistenceState"]
