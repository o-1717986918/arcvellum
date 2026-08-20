"""Shared contracts for one claimed Autopilot route cycle."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading
from typing import Any, Protocol

from ..advisor.creative_steward import CreativeSteward
from ..application.persistence_ports import AutopilotRepositoryPort
from ..runtime.worker import AgentWorker
from .policy import DelegationPolicy


@dataclass(frozen=True)
class RouteCycle:
    """The route identity and lock owner for one worker cycle."""

    route_index: int
    planned_route: str
    route: str
    dependency_route: bool
    owner: str


class RunLoopHost(Protocol):
    """Narrow controller capabilities shared by loop and result handler."""

    runs: AutopilotRepositoryPort
    execution_coordinator: Any

    def _worker(
        self,
        run_id: str,
        *,
        cancel_event: threading.Event | None = None,
    ) -> AgentWorker: ...

    def _resolve_proactive_choice(
        self,
        run_id: str,
        project: Path,
        route: str,
        policy: DelegationPolicy,
        steward: CreativeSteward,
        *,
        stop: threading.Event | None = None,
    ) -> bool: ...

    def _delegate_choice(
        self,
        run_id: str,
        project: Path,
        route: str,
        policy: DelegationPolicy,
        steward: CreativeSteward,
        choice: dict[str, Any],
        *,
        task_id: str = "",
        stop: threading.Event | None = None,
    ) -> bool: ...

    def _current_choices(self, project: Path, route: str) -> list[dict[str, Any]]: ...

    def _complete_release(
        self,
        run_id: str,
        project: Path,
        run: dict[str, Any],
        policy: DelegationPolicy,
    ) -> None: ...

    def _register_no_progress(
        self,
        run_id: str,
        task_id: str,
        route: str,
        message: str,
    ) -> bool: ...

    def _pause_for(self, run_id: str, reason: str, message: str) -> None: ...


__all__ = ["RouteCycle", "RunLoopHost"]
