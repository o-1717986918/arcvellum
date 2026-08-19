"""Legacy one-argument lifecycle adapter kept outside the application core."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from ..application.lifecycle import ManagedProcessState
from ..application.lifecycle import ApplicationLifecycleManager as _ApplicationLifecycleManager
from ..application.ports import ApplicationPorts
from ..runtimes import RUNTIME_TYPES, agent_runner_status
from .defaults import build_default_application_ports


class ApplicationLifecycleManager(_ApplicationLifecycleManager):
    """Preserve the historical constructor while new code injects ports."""

    def __init__(
        self,
        config: dict[str, Any],
        ports: ApplicationPorts | None = None,
    ) -> None:
        selected = ports or build_default_application_ports(config)
        if ports is None:
            selected = replace(
                selected,
                runtime_ids=tuple(RUNTIME_TYPES),
                runner_status_loader=agent_runner_status,
            )
        super().__init__(config, selected)


__all__ = [
    "ApplicationLifecycleManager",
    "ApplicationPorts",
    "ManagedProcessState",
    "RUNTIME_TYPES",
    "agent_runner_status",
]
