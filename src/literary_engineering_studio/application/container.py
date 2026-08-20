"""Application composition contracts independent of HTTP and desktop shells."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..advisor.service import ProjectAdvisor
from ..automation.controller import AutopilotService
from .bootstrap import ApplicationBootstrapService
from .lifecycle import ApplicationLifecycleManager
from .ports import ApplicationPorts
from .style.mount_service import StyleMountApplicationService
from ..observability.agent_session_tracking import track_agent_session_event


@dataclass(frozen=True)
class ApplicationServices:
    lifecycle: ApplicationLifecycleManager
    bootstrap: ApplicationBootstrapService
    advisor: ProjectAdvisor
    autopilot: AutopilotService
    style_mounts: StyleMountApplicationService


@dataclass(frozen=True)
class ApplicationContainer:
    config: dict[str, Any]
    ports: ApplicationPorts
    services: ApplicationServices

    def shutdown(self, *, wait: bool = True) -> None:
        self.services.autopilot.shutdown()
        self.services.bootstrap.shutdown()
        self.services.lifecycle.shutdown(wait=wait)


def build_application_container(
    config: dict[str, Any],
    ports: ApplicationPorts,
) -> ApplicationContainer:
    """Compose use cases over caller-owned ports without selecting adapters."""

    lifecycle = ApplicationLifecycleManager(config, ports)
    style_mounts = StyleMountApplicationService()
    bootstrap = ApplicationBootstrapService(config, lifecycle)
    application = config.get("application") if isinstance(config.get("application"), dict) else {}
    data_root = Path(str(application.get("data_root") or "."))
    session_event_tracker = lambda **fields: track_agent_session_event(ports.store, **fields)
    advisor = ProjectAdvisor(
        config,
        ports.persistence.sessions,
        runtime_pool=ports.runtime_pool,
        data_root=data_root,
        session_event_tracker=session_event_tracker,
    )
    autopilot = AutopilotService(
        config,
        runs=ports.persistence.autopilot,
        sessions=ports.persistence.sessions,
        plans=ports.persistence.plans,
        session_event_tracker=session_event_tracker,
        runtime_pool=ports.runtime_pool,
        execution_coordinator=ports.execution_coordinator,
        style_mount_service=style_mounts,
        prepared_context_cache=ports.prepared_context_cache,
    )
    return ApplicationContainer(
        config=config,
        ports=ports,
        services=ApplicationServices(
            lifecycle=lifecycle,
            bootstrap=bootstrap,
            advisor=advisor,
            autopilot=autopilot,
            style_mounts=style_mounts,
        ),
    )


__all__ = [
    "ApplicationContainer",
    "ApplicationPorts",
    "ApplicationServices",
    "build_application_container",
]
